// SPDX-License-Identifier: AGPL-3.0-or-later
// PC-test af demo-varmeanlaeggets fire ST-programmer: kompilerer dem med
// HypervisionPLC's egen parser/compiler/VM (fra PLC-repoet) inkl. GLOBAL_VAR,
// koerer dem i samme raekkefoelge som PLC'en og tjekker scenarierne.
// Koeres med:  bash demo/varme-plc/test/run.sh
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

// Mindste AST-pulje programmet kan parses i (PLC: hoejst 512 noder, st_parser.cpp)
static int ast_nodes(const char *src) {
  int lo = 16, hi = 512;
  auto fits = [&](int n) { ast_pool_free(); ast_pool_init_with_size(n); st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t)); st_parser_init(p, src); bool ok = st_parser_parse_program(p) != NULL; free(p); ast_pool_free(); return ok; };
  if (!fits(hi)) return 9999;
  while (lo < hi) { int m = (lo + hi) / 2; if (fits(m)) hi = m; else lo = m + 1; }
  return lo;
}

extern uint32_t g_fake_ms;
static int fails = 0;
static int max_steps[4] = {0, 0, 0, 0};
static bool vm_err = false;

// Rigtigt opslag af GLOBAL_VAR (host_stubs' version er omdoebt ved kompilering)
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
  printf("%-28s AST-noder %4d / 512\n", strrchr(path, '/') + 1, nodes);
  if (nodes > 512) { printf("FAIL for mange AST-noder\n"); fails++; return NULL; }
  st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t));
  st_parser_init(p, src);
  st_program_t *prog = st_parser_parse_program(p);
  if (!prog) { printf("PARSE FEJL i %s: %s (linje %d)\n", path, p->error_msg, p->current_token.line); exit(1); }
  st_compiler_t *c = (st_compiler_t *)calloc(1, sizeof(st_compiler_t));
  st_compiler_init(c);
  st_bytecode_program_t *bc = (st_bytecode_program_t *)calloc(1, sizeof(st_bytecode_program_t));
  if (!st_compiler_compile(c, prog, bc)) { printf("COMPILE FEJL i %s: %s\n", path, c->error_msg); exit(1); }
  ast_pool_free();   // som st_logic_compile_monolithic paa PLC'en
  printf("%-28s %5d bytes, %3d instruktioner, %2d variable\n", strrchr(path, '/') + 1, (int)strlen(src), bc->instr_count, bc->var_count);
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
    if (!vm_err) printf("FAIL VM-fejl i Logic%d: %s (steps %d)\n", id + 1, vm->error_msg, steps);
    vm_err = true;
  } else {
    memcpy(bc->variables, vm->variables, vm->var_count * sizeof(st_value_t));
    memcpy(bc->string_vars, vm->string_vars, sizeof(bc->string_vars));
  }
  free(vm);
}

static st_bytecode_program_t *P[4];
static int vi(st_bytecode_program_t *bc, const char *n) {
  for (int i = 0; i < bc->var_count; i++) if (!strcmp(bc->var_names[i], n)) return i;
  printf("ukendt variabel %s\n", n); exit(3);
}
static float R(int p, const char *n) { return P[p]->variables[vi(P[p], n)].real_val; }
static int I(int p, const char *n) { return P[p]->variables[vi(P[p], n)].int_val; }
static bool B(int p, const char *n) { return P[p]->variables[vi(P[p], n)].bool_val; }
static const char *S(int p, const char *n) { return P[p]->string_vars[vi(P[p], n)]; }
static void setR(int p, const char *n, float v) { P[p]->variables[vi(P[p], n)].real_val = v; }
static void setI(int p, const char *n, int v) { int i = vi(P[p], n); P[p]->variables[i].dint_val = 0; P[p]->variables[i].int_val = v; }
static void setB(int p, const char *n, bool v) { int i = vi(P[p], n); P[p]->variables[i].dint_val = 0; P[p]->variables[i].bool_val = v; }
static void ok(bool c, const char *m) { printf("%s %s\n", c ? "PASS" : "FAIL", m); if (!c) fails++; }

static bool sane = true;
static void check_ranges() {
  const char *t2[] = {"FFTF", "PFTF", "FFTR", "PFTR"};
  for (const char *n : t2) { float v = R(1, n); if (!(v >= 0 && v <= 112.5)) { if (sane) printf("   uden for omraade: %s=%.1f\n", n, v); sane = false; } }
  const char *t3[] = {"ATT1", "ATT2", "ATT3", "ATT4", "ATT5", "ATT6", "STF", "STR", "T_RUM"};
  for (const char *n : t3) { float v = R(2, n); if (!(v >= -20 && v <= 112.5)) { if (sane) printf("   uden for omraade: %s=%.1f\n", n, v); sane = false; } }
  float p = R(3, "ST"); if (!(p >= 0 && p <= 4.0)) { if (sane) printf("   tryk uden for omraade: %.2f\n", p); sane = false; }
}

