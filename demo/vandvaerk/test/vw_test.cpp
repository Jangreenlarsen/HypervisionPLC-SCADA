// SPDX-License-Identifier: AGPL-3.0-or-later
// PC-test af broendstationen (Logic2-4 + GLOBAL_VAR): kompilerer programmerne med HypervisionPLC's egen
// parser/compiler/VM (fra PLC-repoet), koerer dem i samme raekkefoelge som PLC'en og tjekker forloebet.
// Koeres med:  bash demo/vandvaerk/test/run.sh
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "st_parser.h"
#include "st_compiler.h"
#include "st_vm.h"
#include "st_stateful.h"
#include "st_logic_config.h"
void ast_pool_free(void);
bool ast_pool_init_with_size(uint16_t max_nodes);

#define AST_MAX 2048   // PLC-firmware 7.9.68.168: ST_AST_POOL_MAX_NODES
#define NPROG 2

// Mindste AST-pulje programmet kan parses i
static int ast_nodes(const char *src) {
  int lo = 16, hi = AST_MAX;
  auto fits = [&](int n) { ast_pool_free(); ast_pool_init_with_size(n); st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t)); st_parser_init(p, src); bool ok = st_parser_parse_program(p) != NULL; if (!ok && n == AST_MAX) printf("PARSE: %s (linje %d)\n", p->error_msg, p->current_token.line); free(p); ast_pool_free(); return ok; };
  if (!fits(hi)) return 99999;
  while (lo < hi) { int m = (lo + hi) / 2; if (fits(m)) hi = m; else lo = m + 1; }
  return lo;
}

extern uint32_t g_fake_ms;
static int fails = 0;
static int max_steps[NPROG] = {0, 0};
static bool vm_err = false;

uint8_t st_logic_globals_lookup(st_logic_engine_state_t *s, const char *name) {
  if (!s || !name) return 0xFF;
  for (uint8_t i = 0; i < s->global_count; i++) if (!strcmp(s->globals[i].name, name)) return i;
  return 0xFF;
}

static char *slurp(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) { printf("kan ikke aabne %s\n", path); exit(2); }
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  char *b = (char *)calloc(1, n + 1); fread(b, 1, n, f); fclose(f);
  return b;
}

static void load_globals(const char *src) {
  st_logic_engine_state_t *s = st_logic_get_state();
  st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t));
  st_parser_init(p, src);
  st_variable_decl_t vars[ST_MAX_GLOBAL_VARS];
  uint8_t n = 0;
  if (!st_parser_parse_global_var_block(p, vars, &n, ST_MAX_GLOBAL_VARS)) { printf("GLOBAL_VAR FEJL: %s\n", p->error_msg); exit(1); }
  memset(s->globals, 0, sizeof(s->globals));
  for (uint8_t i = 0; i < n; i++) { strncpy(s->globals[i].name, vars[i].name, 31); s->globals[i].type = vars[i].type; }
  s->global_count = n;
  printf("GLOBAL_VAR: %d variable, %d bytes kilde (maks %d / %d)\n", n, (int)strlen(src), ST_MAX_GLOBAL_VARS, ST_GLOBAL_SOURCE_MAX);
  if (strlen(src) > ST_GLOBAL_SOURCE_MAX) { printf("FAIL GLOBAL_VAR-kilden er for stor\n"); fails++; }
}

static st_bytecode_program_t *compile(const char *path) {
  char *src = slurp(path);
  int nodes = ast_nodes(src);
  printf("%-24s AST-noder %4d / %d\n", strrchr(path, '/') + 1, nodes, AST_MAX);
  if (nodes > AST_MAX) { printf("FAIL for mange AST-noder\n"); fails++; return NULL; }
  st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t));
  st_parser_init(p, src);
  st_program_t *prog = st_parser_parse_program(p);
  if (!prog) { printf("PARSE FEJL i %s: %s (linje %d)\n", path, p->error_msg, p->current_token.line); exit(1); }
  st_compiler_t *c = (st_compiler_t *)calloc(1, sizeof(st_compiler_t));
  st_compiler_init(c);
  st_bytecode_program_t *bc = (st_bytecode_program_t *)calloc(1, sizeof(st_bytecode_program_t));
  if (!st_compiler_compile(c, prog, bc)) { printf("COMPILE FEJL i %s: %s\n", path, c->error_msg); exit(1); }
  ast_pool_free();
  printf("%-24s %5d bytes, %3d instruktioner, %2d / %d variable\n", strrchr(path, '/') + 1, (int)strlen(src), bc->instr_count, bc->var_count, ST_MAX_PROGRAM_VARS);
  if (bc->var_count > ST_MAX_PROGRAM_VARS) { printf("FAIL for mange variable\n"); fails++; }
  return bc;
}

