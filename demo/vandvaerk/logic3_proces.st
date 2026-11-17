PROGRAM VandvaerkProces
(* Broendstation med klordosering, Logic3: procesmodel. Broend med tilstroemning fra grundvandet, broendpumpe
   (35 l/s, 10 s opstart), trykmaaler, skylleventil (8 s gangtid), hypotank (50 l) med doseringspumpe (5 l/t),
   hoejdebeholder (300 m3) med doegnets forbrug og doegnmaengde. Klor: doseret koncentration (mg/l) = doseret
   hypo l/t * 120000 / flow l/t (12 pct hypo er 120 g/l). AT1 er efter indsproejtningen, AT2 efter kontakttanken
   (40 m3, 1. ordens forsinkelse med V / flow og lille nedbrydning). CT er klor gange kontakttid. Klokke,
   tidsfaktor og scenarier. Interval 500 ms.
   VW_SCEN: 0 normal, 1 broendpumpe fejl, 2 hypotank tom, 3 hoej efterspoergsel (2,5 gange), 4 overdosering (4 gange).
   Fejl der kan kombineres: VW_F_AN analysatorfejl, VW_F_P2 doseringspumpe fejl, VW_F_LAV lav grundvandsstand. *)
VAR
  VW_SPEED      : REAL := 10.0;
  VW_SCEN       : INT;
  VW_F_AN       : BOOL;
  VW_F_P2       : BOOL;
  VW_F_LAV      : BOOL;
  VW_KLOKKE     : REAL;
  VW_BROND      : REAL := 8.0;
  VW_Q          : REAL;
  VW_TRYK       : REAL;
  VW_P1_FB      : BOOL;
  VW_XV1_AABEN  : BOOL;
  VW_XV1_LUKKET : BOOL := TRUE;
  VW_XV1_POS    : REAL;
  VW_P2_FB      : BOOL;
  VW_FYLD       : BOOL;
  VW_HYPO       : REAL := 90.0;
  VW_P2_LH      : REAL;
  VW_BEH        : REAL := 35.0;
  VW_BEHOV      : REAL;
  VW_DOEGN      : REAL;
  VW_DOSE       : REAL;
  VW_AT1        : REAL;
  VW_AT2        : REAL;
  VW_TKONT      : REAL;
  VW_CT         : REAL;
  t_dag         : REAL := 21600.0;
  f_p1          : BOOL;
  over          : BOOL;
  dem_x         : REAL := 1.0;
  rech_x        : REAL := 1.0;
  ramp          : REAL;
  rech          : REAL;
  luft          : REAL;
  c1            : REAL;
  c2            : REAL;
  tau           : REAL;
  dt            : REAL;
  last_hour     : REAL;
