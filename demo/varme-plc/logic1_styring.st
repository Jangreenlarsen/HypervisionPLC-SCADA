PROGRAM Styring
(* Demo-varmeanlaeg, Logic1: styringen (det en rigtig PLC ville goere).
   Laeser anlaeggets tilstand fra GLOBAL_VAR og skriver kommandoer i g_cmd.
   cmd_mode: 0 Fra, 1 Auto, 2 Sommer (kun VP), 3 Kun pille, 4 Manuel. Interval 500 ms. *)
VAR
  SMS_TXT      : STRING;
  cmd_mode     : INT := 1;
  cmd_kvitter  : BOOL;
  man_P1       : BOOL;
  man_P2       : BOOL;
  man_P3       : BOOL;
  man_P4       : BOOL;
  man_MVS      : BOOL;
  man_pille    : BOOL;
  man_VP       : BOOL;
  sp_rum       : REAL := 21.0;
  sp_kurve     : REAL := 1.0;
  sp_stf_max   : REAL := 55.0;
  sp_tank_min  : REAL := 45.0;
  sp_tank_hyst : REAL := 8.0;
  sp_vp_min    : REAL;          (* -5,0 saettes ved foerste scan: negative startvaerdier bliver 0 i firmwaren *)
  sp_sommer    : REAL := 17.0;
  SMS          : INT;
  STF_SP       : REAL;
  PS1          : BOOL;
  PS2          : BOOL;
  PS3          : BOOL;
  PS4          : BOOL;
  AL_P1        : BOOL;
  AL_P2        : BOOL;
  AL_P3        : BOOL;
  AL_P4        : BOOL;
  AL_VP        : BOOL;
  AL_PILLE     : BOOL;
  AL_TRYK_LAV  : BOOL;
  AL_TRYK_HOEJ : BOOL;
  AL_FF_TEMP   : BOOL;
  AL_TANK_KOLD : BOOL;
  ALARMER      : INT;
  kv           : BOOL;
  fb           : INT;
  cmd          : INT;
  tude         : REAL;
  t1           : REAL;
  heat         : BOOL;
  ff_akt       : BOOL;
  need         : BOOL;
  vp_ok        : BOOL;
  direct       : BOOL;
  trykstop     : BOOL;
  c_p1         : BOOL;
  c_p2         : BOOL;
  c_p3         : BOOL;
  c_p4         : BOOL;
  c_pille      : BOOL;
  c_vp         : BOOL;
  p4_hot       : BOOL;
  p2_hot       : BOOL;
  i            : INT;
  init         : BOOL;
