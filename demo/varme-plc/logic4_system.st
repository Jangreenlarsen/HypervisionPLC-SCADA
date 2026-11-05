PROGRAM SystemDemo
(* Demo-varmeanlaeg, Logic4: systemtryk med ekspansion og sikkerhedsventiler
   (2,5 bar), udetemperatur over doegnet, simuleret klokke, tidsfaktor,
   scenarier og fejlinjektion, samt varmepumpen (P3). Interval 500 ms.
   cmd_scenarie: 0 Normal, 1 Vinternat, 2 Sommer, 3 Laekage, 4 Pumpefejl P1. *)
VAR
  FFS_TXT       : STRING;   (* braendefyrets status *)
  sp_speed      : REAL := 1.0;
  cmd_scenarie  : INT;
  cmd_efterfyld : BOOL;
  sp_tude_fast  : BOOL;
  sp_tude       : REAL := 5.0;
  f_P1          : BOOL;
  f_P2          : BOOL;
  f_P3          : BOOL;
  f_P4          : BOOL;
  f_pille       : BOOL;
  f_vp          : BOOL;
  f_laek        : BOOL;
  ST            : REAL := 1.2;
  SV_AABEN      : BOOL;
  T_UDE         : REAL;
  KLOKKE        : REAL;
  DAG           : INT;
  p_fill        : REAL := 1.2;
  t_dag         : REAL := 21600.0;
  dt            : REAL;
  mid           : REAL;
  amp           : REAL;
  tm            : REAL;
  p             : REAL;
  flt           : INT;
  VPTF          : REAL := 20.0;
  VPTR          : REAL := 20.0;
  VP_KW         : REAL;
  VP_EL         : REAL;
  VP_COP        : REAL := 4.0;
  VP_RUN        : BOOL;
  E_VP          : REAL;
  E_VP_EL       : REAL;
  r_p3          : BOOL;
  vq            : REAL;
  kf            : REAL;
END_VAR
BEGIN
  sp_speed := LIMIT(1.0, sp_speed, 120.0);
  g_speed := sp_speed;
  dt := 0.5 * sp_speed;

  t_dag := t_dag + dt;
  IF t_dag >= 86400.0 THEN t_dag := t_dag - 86400.0; DAG := DAG + 1; END_IF;
  KLOKKE := t_dag / 3600.0;

  CASE cmd_scenarie OF
    1: mid := -12.0; amp := 3.0;
    2: mid := 18.0; amp := 6.0;
  ELSE
    mid := 3.0; amp := 4.0;
  END_CASE;
  (* koldest kl. 05, varmest kl. 17 *)
  T_UDE := mid - amp * COS((t_dag - 18000.0) * 0.0000727221);
  IF sp_tude_fast THEN T_UDE := sp_tude; END_IF;
  g_tude := T_UDE;

  flt := 0;
  IF f_P1 OR (cmd_scenarie = 4) THEN flt := BIT_SET(flt, 0); END_IF;
  IF f_P2 THEN flt := BIT_SET(flt, 1); END_IF;
  IF f_P3 THEN flt := BIT_SET(flt, 2); END_IF;
  IF f_P4 THEN flt := BIT_SET(flt, 3); END_IF;
  IF f_pille THEN flt := BIT_SET(flt, 4); END_IF;
  IF f_laek OR (cmd_scenarie = 3) THEN flt := BIT_SET(flt, 5); END_IF;
  IF f_vp THEN flt := BIT_SET(flt, 7); END_IF;

  (* ---- Varmepumpe: ca. 8 kW, COP efter udetemp og fremloeb, stopper ved retur > 52 C ---- *)
  r_p3 := BIT_TST(g_cmd, 2) AND NOT f_P3;
  VP_RUN := BIT_TST(g_cmd, 7) AND r_p3 AND NOT f_vp AND (g_att6 < 52.0);
  IF BIT_TST(g_cmd, 7) AND f_vp THEN flt := BIT_SET(flt, 12); END_IF;
  g_fault := flt;
  vq := 0.0;
  IF VP_RUN THEN
    vq := 8.0 * (1.0 + 0.02 * (T_UDE - 7.0));
    VP_COP := LIMIT(1.5, 4.8 - 0.07 * (VPTF - 35.0) + 0.06 * (T_UDE - 7.0), 6.0);
  END_IF;
  kf := MIN(1.0, dt / 1800.0);
  VP_KW := VP_KW + (vq - VP_KW) * MIN(1.0, dt / 120.0);
  IF r_p3 THEN
    VPTR := g_att6;
    VPTF := g_att6 + VP_KW / 1.2558;
  ELSE
    VP_KW := 0.0;
    VPTF := VPTF + (20.0 - VPTF) * kf;
    VPTR := VPTR + (20.0 - VPTR) * kf;
  END_IF;
  g_vptf := VPTF;
  VP_EL := 0.0;
  IF VP_RUN THEN VP_EL := VP_KW / VP_COP; END_IF;
  E_VP := E_VP + VP_KW * dt / 3600.0;
  E_VP_EL := E_VP_EL + VP_EL * dt / 3600.0;

  (* Tryk: fyldning + varmeudvidelse (ekspansionsbeholder) + damp over 100 C *)
  tm := (g_att1 + g_att3 + g_att6) / 3.0 * 0.85 + (g_fftf + g_pftf) * 0.075;
  p := p_fill + 0.012 * (tm - 20.0);
  IF g_fftf > 100.0 THEN p := p + (g_fftf - 100.0) * 0.15; END_IF;
  IF g_pftf > 100.0 THEN p := p + (g_pftf - 100.0) * 0.15; END_IF;
  SV_AABEN := HYSTERESIS(p, 2.5, 2.3);
  IF SV_AABEN THEN p_fill := p_fill - 0.002 * dt; END_IF;
  IF BIT_TST(flt, 5) THEN p_fill := p_fill - 0.00005 * dt; END_IF;
  IF cmd_efterfyld THEN p_fill := 1.2; END_IF;
  cmd_efterfyld := FALSE;
  p_fill := MAX(p_fill, 0.0);
  ST := MAX(p, 0.0);
  g_tryk := ST;
  IF g_fftf > 95.0 THEN FFS_TXT := 'Overtemp';
  ELSIF BIT_TST(g_fb, 9) AND (g_fftf < 60.0) THEN FFS_TXT := 'Optænding';
  ELSIF BIT_TST(g_fb, 9) THEN FFS_TXT := 'Drift';
  ELSE FFS_TXT := 'Slukket';
  END_IF;
  WDT_FEED();
END_PROGRAM