// Koer n scans (500 ms hver). Logic1-4 i raekkefoelge, som PLC'en.
static void scans(int n) {
  for (int k = 0; k < n; k++) {
    g_fake_ms += 500;
    for (int i = 0; i < 4; i++) run(i, P[i]);
    check_ranges();
  }
}
static void hours(float h) { scans((int)(h * 3600.0f / (0.5f * R(3, "sp_speed")))); }

static void status(const char *t) {
  printf("   [%-14s] kl %5.2f ude %5.1f | tank %4.1f/%4.1f/%4.1f TS %3.0f%% | FF %5.1f %s | pille %5.1f %s | VP %4.1f %4.1fkW | STF %4.1f STR %4.1f rum %4.1f | %4.2f bar | %s (%d) | MVS1 %s | alarmer %d\n",
         t, R(3, "KLOKKE"), R(3, "T_UDE"), R(2, "ATT1"), R(2, "ATT3"), R(2, "ATT6"), R(2, "TS"),
         R(1, "FFTF"), S(3, "FFS_TXT"), R(1, "PFTF"), S(1, "PILLE_TXT"), R(3, "VPTF"), R(3, "VP_KW"),
         R(2, "STF"), R(2, "STR"), R(2, "T_RUM"), R(3, "ST"), S(0, "SMS_TXT"), I(0, "SMS"), S(2, "MVS1_TXT"), I(0, "ALARMER"));
}

