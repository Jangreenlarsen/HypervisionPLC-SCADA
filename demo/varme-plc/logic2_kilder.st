PROGRAM Kilder
(* Demo-varmeanlaeg, Logic2: procesmodel for braendefyr (+ Laddomat/P4) og
   pillefyr (P2); varmepumpen og braendefyrets statustekst ligger i Logic4. Leverer ladeflow/-temp til tanken
   (g_mch/g_tch) og tilbagemeldinger i g_fb. Interval 500 ms. *)
VAR
  PILLE_TXT  : STRING;
  cmd_fyr_op : BOOL;
  sp_pille   : REAL := 75.0;
  FFTF       : REAL := 20.0;
  FFTR       : REAL := 20.0;
  FF_KW      : REAL;
  FF_KG      : REAL;
  LADDOMAT   : BOOL;
  PFTF       : REAL := 20.0;
  PFTR       : REAL := 20.0;
  PILLE_KW   : REAL;
  PILLE_KG   : REAL;
  PILLE_ST   : INT;
  PILLE_STARTS : DINT;
  E_FF       : REAL;
  E_PILLE    : REAL;
  dt         : REAL;
  cmd        : INT;
  flt        : INT;
  fb         : INT;
  r_p1       : BOOL;
  r_p2       : BOOL;
  r_p4       : BOOL;
  direct     : BOOL;
  ff_q       : REAL;
  ff_mt      : REAL;
  psp        : REAL;
  ps_t       : REAL;
  p_q        : REAL;
  pm         : REAL;
  pret       : REAL;
  m_ch       : REAL;
  e_ch       : REAL;
  en         : BOOL;
