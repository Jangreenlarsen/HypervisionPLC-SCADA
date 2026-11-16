// SPDX-License-Identifier: AGPL-3.0-or-later
// PC-test af test_ny_editor.st: kompilerer dem med
// HypervisionPLC's egen parser/compiler/VM (fra PLC-repoet) inkl. GLOBAL_VAR,
// koerer dem i samme raekkefoelge som PLC'en og tjekker scenarierne.
// Koeres med:  bash demo/test-ny-editor/test/run.sh
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <string>
#include "st_parser.h"
#include "st_compiler.h"
#include "st_vm.h"
#include "st_stateful.h"
#include "st_logic_config.h"
void ast_pool_free(void);
bool ast_pool_init_with_size(uint16_t max_nodes);

// Mindste AST-pulje programmet kan parses i (PLC: hoejst 512 noder, st_parser.cpp)
static int ast_nodes(const char *src) {
  int lo = 16, hi = 4096;
  auto fits = [&](int n) { ast_pool_free(); ast_pool_init_with_size(n); st_parser_t *p = (st_parser_t *)calloc(1, sizeof(st_parser_t)); st_parser_init(p, src); bool ok = st_parser_parse_program(p) != NULL; if (!ok && n == 4096) printf("PARSE: %s (linje %d)\n", p->error_msg, p->current_token.line); free(p); ast_pool_free(); return ok; };
  if (!fits(hi)) return 99999;
  while (lo < hi) { int m = (lo + hi) / 2; if (fits(m)) hi = m; else lo = m + 1; }
  return lo;
}

extern uint32_t g_fake_ms;
static int fails = 0;
static bool vm_err = false;
static int max_steps[4] = {0,0,0,0};

uint8_t st_logic_globals_lookup(st_logic_engine_state_t *s, const char *name) { return 0xFF; }

static char *slurp(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) { printf("kan ikke aabne %s\n", path); exit(2); }
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  char *b = (char *)calloc(1, n + 1); fread(b, 1, n, f); fclose(f);
  return b;
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


