PROGRAM Styring
(* Demo-varmeanlaeg, Logic1: styringen (det en rigtig PLC ville goere).
   Laeser anlaeggets tilstand fra GLOBAL_VAR og skriver kommandoer i g_cmd.
   cmd_mode: 0 Auto, 1 Manuel mode 1, 2 Manuel mode 2, 3 Manuel mode 3.
   MODE 1 Hus + pille (M1 AB-A, M2 AB-A, P1) - 2 Hus + pille + tank (M1 AB-A, M2 AB-B, P1)
   - 3 Hus + tank (M1 AB-B, M2 AB-B, P2). Auto: tanken ind (mode 3) ved ATT1 >= sp_tank_ind,
   ud (mode 1) under sp_tank_ud. Varmepumpen startes manuelt (cmd_vp). Interval 500 ms. *)
VAR
  SMS_TXT      : STRING;
  cmd_mode     : INT;
  cmd_kvitter  : BOOL;
  cmd_vp       : BOOL;
  sp_rum       : REAL := 21.0;
  sp_kurve     : REAL := 1.0;
  sp_stf_max   : REAL := 55.0;
  sp_tank_ind  : REAL := 60.0;
  sp_tank_ud   : REAL := 45.0;
  sp_vp_min    : REAL;          (* -5,0 saettes ved foerste scan: negative startvaerdier bliver 0 i firmwaren *)
  MODE         : INT := 1;
  SMS          : INT;
  STF_SP       : REAL;
  TANK_IND     : BOOL;
  PS1          : BOOL;
  PS2          : BOOL;
  PS3          : BOOL;
  PS4          : BOOL;
  F_HUS        : BOOL;
  F_PILLE      : BOOL;
  F_TANK       : BOOL;
  F_BYPASS     : BOOL;
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
  trykstop     : BOOL;
  c_p1         : BOOL;
  c_p2         : BOOL;
  c_p3         : BOOL;
  c_p4         : BOOL;
  c_pille      : BOOL;
  c_vp         : BOOL;
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

  STF_SP := LIMIT(20.0, sp_rum + sp_kurve * (sp_rum - tude), sp_stf_max);
  g_stf_sp := STF_SP;

  (* Tanken i kredsen (Auto): ind ved sp_tank_ind, ud under sp_tank_ud *)
  IF t1 >= sp_tank_ind THEN
    TANK_IND := TRUE;
  ELSIF t1 < sp_tank_ud THEN
    TANK_IND := FALSE;
  END_IF;
  IF cmd_mode = 0 THEN
    IF TANK_IND THEN MODE := 3; ELSE MODE := 1; END_IF;
  ELSE
    MODE := LIMIT(1, cmd_mode, 3);
  END_IF;
  AL_TANK_KOLD := (cmd_mode = 3) AND (t1 < STF_SP - 5.0);

  c_p1 := MODE < 3;                 (* P1 i pillefyrets sloejfe: mode 1 og 2 *)
  c_p2 := MODE = 3;                 (* P2 fra tanken: mode 3 *)
  c_pille := c_p1 AND NOT AL_PILLE;
  c_vp := cmd_vp AND (tude >= sp_vp_min) AND NOT AL_VP AND NOT AL_P3;
  c_p3 := c_vp;
  c_p4 := HYSTERESIS(g_fftf, 60.0, 55.0);   (* Laddomat-pumpen koerer altid naar braendefyret er varmt *)

  SMS := MODE;
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
  IF MODE = 3 THEN cmd := BIT_SET(cmd, 4); END_IF;    (* MVS1 AB-B *)
  IF MODE >= 2 THEN cmd := BIT_SET(cmd, 5); END_IF;   (* MVS2 AB-B *)
  IF c_pille THEN cmd := BIT_SET(cmd, 6); END_IF;
  IF c_vp THEN cmd := BIT_SET(cmd, 7); END_IF;
  g_cmd := cmd;

  (* SMS: 1-3 mode, 10 trykstop *)
  CASE SMS OF
    1: SMS_TXT := 'Hus + pille';
    2: SMS_TXT := 'Hus + pille + tank';
    3: SMS_TXT := 'Hus + tank';
    10: SMS_TXT := 'TRYKSTOP';
  END_CASE;
  PS1 := BIT_TST(fb, 0);
  PS2 := BIT_TST(fb, 1);
  PS3 := BIT_TST(fb, 2);
  PS4 := BIT_TST(fb, 3);
  (* Kredsdele med flow (roerene paa tegningen) *)
  F_HUS := PS1 OR PS2;
  F_PILLE := PS1;
  F_TANK := F_HUS AND (MODE >= 2);
  F_BYPASS := PS1 AND (MODE = 1);
  ALARMER := BOOL_TO_INT(AL_P1) + BOOL_TO_INT(AL_P2) + BOOL_TO_INT(AL_P3) + BOOL_TO_INT(AL_P4)
           + BOOL_TO_INT(AL_VP) + BOOL_TO_INT(AL_PILLE) + BOOL_TO_INT(AL_TRYK_LAV)
           + BOOL_TO_INT(AL_TRYK_HOEJ) + BOOL_TO_INT(AL_FF_TEMP) + BOOL_TO_INT(AL_TANK_KOLD);
END_PROGRAM