END_VAR
BEGIN
  dt := 0.5 * MAX(g_speed, 1.0);
  cmd := g_cmd;
  flt := g_fault;
  (* pumper der faktisk koerer: kommanderet og ikke i fejl *)
  r_p1 := BIT_TST(cmd, 0) AND NOT BIT_TST(flt, 0);
  r_p2 := BIT_TST(cmd, 1) AND NOT BIT_TST(flt, 1);
  r_p4 := BIT_TST(cmd, 3) AND NOT BIT_TST(flt, 3);
  fb := 0;
  IF r_p1 THEN fb := BIT_SET(fb, 0); END_IF;
  IF r_p2 THEN fb := BIT_SET(fb, 1); END_IF;
  IF BIT_TST(cmd, 2) AND NOT BIT_TST(flt, 2) THEN fb := BIT_SET(fb, 2); END_IF;
  IF r_p4 THEN fb := BIT_SET(fb, 3); END_IF;
  direct := BIT_TST(cmd, 4);

  (* ---- Braendefyr: 15 kg pr. ilaegning, maks 30 kg, 25 kW, spjaeld over 88 C ---- *)
  IF cmd_fyr_op THEN FF_KG := MIN(FF_KG + 15.0, 30.0); END_IF;
  cmd_fyr_op := FALSE;
  IF FF_KG > 0.0 THEN
    FF_KW := 25.0 * MIN(1.0, FF_KG / 4.0) * LIMIT(0.3, (FFTF - 10.0) / 50.0, 1.0);
    IF FFTF > 88.0 THEN FF_KW := FF_KW * 0.3; END_IF;
  ELSE
    FF_KW := 0.0;
  END_IF;
  FF_KG := FF_KG - FF_KW * dt / 12000.0;
  IF FF_KG < 0.3 THEN FF_KG := 0.0; END_IF;   (* gloederne er braendt ud *)
  LADDOMAT := HYSTERESIS(FFTF, 72.0, 68.0);
  ff_q := 0.0; ff_mt := 0.0;
  IF r_p4 THEN
    IF LADDOMAT THEN
      FFTR := MIN(MAX(g_att6, 60.0), FFTF);
      ff_q := 0.3 * 4.186 * (FFTF - FFTR);
      ff_mt := ff_q / (4.186 * MAX(FFTF - g_att6, 2.0));
    ELSE
      FFTR := FFTF - 1.0;
    END_IF;
  ELSE
    FFTR := FFTR + (20.0 - FFTR) * MIN(1.0, dt / 1800.0);
  END_IF;
  FFTF := LIMIT(0.0, FFTF + (FF_KW - ff_q - 0.05 * (FFTF - 20.0)) * dt / 400.0, 112.0);
  g_fftf := FFTF;
  E_FF := E_FF + ff_q * dt / 3600.0;

  (* ---- Pillefyr: 0 Stop, 1 Taending, 2 Drift (5-15 kW), 3 Udbraending, 4 Fejl ---- *)
  en := BIT_TST(cmd, 6);
  psp := sp_pille;
  IF direct THEN psp := g_stf_sp + 5.0; END_IF;
  CASE PILLE_ST OF
    0: PILLE_KW := 0.0;
       IF en AND (PFTF < psp - 5.0) THEN PILLE_ST := 1; ps_t := 0.0; PILLE_STARTS := PILLE_STARTS + 1; END_IF;
    1: PILLE_KW := 0.5;
       ps_t := ps_t + dt;
       IF NOT en THEN PILLE_ST := 0;
       ELSIF BIT_TST(flt, 4) THEN
         IF ps_t > 600.0 THEN PILLE_ST := 4; END_IF;
       ELSIF ps_t > 180.0 THEN PILLE_ST := 2;
       END_IF;
    2: PILLE_KW := LIMIT(5.0, 5.0 + (psp - PFTF) * 1.5, 15.0);
       IF (NOT en) OR (PFTF > psp + 5.0) THEN PILLE_ST := 3; ps_t := 0.0; END_IF;
    3: ps_t := ps_t + dt;
       PILLE_KW := MAX(0.0, 3.0 - ps_t * 0.01);
       IF ps_t > 300.0 THEN PILLE_ST := 0; END_IF;
    4: PILLE_KW := 0.0;
       IF NOT en THEN PILLE_ST := 0; END_IF;
  END_CASE;
  pm := 0.0; pret := PFTR;
  IF direct THEN
    IF r_p1 THEN pm := 0.15; END_IF;
    pret := g_str;
  ELSIF r_p2 THEN
    pm := 0.25; pret := g_att6;
  END_IF;
  IF pm > 0.0 THEN
    PFTR := pret;
  ELSE
    PFTR := PFTR + (20.0 - PFTR) * MIN(1.0, dt / 1800.0);
  END_IF;
  p_q := pm * 4.186 * (PFTF - pret);
  PFTF := LIMIT(0.0, PFTF + (PILLE_KW - p_q - 0.03 * (PFTF - 20.0)) * dt / 250.0, 112.0);
  g_pftf := PFTF;
  E_PILLE := E_PILLE + MAX(p_q, 0.0) * dt / 3600.0;
  PILLE_KG := PILLE_KG + PILLE_KW * dt / 15552.0;
  CASE PILLE_ST OF
    0: PILLE_TXT := 'Stop';
    1: PILLE_TXT := 'Tænding';
    2: PILLE_TXT := 'Drift';
    3: PILLE_TXT := 'Udbrænding';
    4: PILLE_TXT := 'Fejl';
  END_CASE;

  (* ---- Ladning af tanken (blanding af kilderne) ---- *)
  m_ch := ff_mt;
  e_ch := ff_mt * FFTF;
  IF r_p2 AND NOT direct THEN
    m_ch := m_ch + 0.25;
    e_ch := e_ch + 0.25 * PFTF;
  END_IF;
  g_mch := m_ch;
  IF m_ch > 0.001 THEN g_tch := e_ch / m_ch; ELSE g_tch := g_att1; END_IF;

  IF PILLE_ST = 2 THEN fb := BIT_SET(fb, 6); END_IF;
  IF FF_KG > 0.0 THEN fb := BIT_SET(fb, 9); END_IF;
  IF LADDOMAT THEN fb := BIT_SET(fb, 10); END_IF;
  IF PILLE_ST = 4 THEN fb := BIT_SET(fb, 11); END_IF;
  g_fb := fb;
END_PROGRAM
