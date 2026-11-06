PROGRAM TankHus
(* Demo-varmeanlaeg, Logic3: akkumuleringstank i 6 lag (750 L), husets
   varmekreds med AVTB-blandeventil og P1, motorventiler MVS1/MVS2
   (30 s gangtid i realtid). Interval 500 ms. *)
VAR
  MVS1_TXT : STRING;
  MVS2_TXT : STRING;
  T        : ARRAY[1..6] OF REAL;
  ATT1     : REAL;
  ATT2     : REAL;
  ATT3     : REAL;
  ATT4     : REAL;
  ATT5     : REAL;
  ATT6     : REAL;
  ATF      : REAL;
  TS       : REAL;
  E_TANK   : REAL;
  STF      : REAL := 30.0;
  STR      : REAL := 30.0;
  MVT2     : REAL := 30.0;
  FMTR     : REAL;
  T_RUM    : REAL := 21.0;
  Q_HUS    : REAL;
  E_HUS    : REAL;
  MVS1_POS : REAL;
  MVS2_POS : REAL;
  cmd_mvs1 : INT;
  cmd_mvs2 : INT;
  init     : BOOL;
  w        : BOOL;
  i        : INT;
  dt       : REAL;
  k        : REAL;
  m_h      : REAL;
  m_ht     : REAL;
  m_ch     : REAL;
  net      : REAL;
  up       : REAL;
  down     : REAL;
  prev     : REAL;
  old      : REAL;
  avg      : REAL;
  frac     : REAL;
  tsrc     : REAL;
  sum      : REAL;
  tch      : REAL;
  tin      : REAL;
END_VAR
BEGIN
  IF NOT init THEN
    FOR i := 1 TO 6 DO T[i] := 52.0 - 3.0 * INT_TO_REAL(i); END_FOR;
    init := TRUE;
  END_IF;
  dt := 0.5 * MAX(g_speed, 1.0);

  (* Motorventiler: ON = AB-B, OFF = AB-A. MVS1 AB-B = P2-grenen (uden om pillefyret), MVS2 AB-B = tanken i kredsen *)
  (* Haandbetjening paa motoren: cmd_mvsN 0 = Auto (styringen), 1 = AB-A, 2 = AB-B *)
  w := BIT_TST(g_cmd, 4);
  IF cmd_mvs1 = 1 THEN w := FALSE; ELSIF cmd_mvs1 = 2 THEN w := TRUE; END_IF;
  IF w THEN MVS1_POS := MIN(100.0, MVS1_POS + 1.667); ELSE MVS1_POS := MAX(0.0, MVS1_POS - 1.667); END_IF;
  w := BIT_TST(g_cmd, 5);
  IF cmd_mvs2 = 1 THEN w := FALSE; ELSIF cmd_mvs2 = 2 THEN w := TRUE; END_IF;
  IF w THEN MVS2_POS := MIN(100.0, MVS2_POS + 1.667); ELSE MVS2_POS := MAX(0.0, MVS2_POS - 1.667); END_IF;
  IF MVS1_POS >= 100.0 THEN MVS1_TXT := 'AB-B'; ELSIF MVS1_POS <= 0.0 THEN MVS1_TXT := 'AB-A'; ELSE MVS1_TXT := 'Kører'; END_IF;
  IF MVS2_POS >= 100.0 THEN MVS2_TXT := 'AB-B'; ELSIF MVS2_POS <= 0.0 THEN MVS2_TXT := 'AB-A'; ELSE MVS2_TXT := 'Kører'; END_IF;

  (* Husets kreds: P1 eller P2 = 15 L/min. M2: retur direkte (AB-A) eller gennem tanken (AB-B);
     M1: gennem pillefyret (AB-A) eller uden om (AB-B). AVTB blander ned til fremloebssetpunktet *)
  m_h := 0.0;
  IF BIT_TST(g_fb, 0) OR BIT_TST(g_fb, 1) THEN m_h := 0.25; END_IF;
  tin := SEL(MVS2_POS > 50.0, STR, T[1]);
  g_str := tin;   (* pillefyrets indloeb *)
  tsrc := SEL(MVS1_POS > 50.0, g_pftf, tin);
  frac := 1.0;
  IF tsrc > STR + 0.5 THEN frac := LIMIT(0.0, (g_stf_sp - STR) / (tsrc - STR), 1.0); END_IF;
  IF m_h > 0.0 THEN
    STF := STR + frac * (tsrc - STR);
    Q_HUS := MAX(0.0, 0.285 * (STF - T_RUM) / (1.0 + 0.285 / (2.0 * m_h * 4.186)));
    STR := STF - Q_HUS / (m_h * 4.186);
  ELSE
    Q_HUS := 0.0;
    STF := STF + (T_RUM - STF) * MIN(1.0, dt / 1200.0);
    STR := STR + (T_RUM - STR) * MIN(1.0, dt / 1200.0);
  END_IF;
  T_RUM := T_RUM + (Q_HUS + 0.4 - 0.25 * (T_RUM - g_tude)) * dt / 15000.0;
  FMTR := m_h * 60.0;
  MVT2 := STR;
  E_HUS := E_HUS + Q_HUS * dt / 3600.0;
  m_ht := 0.0;
  IF MVS2_POS > 50.0 THEN m_ht := m_h * frac; END_IF;   (* gennem tanken: retur i bunden, ud i toppen *)

  (* Tank: ladning i toppen fra kilderne, husets retur i bunden, lagdelt strømning *)
  m_ch := g_mch;
  IF BIT_TST(g_fb, 2) THEN   (* varmepumpen (P3) lader fra bund til top *)
    m_ch := m_ch + 0.3;
    tch := (g_mch * g_tch + 0.3 * g_vptf) / m_ch;
  ELSE
    tch := g_tch;
  END_IF;
  net := m_ch - m_ht;
  down := MAX(net, 0.0);
  up := MAX(0.0 - net, 0.0);
  k := dt / 125.0;
  prev := T[1];
  T[1] := T[1] + (m_ch * (tch - T[1]) + up * (T[2] - T[1])) * k;
  FOR i := 2 TO 5 DO
    old := T[i];
    T[i] := T[i] + (down * (prev - T[i]) + up * (T[i + 1] - T[i])) * k;
    prev := old;
  END_FOR;
  T[6] := T[6] + (down * (prev - T[6]) + m_ht * (STR - T[6])) * k;
  sum := 0.0;
  FOR i := 1 TO 6 DO
    T[i] := T[i] - 0.002 * (T[i] - 20.0) * dt / 523.0;
    sum := sum + T[i];
  END_FOR;
  FOR i := 1 TO 5 DO
    IF T[i + 1] > T[i] THEN
      avg := (T[i] + T[i + 1]) / 2.0;
      T[i] := avg;
      T[i + 1] := avg;
    END_IF;
  END_FOR;

  ATT1 := T[1]; ATT2 := T[2]; ATT3 := T[3]; ATT4 := T[4]; ATT5 := T[5]; ATT6 := T[6];
  ATF := T[1];
  E_TANK := 0.14535 * (sum - 180.0);
  TS := LIMIT(0.0, (sum / 6.0 - 30.0) * 2.0, 100.0);
  g_att1 := T[1];
  g_att3 := T[3];
  g_att6 := T[6];
END_PROGRAM