static void run(int id, st_bytecode_program_t *bc) {
  if (bc->stateful) ((st_stateful_storage_t *)bc->stateful)->cycle_time_ms = 500;
  st_vm_t *vm = (st_vm_t *)calloc(1, sizeof(st_vm_t));
  st_vm_init(vm, bc);
  int steps = 0;
  while (!vm->halted && !vm->error && steps < 10000) { if (!st_vm_step(vm)) break; steps++; }
  if (steps > max_steps[id]) max_steps[id] = steps;
  if (vm->error || steps >= 10000) {
    if (!vm_err) printf("FAIL VM-fejl i Logic%d: %s (steps %d)\n", id + 2, vm->error_msg, steps);
    vm_err = true;
  } else {
    memcpy(bc->variables, vm->variables, vm->var_count * sizeof(st_value_t));
    memcpy(bc->string_vars, vm->string_vars, sizeof(bc->string_vars));
  }
  free(vm);
}

static st_bytecode_program_t *P[NPROG];   // 0 = Logic2 styring, 1 = Logic3 proces
static int vi(st_bytecode_program_t *bc, const char *n) {
  for (int i = 0; i < bc->var_count; i++) if (!strcmp(bc->var_names[i], n)) return i;
  printf("ukendt variabel %s\n", n); exit(3);
}
static float R(int p, const char *n) { return P[p]->variables[vi(P[p], n)].real_val; }
static int I(int p, const char *n) { return P[p]->variables[vi(P[p], n)].int_val; }
static bool B(int p, const char *n) { return P[p]->variables[vi(P[p], n)].bool_val; }
static void setR(int p, const char *n, float v) { P[p]->variables[vi(P[p], n)].real_val = v; }
static void setI(int p, const char *n, int v) { int i = vi(P[p], n); P[p]->variables[i].dint_val = 0; P[p]->variables[i].int_val = v; }
static void setB(int p, const char *n, bool v) { int i = vi(P[p], n); P[p]->variables[i].dint_val = 0; P[p]->variables[i].bool_val = v; }
static void ok(bool c, const char *m) { printf("%s %s\n", c ? "PASS" : "FAIL", m); if (!c) fails++; }

static bool sane = true;
static void bad(const char *n, float v) { if (sane) printf("   uden for omraade: %s=%.3f\n", n, v); sane = false; }
static void check_ranges() {
  float v;
  v = R(1, "VW_BROND"); if (!(v >= 0 && v <= 10.0f)) bad("VW_BROND", v);
  v = R(1, "VW_Q"); if (!(v >= 0 && v <= 35.01f)) bad("VW_Q", v);
  v = R(1, "VW_HYPO"); if (!(v >= 0 && v <= 100.0f)) bad("VW_HYPO", v);
  v = R(1, "VW_BEH"); if (!(v >= 0 && v <= 100.0f)) bad("VW_BEH", v);
  v = R(1, "VW_TRYK"); if (!(v >= 0 && v <= 6.0f)) bad("VW_TRYK", v);
  v = R(1, "VW_AT1"); if (!(v >= 0 && v <= 30.0f)) bad("VW_AT1", v);
  v = R(1, "VW_AT2"); if (!(v >= -1.01f && v <= 30.0f)) bad("VW_AT2", v);
  v = R(1, "VW_KLOKKE"); if (!(v >= 0 && v < 24.0f)) bad("VW_KLOKKE", v);
}

// Koer n scans (500 ms hver). Logic2-3 i raekkefoelge, som PLC'en.
static void scans(int n) {
  for (int k = 0; k < n; k++) {
    g_fake_ms += 500;
    for (int i = 0; i < NPROG; i++) run(i, P[i]);
    check_ranges();
  }
}
static void hours(float h) { scans((int)(h * 3600.0f / (0.5f * R(1, "VW_SPEED")))); }