int main(int argc, char **argv) {
  const char *dir = argc > 1 ? argv[1] : "demo/varme-plc";
  char path[512];
  snprintf(path, sizeof path, "%s/globals.st", dir); load_globals(slurp(path));
  const char *files[4] = {"logic1_styring.st", "logic2_kilder.st", "logic3_tank_hus.st", "logic4_system.st"};
  for (int i = 0; i < 4; i++) { snprintf(path, sizeof path, "%s/%s", dir, files[i]); P[i] = compile(path); }
  for (int i = 0; i < 4; i++) if (!P[i]) { printf("\n%d FEJL\n", fails); return 1; }

  setR(3, "sp_speed", 60.0f);
  scans(1);
  ok(fabsf(R(0, "sp_vp_min") + 5.0f) < 0.01f, "sp_vp_min = -5 efter foerste scan");

  auto tank = [](float t) { for (int i = 1; i <= 6; i++) P[2]->variables[vi(P[2], "T[1]") + i - 1].real_val = t; };
  auto valves = [](const char *m1, const char *m2) { return !strcmp(S(2, "MVS1_TXT"), m1) && !strcmp(S(2, "MVS2_TXT"), m2); };
  float tmax = 0;

  printf("\n-- Auto, tank lunken: mode 1 (hus + pille), et doegn x60 --\n");
  for (int h = 0; h < 24; h += 6) { hours(6); status("auto"); }
  ok(!vm_err, "ingen VM-fejl");
  ok(sane, "temperaturer og tryk holder sig fysisk");
  ok(I(0, "MODE") == 1 && !strcmp(S(0, "SMS_TXT"), "Hus + pille"), "Auto: mode 1 naar tanken er under Tank ind");
  ok(valves("AB-A", "AB-A") && B(0, "PS1") && !B(0, "PS2"), "mode 1: M1 AB-A, M2 AB-A, P1 koerer, P2 staar");
  ok(B(0, "F_PILLE") && B(0, "F_BYPASS") && !B(0, "F_TANK"), "mode 1: flow i pillesloejfen og uden om tanken");
  ok(fabsf(R(2, "T_RUM") - 21.0f) < 1.5f, "rumtemperatur ca. 21 C fra pillefyret");
  ok(R(1, "E_PILLE") > 5.0f, "pillefyret har leveret varmen");
  ok(I(0, "ALARMER") == 0, "ingen alarmer i normal drift");
  ok(!B(3, "VP_RUN"), "varmepumpen staar, til den startes manuelt");

  printf("\n-- Varmepumpe startet manuelt: lader tanken, Auto kobler tanken ind (mode 3) --\n");
  setB(0, "cmd_vp", true);
  for (int k = 0; k < 48 && I(0, "MODE") != 3; k++) { hours(0.5); if (R(2, "ATT1") > tmax) tmax = R(2, "ATT1"); }
  status("tank ind");
  ok(B(0, "TANK_IND") && I(0, "MODE") == 3, "tanken kobles ind ved Tank ind (60 C)");
  ok(R(3, "E_VP") > 1.0f, "varmepumpen har leveret energi");
  scans(70); status("+35 s");
  ok(valves("AB-B", "AB-B") && B(0, "PS2") && !B(0, "PS1") && !strcmp(S(0, "SMS_TXT"), "Hus + tank"),
     "mode 3: M1 AB-B, M2 AB-B, P2 koerer, P1 staar");
  ok(B(0, "F_TANK") && !B(0, "F_PILLE"), "mode 3: flow gennem tanken, ikke pillefyret");
  for (int k = 0; k < 12; k++) { hours(0.5); if (R(2, "ATT1") > tmax) tmax = R(2, "ATT1"); }
  status("VP fuld");
  ok(tmax <= 66.0f, "varmepumpen lader hoejst til ca. 65 C");
  ok(R(1, "PILLE_KW") == 0.0f && fabsf(R(2, "T_RUM") - 21.0f) < 1.5f, "huset forsynes fra tanken, pillefyret staar");

  printf("\n-- VP stoppet: tanken aflades, Auto kobler den ud under Tank ud (45 C) --\n");
  setB(0, "cmd_vp", false);
  int g = 0;
  while (I(0, "MODE") != 1 && g++ < 200) hours(0.25);
  status("tank ud");
  ok(I(0, "MODE") == 1 && R(2, "ATT1") < 45.5f, "tanken kobles ud igen, mode 1");
  scans(70);
  ok(valves("AB-A", "AB-A") && B(0, "PS1"), "ventilerne tilbage i AB-A, P1 koerer");

  printf("\n-- Fyr op i braendefyret: lader tanken til over 80 C --\n");
  setB(1, "cmd_fyr_op", true); scans(2); setB(1, "cmd_fyr_op", true);
  tmax = 0;
  bool p4 = false;
  for (int k = 0; k < 16; k++) { hours(0.5); if (R(2, "ATT1") > tmax) tmax = R(2, "ATT1"); p4 = p4 || B(0, "PS4"); }
  status("+8 t");
  ok(p4, "Laddomat-pumpen P4 har koert");
  ok(tmax > 80.0f, "braendefyret lader tanken over 80 C (VP kan kun 65)");
  ok(I(0, "MODE") == 3, "Auto har koblet tanken ind");
  hours(12); status("+20 t");
  ok(strcmp(S(3, "FFS_TXT"), "Slukket") == 0, "braendet er braendt ud igen");

  printf("\n-- Manuel mode 2: hus + pille + tank --\n");
  setI(0, "cmd_mode", 2); tank(40.0f);
  scans(70); status("mode 2");
  ok(valves("AB-A", "AB-B") && B(0, "PS1") && !B(0, "PS2") && !strcmp(S(0, "SMS_TXT"), "Hus + pille + tank"),
     "mode 2: M1 AB-A, M2 AB-B, P1 koerer, P2 staar");
  ok(B(0, "F_PILLE") && B(0, "F_TANK") && !B(0, "F_BYPASS"), "mode 2: flow gennem tanken og pillefyret");
  hours(2); status("+2 t");
  ok(fabsf(R(2, "T_RUM") - 21.0f) < 1.5f, "pillefyret holder huset med tanken i kredsen");
  setI(0, "cmd_mode", 3); scans(70);
  ok(valves("AB-B", "AB-B") && B(0, "PS2") && !B(0, "PS1"), "manuel mode 3");
  setI(0, "cmd_mode", 1); scans(70);
  ok(valves("AB-A", "AB-A") && B(0, "PS1") && !B(0, "PS2"), "manuel mode 1");

  printf("\n-- Haandbetjening af motorventilerne --\n");
  setI(2, "cmd_mvs1", 2); scans(70);
  ok(valves("AB-B", "AB-A"), "haandbetjening: MVS1 koert til AB-B, MVS2 foelger styringen");
  setI(2, "cmd_mvs1", 0); setI(2, "cmd_mvs2", 2); scans(70);
  ok(valves("AB-A", "AB-B"), "haandbetjening: MVS2 AB-B, MVS1 tilbage paa Auto");
  setI(2, "cmd_mvs2", 0); scans(70);
  setI(0, "cmd_mode", 0);

  printf("\n-- Vinternat (-15..-9 C): VP blokeret, pillefyr --\n");
  setI(3, "cmd_scenarie", 1); setB(0, "cmd_vp", true); tank(40.0f);
  for (int h = 0; h < 12; h += 3) { hours(3); status("vinter"); }
  ok(!B(3, "VP_RUN"), "VP koerer ikke under sp_vp_min");
  ok(R(2, "T_RUM") > 19.0f, "huset holdes over 19 C af pillefyret");
  ok(I(0, "ALARMER") == 0, "ingen alarmer i vinternat");
  setB(0, "cmd_vp", false); setI(3, "cmd_scenarie", 0);
  hours(6); status("normal igen");

  printf("\n-- Laekage: trykket falder --\n");
  setI(3, "cmd_scenarie", 3);
  float t0 = 0; int guard = 0;
  while (!B(0, "AL_TRYK_LAV") && guard++ < 20000) scans(1);
  t0 = guard * 0.5f; status("tryk lavt");
  ok(B(0, "AL_TRYK_LAV"), "alarm for lavt tryk");
  while (I(0, "SMS") != 10 && guard++ < 40000) scans(1);
  scans(2); status("trykstop");
  ok(I(0, "SMS") == 10 && !B(0, "PS1") && !B(0, "PS2"), "trykstop stopper pumperne");
  setI(3, "cmd_scenarie", 0);
  setB(3, "cmd_efterfyld", true);
  scans(4); status("efterfyldt");
  ok(!B(0, "AL_TRYK_LAV") && I(0, "SMS") != 10, "efterfyldning genopretter trykket");
  printf("   (lavt tryk efter %.0f s realtid ved x60)\n", t0);

  printf("\n-- Pumpefejl P1 + kvittering (mode 1) --\n");
  setI(0, "cmd_mode", 1);
  setI(3, "cmd_scenarie", 4);
  scans(30); status("P1 fejl");
  ok(B(0, "AL_P1") && !B(0, "PS1"), "AL_P1 efter 10 s, P1 staar");
  setI(3, "cmd_scenarie", 0);
  scans(4);
  ok(B(0, "AL_P1"), "alarmen er laast til kvittering");
  setB(0, "cmd_kvitter", true); scans(4);
  ok(!B(0, "AL_P1") && B(0, "PS1"), "kvittering nulstiller, P1 koerer igen");

  printf("\n-- Overophedning: P4 i fejl mens braendefyret braender --\n");
  setI(0, "cmd_mode", 0);   /* Auto: tanken kobles ind og aflades igen */
  setB(3, "f_P4", true);
  setB(1, "cmd_fyr_op", true); scans(2);
  setB(1, "cmd_fyr_op", true);
  bool sv = false, ovt = false;
  for (int k = 0; k < 600 && !sv; k++) { scans(10); sv = sv || B(3, "SV_AABEN"); ovt = ovt || B(0, "AL_FF_TEMP"); }
  status("overtemp");
  ok(ovt, "alarm for overtemperatur i braendefyret");
  ok(sv, "sikkerhedsventilen aabner");
  ok(B(0, "AL_P4"), "pumpefejl P4 alarmeret");
  setB(3, "f_P4", false); setB(0, "cmd_kvitter", true);
  hours(6); setB(3, "cmd_efterfyld", true); scans(4); status("koelet ned");
  ok(!B(3, "SV_AABEN") && R(1, "FFTF") < 95.0f, "fyret koeler ned efter fejlen er vaek");

  printf("\n-- Pillefyr taender ikke (mode 1) --\n");
  setI(0, "cmd_mode", 1); setI(1, "PILLE_ST", 0);   /* fyret starter forfra */
  setB(3, "f_pille", true); setB(0, "cmd_kvitter", true); scans(2);
  hours(1); status("pillefejl");
  ok(B(0, "AL_PILLE"), "alarm for pillefyr-taendingsfejl");
  setB(3, "f_pille", false); setB(0, "cmd_kvitter", true); hours(1); status("efter kvit.");
  ok(!B(0, "AL_PILLE"), "kvitteret, pillefyret starter igen");

  printf("\n-- Varmepumpefejl --\n");
  setB(0, "cmd_vp", true); setB(3, "f_vp", true);
  scans(20); status("VP fejl");
  ok(B(0, "AL_VP") && !B(3, "VP_RUN"), "alarm for varmepumpefejl, VP staar");
  setB(3, "f_vp", false); setB(0, "cmd_kvitter", true); scans(4);
  ok(!B(0, "AL_VP"), "kvitteret");
  setB(0, "cmd_vp", false); setI(0, "cmd_mode", 0);

  printf("\nMaks VM-instruktioner pr. scan: L1 %d, L2 %d, L3 %d, L4 %d (graense 10000)\n", max_steps[0], max_steps[1], max_steps[2], max_steps[3]);
  ok(max_steps[0] < 5000 && max_steps[1] < 5000 && max_steps[2] < 5000 && max_steps[3] < 5000, "god margin til instruktionsloftet");
  ok(sane && !vm_err, "hele forloebet fysisk og uden VM-fejl");
  printf(fails ? "\n%d FEJL\n" : "\nALLE TESTS OK\n", fails);
  return fails ? 1 : 0;
}