END_VAR
BEGIN
  IF NOT init THEN sp_vp_min := -5.0; init := TRUE; END_IF;
  kv := cmd_kvitter;
  cmd_kvitter := FALSE;
  fb := g_fb;
  tude := g_tude;
  t1 := g_att1;

  (* Pumpefejl: kommanderet, men ingen tilbagemelding i 10 s -> laast til kvittering *)
  AL_P1 := SR(TON(BIT_TST(g_cmd, 0) AND NOT BIT_TST(fb, 0), T#10s), kv);
  AL_P2 := SR(TON(BIT_TST(g_cmd, 1) AND NOT BIT_TST(fb, 1), T#10s), kv);
  AL_P3 := SR(TON(BIT_TST(g_cmd, 2) AND NOT BIT_TST(fb, 2), T#10s), kv);
  AL_P4 := SR(TON(BIT_TST(g_cmd, 3) AND NOT BIT_TST(fb, 3), T#10s), kv);
  AL_VP := SR(BIT_TST(g_fault, 12), kv);   (* fejlsignal fra VP'ens egen styring *)
  AL_PILLE := SR(BIT_TST(fb, 11), kv);
  AL_TRYK_LAV := g_tryk < 1.0;
  AL_TRYK_HOEJ := g_tryk > 2.4;
  AL_FF_TEMP := g_fftf > 95.0;
  trykstop := g_tryk < 0.6;

  heat := tude < sp_sommer;
  STF_SP := LIMIT(20.0, sp_rum + sp_kurve * (sp_rum - tude), sp_stf_max);
  g_stf_sp := STF_SP;
  IF t1 < sp_tank_min THEN
    need := TRUE;
  ELSIF g_att3 >= sp_tank_min + sp_tank_hyst THEN
    need := FALSE;
  END_IF;
  vp_ok := (tude >= sp_vp_min) AND NOT AL_VP AND NOT AL_P3;
  AL_TANK_KOLD := heat AND (cmd_mode = 1) AND (t1 < 35.0) AND NOT direct;

  c_p1 := FALSE; c_p2 := FALSE; c_p3 := FALSE; c_p4 := FALSE;
  c_pille := FALSE; c_vp := FALSE;
  p4_hot := HYSTERESIS(g_fftf, 60.0, 55.0);
  p2_hot := HYSTERESIS(g_pftf, 60.0, 50.0);
  ff_akt := BIT_TST(fb, 9) OR p4_hot;   (* braende i fyret, eller det er varmt nok til Laddomat-pumpen *)

  IF cmd_mode = 4 THEN
    c_p1 := man_P1; c_p2 := man_P2; c_p3 := man_P3; c_p4 := man_P4;
    c_pille := man_pille; c_vp := man_VP; direct := man_MVS;
    SMS := 9;
  ELSIF cmd_mode = 0 THEN
    direct := FALSE;
    c_p1 := tude < 2.0;
    IF c_p1 THEN SMS := 8; ELSE SMS := 0; END_IF;
  ELSE
    c_p1 := heat AND (cmd_mode <> 2);
    IF need AND NOT ff_akt THEN
      IF cmd_mode = 3 THEN
        c_pille := TRUE;
      ELSE
        c_vp := vp_ok;
        c_pille := (cmd_mode = 1) AND ((NOT vp_ok) OR (t1 < sp_tank_min - 5.0));
      END_IF;
    END_IF;
    c_pille := c_pille AND NOT AL_PILLE;
    IF c_pille AND c_p1 AND (t1 < STF_SP - 5.0) THEN
      direct := TRUE;
    ELSIF (NOT c_pille) OR (NOT c_p1) OR (t1 >= STF_SP) THEN
      direct := FALSE;
    END_IF;
    c_p2 := p2_hot AND NOT direct;
    c_p3 := c_vp;
    IF ff_akt THEN SMS := 2;
    ELSIF direct THEN SMS := 6;
    ELSIF c_pille THEN SMS := 4;
    ELSIF c_vp THEN SMS := 3;
    ELSE SMS := 1;
    END_IF;
  END_IF;

  (* Sikkerhed: Laddomat-pumpen koerer altid naar braendefyret er varmt, P2 ved overtemp *)
  c_p4 := c_p4 OR p4_hot;
  c_p2 := c_p2 OR (g_pftf > 90.0);
  IF trykstop THEN
    c_p1 := FALSE; c_p2 := FALSE; c_p3 := FALSE; c_pille := FALSE; c_vp := FALSE;
    SMS := 10;
  END_IF;
  c_p1 := c_p1 AND NOT AL_P1;
  c_p2 := c_p2 AND NOT AL_P2;
  c_p3 := c_p3 AND NOT AL_P3;
  c_p4 := c_p4 AND NOT AL_P4;
  c_vp := c_vp AND c_p3;

  cmd := 0;
  IF c_p1 THEN cmd := BIT_SET(cmd, 0); END_IF;
  IF c_p2 THEN cmd := BIT_SET(cmd, 1); END_IF;
  IF c_p3 THEN cmd := BIT_SET(cmd, 2); END_IF;
  IF c_p4 THEN cmd := BIT_SET(cmd, 3); END_IF;
  IF direct THEN cmd := BIT_SET(cmd, 4); cmd := BIT_SET(cmd, 5); END_IF;
  IF c_pille THEN cmd := BIT_SET(cmd, 6); END_IF;
  IF c_vp THEN cmd := BIT_SET(cmd, 7); END_IF;
  g_cmd := cmd;

  (* SMS: 0 Stop, 1 Tank, 2 Braendefyr, 3 VP, 4 Pille, 6 Pille direkte, 8 Frost, 9 Manuel, 10 Trykstop *)
  i := SMS;
  IF i = 6 THEN i := 4; END_IF;   (* CASE med flere vaerdier pr. gren ("4, 6:") virker ikke i firmwaren *)
  CASE i OF
    0: SMS_TXT := 'Stop';
    1: SMS_TXT := 'Tank';
    2: SMS_TXT := 'Brændefyr';
    3: SMS_TXT := 'Varmepumpe';
    4: SMS_TXT := 'Pillefyr';
    8: SMS_TXT := 'Frostsikring';
    9: SMS_TXT := 'Manuel';
    10: SMS_TXT := 'TRYKSTOP';
  END_CASE;
  PS1 := BIT_TST(fb, 0);
  PS2 := BIT_TST(fb, 1);
  PS3 := BIT_TST(fb, 2);
  PS4 := BIT_TST(fb, 3);
  ALARMER := BOOL_TO_INT(AL_P1) + BOOL_TO_INT(AL_P2) + BOOL_TO_INT(AL_P3) + BOOL_TO_INT(AL_P4)
           + BOOL_TO_INT(AL_VP) + BOOL_TO_INT(AL_PILLE) + BOOL_TO_INT(AL_TRYK_LAV)
           + BOOL_TO_INT(AL_TRYK_HOEJ) + BOOL_TO_INT(AL_FF_TEMP) + BOOL_TO_INT(AL_TANK_KOLD);
END_PROGRAM