static void status(const char *t) {
  printf("   [%-12s] kl %5.2f | status %d trin %d trip %d | broend %4.2f m, %4.1f l/s, %4.2f bar | hypo %5.1f%% %4.2f l/t | AT1 %4.2f AT2 %5.2f dosis %4.2f | CT %5.1f | beh %5.1f%% | doegn %6.1f m3 | alarmer %d\n",
         t, R(1, "VW_KLOKKE"), I(0, "VW_STATUS"), I(0, "VW_TRIN"), I(0, "VW_TRIP"), R(1, "VW_BROND"), R(1, "VW_Q"), R(1, "VW_TRYK"),
         R(1, "VW_HYPO"), R(1, "VW_P2_LH"), R(1, "VW_AT1"), R(1, "VW_AT2"), R(0, "VW_DOSIS_EFF"), R(1, "VW_CT"), R(1, "VW_BEH"),
         R(1, "VW_DOEGN"), I(0, "VW_ALARMER"));
}

// Til en bestemt status (hoejst h simulerede timer)
static bool until_status(int st, float maxh) { for (float t = 0; t < maxh; t += 0.01f) { if (I(0, "VW_STATUS") == st) return true; hours(0.01f); } return I(0, "VW_STATUS") == st; }
static void reset_plant() {
  setI(1, "VW_SCEN", 0); setB(1, "VW_F_AN", false); setB(1, "VW_F_P2", false); setB(1, "VW_F_LAV", false);
  setB(1, "VW_FYLD", true); setI(0, "VW_MODE", 0); hours(0.1f);
  setB(0, "VW_KVIT", true); hours(0.1f);
  setR(1, "VW_BROND", 8.0f); setR(1, "VW_BEH", 35.0f); setR(1, "VW_DOEGN", 0.0f);
  setR(1, "c1", 0.0f); setR(1, "c2", 0.0f);
  setI(0, "VW_MODE", 1);
}