static st_bytecode_program_t *P;
static int vi(const char *n) {
  for (int i = 0; i < P->var_count; i++) if (!strcmp(P->var_names[i], n)) return i;
  printf("ukendt variabel %s\n", n); exit(3);
}
static float R(const char *n) { return P->variables[vi(n)].real_val; }
static int I(const char *n) { return P->variables[vi(n)].int_val; }
static bool B(const char *n) { return P->variables[vi(n)].bool_val; }
static const char *S(const char *n) { return P->string_vars[vi(n)]; }
static void setB(const char *n, bool v) { int i = vi(n); P->variables[i].dint_val = 0; P->variables[i].bool_val = v; }
static void setI(const char *n, int v) { int i = vi(n); P->variables[i].dint_val = 0; P->variables[i].int_val = v; }
static void ok(bool c, const char *m) { printf("%s %s\n", c ? "PASS" : "FAIL", m); if (!c) fails++; }
static void scans(int n) { for (int k = 0; k < n; k++) { g_fake_ms += 500; run(0, P); } }
static void line(const char *t) {
  printf("  %-9s trin %d | cmd P%d V%d%d%d MV%d L%d | fb P%d V%d%d%d | %d %-8s alarm %d | temp %5.1f tryk %4.2f%s niv %5.1f flow %5.1f\n",
    t, I("TNE_TRIN"), B("TNE_CMD_PUMPE"), B("TNE_CMD_V1"), B("TNE_CMD_V2"), B("TNE_CMD_V3"), B("TNE_CMD_MV"), B("TNE_CMD_LAMPE"),
    B("TNE_FB_PUMPE"), B("TNE_FB_V1"), B("TNE_FB_V2"), B("TNE_FB_V3"), I("TNE_STATUS"), S("TNE_TXT"), B("TNE_ALARM"),
    R("TNE_TEMP"), R("TNE_TRYK"), B("TNE_TRYK_HOEJ") ? "!" : " ", R("TNE_NIVEAU"), R("TNE_FLOW"));
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "demo/test-ny-editor/test_ny_editor.st";
  P = compile(path);
  if (!P) return 1;
  printf("\n-- Auto: et helt forloeb (9 trin x 10 s) --\n");
  scans(1);
  ok(B("TNE_AUTO"), "auto er til fra start");
  int seen_alarm = 0, seen_tryk = 0, flow_ok = 0; bool steps[9] = {};
  for (int s = 1; s <= 100; s++) {
    scans(2);
    steps[I("TNE_TRIN")] = true;
    if (B("TNE_ALARM")) seen_alarm++;
    if (B("TNE_TRYK_HOEJ")) seen_tryk++;
    if (B("TNE_FB_PUMPE") && R("TNE_FLOW") > 45.0f) flow_ok++;
    if (s % 5 == 0) line((std::string("t=") + std::to_string(s) + "s").c_str());
  }
  bool all = true; for (int i = 0; i < 9; i++) all = all && steps[i];
  ok(all, "alle 9 trin er kommet forbi");
  ok(seen_alarm > 0, "pumpealarmen kommer i fejltrinnet");
  ok(seen_tryk > 0, "hoejt tryk giver TNE_TRYK_HOEJ");
  ok(flow_ok > 20, "flow, naar pumpen koerer");
  ok(!vm_err, "ingen VM-fejl");
  ok(I("TNE_TRIN") == 0 && !B("TNE_ALARM"), "alarmen er kvitteret igen i trin 0 (auto)");

  printf("\n-- Manuel: auto fra, pumpe start/stop og fejl --\n");
  setB("TNE_AUTO", false);
  setB("TNE_CMD_PUMPE", false); setB("TNE_CMD_V1", false); setB("TNE_CMD_V2", false); setB("TNE_CMD_V3", false);
  scans(8);
  ok(I("TNE_STATUS") == 0 && !strcmp(S("TNE_TXT"), "Stop"), "stop: status 0 Stop");
  setB("TNE_CMD_PUMPE", true); scans(1);
  ok(I("TNE_STATUS") == 1 && !strcmp(S("TNE_TXT"), "Starter"), "kommando uden tilbagemelding: status 1 Starter");
  scans(6);
  ok(I("TNE_STATUS") == 2 && B("TNE_FB_PUMPE"), "efter 2 s: status 2 Koerer");
  setB("TNE_CMD_V1", true); scans(1);
  ok(!B("TNE_FB_V1"), "V1: staar i A de foerste 2 s (gangtid)");
  scans(6);
  ok(B("TNE_FB_V1"), "V1: i B efter gangtiden");
  setB("TNE_CMD_V1", false); scans(1);
  ok(B("TNE_FB_V1"), "V1: bliver i B under gangtiden tilbage");
  scans(6);
  ok(!B("TNE_FB_V1"), "V1: tilbage i A");
  setB("TNE_CMD_PUMPE", false); scans(1);
  ok(I("TNE_STATUS") == 0 || I("TNE_STATUS") == 4, "pumpe stoppet");
  setB("TNE_FEJL", true); setB("TNE_CMD_PUMPE", true); scans(12);
  ok(B("TNE_ALARM") && I("TNE_STATUS") == 3 && !strcmp(S("TNE_TXT"), "Fejl"), "fejlinjektion: ingen tilbagemelding -> alarm, status 3 Fejl");
  setB("TNE_FEJL", false); scans(6);          // fejlen fjernes; pumpen er tilbage efter 2 s
  setB("TNE_KVIT", true); scans(4);
  ok(!B("TNE_ALARM") && B("TNE_FB_PUMPE") && I("TNE_STATUS") == 2, "fejlen er vaek, pumpen koerer igen: kvittering virker");
  line("manuel");
  printf("\n%d fejl, max %d VM-trin pr. scan (graense 10000)\n", fails, max_steps[0]);
  return fails ? 1 : 0;
}