END_VAR
BEGIN
  VW_SPEED := LIMIT(1.0, VW_SPEED, 120.0);
  g_speed := VW_SPEED;
  dt := 0.5 * VW_SPEED;

  (* klokken starter kl. 6 og gaar rundt i doegn *)
  t_dag := t_dag + dt;
  IF t_dag >= 86400.0 THEN t_dag := t_dag - 86400.0; END_IF;
  VW_KLOKKE := t_dag / 3600.0;

  (* scenarier og fejl *)
  VW_SCEN := LIMIT(0, VW_SCEN, 4);
  f_p1 := (VW_SCEN = 1);
  over := (VW_SCEN = 4);
  IF VW_SCEN = 3 THEN dem_x := 2.5; ELSE dem_x := 1.0; END_IF;
  IF VW_F_LAV THEN rech_x := 0.3; ELSE rech_x := 1.0; END_IF;
  g_f_p1 := f_p1;
  g_f_p2 := VW_F_P2;
  g_f_an := VW_F_AN;

  (* broendpumpen: 10 s op, 6 s ned; trukket tom for vand falder ydelsen *)
  IF g_p1_cmd AND (NOT f_p1) THEN
    ramp := MIN(1.0, ramp + dt / 10.0);
  ELSE
    ramp := MAX(0.0, ramp - dt / 6.0);
  END_IF;
  VW_P1_FB := ramp > 0.5;
  luft := LIMIT(0.0, (VW_BROND - 0.3) / 0.7, 1.0);
  VW_Q := 35.0 * ramp * luft;
  rech := 70.0 * rech_x * (10.0 - VW_BROND) / 10.0;
  VW_BROND := LIMIT(0.0, VW_BROND + (rech - VW_Q) * dt / 3000.0, 10.0);
  VW_TRYK := ramp * (3.0 + 0.02 * VW_BEH);

  (* skylleventil: 8 s gangtid *)
  IF g_xv1_cmd THEN
    VW_XV1_POS := MIN(100.0, VW_XV1_POS + dt / 8.0 * 100.0);
  ELSE
    VW_XV1_POS := MAX(0.0, VW_XV1_POS - dt / 8.0 * 100.0);
  END_IF;
  VW_XV1_AABEN := VW_XV1_POS >= 95.0;
  VW_XV1_LUKKET := VW_XV1_POS <= 5.0;

  (* hypo: doseringspumpen kan give 5 l/t; overdosering er 4 gange; tanken er 50 l *)
  VW_P2_FB := g_p2_cmd AND (NOT VW_F_P2);
  IF VW_P2_FB THEN
    VW_P2_LH := 5.0 * g_p2_pct / 100.0;
    IF over THEN VW_P2_LH := VW_P2_LH * 4.0; END_IF;
  ELSE
    VW_P2_LH := 0.0;
  END_IF;
  IF VW_FYLD THEN
    VW_HYPO := 100.0;
    VW_FYLD := FALSE;
  END_IF;
  VW_HYPO := LIMIT(0.0, VW_HYPO - VW_P2_LH * dt / 3600.0 / 50.0 * 100.0, 100.0);
  IF VW_SCEN = 2 THEN VW_HYPO := MIN(VW_HYPO, 2.0); END_IF;

  (* forbrug: 20 l/s i middel, mest om eftermiddagen; hoejdebeholderen er 300 m3 *)
  VW_BEHOV := 20.0 * (1.0 + 0.6 * SIN(6.2832 * (VW_KLOKKE - 9.0) / 24.0)) * dem_x;
  VW_BEH := LIMIT(0.0, VW_BEH + (VW_Q - VW_BEHOV) * dt / 1000.0 / 300.0 * 100.0, 100.0);

  (* doegnmaengde nulstilles ved midnat *)
  VW_DOEGN := VW_DOEGN + VW_Q * dt / 1000.0;
  IF VW_KLOKKE < last_hour THEN VW_DOEGN := 0.0; END_IF;
  last_hour := VW_KLOKKE;

  (* klor: doseret koncentration, blanding, kontakttank *)
  IF VW_Q > 0.5 THEN
    VW_DOSE := VW_P2_LH * 120000.0 / (VW_Q * 3600.0);
  ELSE
    VW_DOSE := 0.0;
  END_IF;
  c1 := c1 + (VW_DOSE - c1) * MIN(1.0, dt / 20.0);
  IF VW_Q > 1.0 THEN
    tau := 40000.0 / VW_Q;
    VW_TKONT := MIN(40000.0 / VW_Q / 60.0, 999.0);
  ELSE
    tau := 1000000.0;
    VW_TKONT := 0.0;
  END_IF;
  c2 := MAX(0.0, c2 + ((c1 - c2) / tau - 0.00005 * c2) * dt);
  VW_AT1 := c1;
  IF VW_F_AN THEN
    VW_AT2 := -1.0;
    VW_CT := 0.0;
  ELSE
    VW_AT2 := c2;
    VW_CT := c2 * VW_TKONT;
  END_IF;

  g_at2 := VW_AT2;
  g_well := VW_BROND;
  g_q := VW_Q;
  g_p1_run := VW_P1_FB;
  g_p2_run := VW_P2_FB;
  g_xv1_open := VW_XV1_AABEN;
  g_hypo := VW_HYPO;
  g_res := VW_BEH;
  g_vol := VW_DOEGN;
END_PROGRAM