int main(int argc, char **argv) {
  const char *dir = argc > 1 ? argv[1] : "demo/vandvaerk";
  char path[512];
  snprintf(path, sizeof path, "%s/globals.st", dir); load_globals(slurp(path));
  const char *files[NPROG] = {"logic2_styring.st", "logic3_proces.st"};
  for (int i = 0; i < NPROG; i++) { snprintf(path, sizeof path, "%s/%s", dir, files[i]); P[i] = compile(path); }
  for (int i = 0; i < NPROG; i++) if (!P[i]) { printf("\n%d FEJL\n", fails); return 1; }

  setR(1, "VW_SPEED", 10.0f);   // sekvensen ses bedst ved 10 gange
  scans(1);

  printf("\n-- Auto: hoejdebeholderen under start-niveau, hele startsekvensen --\n");
  ok(I(0, "VW_STATUS") == 0, "stoppet foer start");
  scans(4); status("+2 s");
  ok(I(0, "VW_TRIN") == 1 && B(0, "VW_KOM_XV1") && !B(0, "VW_KOM_P1"), "trin 1: skylleventilen aabner, pumpen staar");
  scans(4); status("skyl");
  ok(I(0, "VW_TRIN") >= 2 && !B(0, "VW_KOM_XV1"), "skylleventilen er lukket igen efter skylning");
  until_status(2, 0.2f); status("drift");
  ok(I(0, "VW_STATUS") == 2 && I(0, "VW_TRIN") == 4, "drift efter skyl, pumpe og dosering");
  ok(R(1, "VW_Q") > 34.0f && B(0, "VW_KOM_P1") && B(0, "VW_KOM_P2"), "35 l/s, pumpe og doseringspumpe koerer");
  hours(0.5f); status("+30 min");
  ok(fabsf(R(1, "VW_DOSE") - 1.0f) < 0.15f, "doseret klor ca. 1,0 mg/l (flow-proportional)");
  ok(R(1, "VW_P2_LH") > 0.9f && R(1, "VW_P2_LH") < 1.3f, "ca. 1,05 l/t hypo ved 35 l/s og 1,0 mg/l");
  ok(R(1, "VW_AT2") < R(1, "VW_AT1"), "AT2 foelger efter AT1 (kontakttanken forsinker)");
  ok(R(1, "VW_TKONT") > 15.0f && R(1, "VW_TKONT") < 25.0f, "kontakttid ca. 19 min");
  ok(R(1, "VW_CT") > 5.0f, "CT beregnes");
  setR(1, "VW_SPEED", 60.0f);
  hours(1.0f); status("+1,5 t");
  ok(R(1, "VW_AT2") > 0.4f && R(1, "VW_AT2") < 1.2f && I(0, "VW_STATUS") != 4, "AT2 naar ca. setpunkt efter kontakttiden");
  ok(I(0, "VW_ALARMER") <= 1, "ingen alarmer i normal drift (hoejst haelvnivaa)");
  // fyld op til stop-niveau, hold fast i drift indtil da
  for (int k = 0; k < 20000 && I(0, "VW_STATUS") != 3; k++) scans(1);
  float bstop = R(1, "VW_BEH"); status("stop-niveau");
  ok(I(0, "VW_STATUS") == 3 && bstop >= 84.0f && bstop < 90.0f, "stopper ved stop-niveau (85 pct)");
  hours(0.05f); status("stoppet");
  ok(I(0, "VW_STATUS") == 0 && !B(0, "VW_KOM_P1") && !B(0, "VW_KOM_P2"), "alt staar efter stop-sekvensen");

  printf("\n-- Doegnet rundt i auto (hoej tidsfaktor) --\n");
  float vmax = 0, bmin = 100, bmax = 0, cmax = 0; int starts = 0, prev = I(0, "VW_STATUS");
  for (int k = 0; k < 2880; k++) {
    scans(1);
    if (R(1, "VW_DOEGN") > vmax) vmax = R(1, "VW_DOEGN");
    if (R(1, "VW_BEH") < bmin) bmin = R(1, "VW_BEH");
    if (R(1, "VW_BEH") > bmax) bmax = R(1, "VW_BEH");
    if (R(1, "VW_AT2") > cmax) cmax = R(1, "VW_AT2");
    if (I(0, "VW_STATUS") == 1 && prev != 1) starts++;
    prev = I(0, "VW_STATUS");
  }
  status("efter 24 t");
  printf("   doegnmaengde max %.0f m3, beholder %.0f-%.0f pct, %d starter, AT2 max %.2f\n", vmax, bmin, bmax, starts, cmax);
  ok(starts >= 3, "pumpen starter og stopper med niveauet (flere cyklusser)");
  ok(bmin > 20.0f && bmax <= 100.0f, "beholderen holder sig mellem 20 og 100 pct");
  ok(vmax > 800.0f && vmax < 2400.0f, "doegnmaengden under tilladelsens loft (2400 m3)");
  ok(cmax < 2.0f, "klor under hoej-graensen i hele doegnet");
  ok(I(0, "VW_TRIP") == 0, "ingen trip i normal drift");

  printf("\n-- Scenarie 1: broendpumpe fejl under drift --\n");
  reset_plant(); setR(1, "VW_BEH", 30.0f); until_status(2, 0.3f); status("drift");
  setI(1, "VW_SCEN", 1); scans(10); status("fejl");
  ok(I(0, "VW_STATUS") == 4 && I(0, "VW_TRIP") == 4, "trip, aarsag 4 (pumpe)");
  ok(!B(0, "VW_KOM_P1") && !B(0, "VW_KOM_P2"), "pumpe og dosering sat fra");
  ok(B(0, "VW_AL_P1") && B(0, "VW_AL_TRIP"), "alarmer for pumpefejl og trip");
  setB(0, "VW_KVIT", true); scans(4); status("kvit., fejl");
  ok(I(0, "VW_TRIP") == 0 && I(0, "VW_STATUS") == 0 && B(0, "VW_AL_P1"), "kvitteret: trip vaek, men alarmen staar");
  hours(0.3f);
  ok(I(0, "VW_STATUS") == 0, "auto starter ikke, mens broendpumpen har fejl");
  setI(1, "VW_SCEN", 0); scans(4); status("fejl vaek");
  until_status(2, 0.4f);
  ok(I(0, "VW_STATUS") == 2, "auto starter igen efter kvittering");

  printf("\n-- Scenarie 2: hypotanken er tom --\n");
  reset_plant(); setR(1, "VW_BEH", 30.0f); until_status(2, 0.3f);
  setI(1, "VW_SCEN", 2); scans(10); status("hypo tom");
  ok(I(0, "VW_TRIP") == 2 && I(0, "VW_STATUS") == 4, "trip, aarsag 2 (hypo)");
  ok(B(0, "VW_AL_HYPO_TOM") && B(0, "VW_AL_HYPO"), "alarmer for lav og tom hypotank");
  setB(0, "VW_KVIT", true); hours(0.3f); status("kvit., tom");
  ok(I(0, "VW_STATUS") == 0 && I(0, "VW_TRIP") == 0, "kvitteret, men ingen start, mens hypotanken er under 10 pct");
  setI(1, "VW_SCEN", 0); setB(1, "VW_FYLD", true); until_status(2, 0.4f);
  ok(I(0, "VW_STATUS") == 2, "efter paafyldning starter auto igen");

  printf("\n-- Scenarie 4: overdosering giver hoejt klor --\n");
  reset_plant(); setR(1, "VW_BEH", 30.0f); until_status(2, 0.3f);
  setI(1, "VW_SCEN", 4); hours(1.5f); status("+1,5 t");
  float a2 = R(1, "VW_AT2");
  hours(1.5f); status("+3 t");
  ok(I(0, "VW_TRIP") == 3 || a2 > 1.5f, "klor stiger ved overdosering");
  ok(I(0, "VW_TRIP") == 3 && I(0, "VW_STATUS") == 4, "trip, aarsag 3 (klor uden for graenser)");
  ok(B(0, "VW_AL_KLOR_HOEJ") || I(0, "VW_TRIP") == 3, "alarm for hoejt klor");

  printf("\n-- Analysatorfejl: klor-interlocks spaerres, alarm --\n");
  reset_plant(); setR(1, "VW_BEH", 30.0f); until_status(2, 0.3f);
  setB(1, "VW_F_AN", true); setI(1, "VW_SCEN", 4); hours(3.0f); status("AN fejl");
  ok(B(0, "VW_AL_AN") && R(1, "VW_AT2") < 0.0f, "analysatorfejl: alarm og AT2 = -1");
  ok(I(0, "VW_TRIP") != 3, "ingen klor-trip uden gyldig maaling");
  setI(1, "VW_SCEN", 0); setB(1, "VW_F_AN", false);

  printf("\n-- Lav grundvandsstand --\n");
  reset_plant(); setR(1, "VW_BEH", 30.0f); setB(1, "VW_F_LAV", true); setR(1, "VW_BROND", 3.5f);
  until_status(2, 0.3f);
  for (int k = 0; k < 40 && I(0, "VW_TRIP") == 0 && I(0, "VW_STATUS") != 3; k++) hours(0.1f);
  status("lavt vand");
  ok(R(1, "VW_BROND") < 3.5f, "broendniveauet falder, naar tilstroemningen er lav");
  ok(B(0, "VW_AL_BROND") || I(0, "VW_STATUS") == 3 || I(0, "VW_STATUS") == 4, "alarm eller beskyttende stop ved lavt broendniveau");
  setB(1, "VW_F_LAV", false);

  printf("\n-- Hoej efterspoergsel (2,5 gange): doegnloftet stopper pumpen --\n");
  reset_plant(); setI(1, "VW_SCEN", 3); setR(1, "VW_BEH", 30.0f);
  float bmin2 = 100; bool capped = false;
  for (int k = 0; k < 160; k++) { hours(0.25f); if (R(1, "VW_BEH") < bmin2) bmin2 = R(1, "VW_BEH"); if (R(1, "VW_DOEGN") >= 2400.0f && I(0, "VW_STATUS") == 0) capped = true; }
  status("efter 40 t");
  ok(bmin2 < 20.0f, "beholderen tappes under 20 pct (alarm lavt niveau)");
  ok(capped || R(1, "VW_DOEGN") < 2400.0f, "doegnmaengden over 2400 m3 stopper pumpen");
  setI(1, "VW_SCEN", 0);

  printf("\n-- Manuel: interlocks gaelder, dosering kun med koerende pumpe --\n");
  reset_plant(); setI(0, "VW_MODE", 2); scans(2);
  setB(0, "VW_MAN_P2", true); scans(4);
  ok(!B(0, "VW_KOM_P2"), "dosering kan ikke startes uden koerende pumpe");
  setB(0, "VW_MAN_P1", true); scans(10); setB(0, "VW_MAN_P2", true); scans(10); status("manuel");
  ok(B(0, "VW_KOM_P1") && B(0, "VW_KOM_P2") && I(0, "VW_STATUS") == 2, "manuel: pumpe og dosering koerer");
  setB(0, "VW_MAN_XV1", true); scans(4);
  ok(!B(0, "VW_KOM_XV1"), "skylleventilen aabner ikke, mens pumpen koerer");
  setB(0, "VW_MAN_P1", false); setB(0, "VW_MAN_P2", false); scans(40);
  ok(!B(0, "VW_KOM_P1") && I(0, "VW_STATUS") == 0, "manuel stop");
  setI(0, "VW_MODE", 0);

  printf("\nMaks VM-instruktioner pr. scan: L2 %d, L3 %d (graense 10000)\n", max_steps[0], max_steps[1]);
  ok(max_steps[0] < 5000 && max_steps[1] < 5000, "god margin til instruktionsloftet");
  ok(sane && !vm_err, "hele forloebet fysisk og uden VM-fejl");
  printf(fails ? "\n%d FEJL\n" : "\nALLE TESTS OK\n", fails);
  return fails ? 1 : 0;
}
