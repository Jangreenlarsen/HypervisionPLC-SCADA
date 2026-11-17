PROGRAM VandvaerkStyring
(* Broendstation med klordosering, Logic2: styring. Driftsform (0 fra, 1 auto, 2 manuel), startsekvens (skyl,
   broendpumpe, dosering), stop, tilladelser, interlocks og alarmer. Dosering er flow-proportional med trim fra
   analysatoren efter kontakttanken. Ingen fysisk I/O. Interval 500 ms. Tider i sekunder paa den simulerede tid.
   VW_STATUS: 0 stoppet, 1 starter, 2 drift, 3 stopper, 4 trip.
   VW_TRIP: 0 ingen, 1 broend lav, 2 hypo eller dosering, 3 klor uden for graenser, 4 pumpe eller intet flow. *)
VAR
  VW_MODE        : INT := 1;
  VW_KVIT        : BOOL;
  VW_MAN_P1      : BOOL;
  VW_MAN_P2      : BOOL;
  VW_MAN_XV1     : BOOL;
  VW_SP_START    : REAL := 40.0;
  VW_SP_STOP     : REAL := 85.0;
  VW_SP_DOSE     : REAL := 1.0;
  VW_SP_RES      : REAL := 0.5;
  VW_TRIM        : BOOL := TRUE;
  VW_SP_LAV      : REAL := 0.2;
  VW_SP_HOEJ     : REAL := 2.0;
  VW_STATUS      : INT;
  VW_TRIN        : INT;
  VW_TRIP        : INT;
  VW_KOM_P1      : BOOL;
  VW_KOM_P2      : BOOL;
  VW_KOM_XV1     : BOOL;
  VW_DOSIS_EFF   : REAL := 1.0;
  VW_P2_PCT      : REAL;
  VW_ALARMER     : INT;
  VW_AL_BROND    : BOOL;
  VW_AL_BROND_LL : BOOL;
  VW_AL_HYPO     : BOOL;
  VW_AL_HYPO_TOM : BOOL;
  VW_AL_KLOR_LAV : BOOL;
  VW_AL_KLOR_HOEJ: BOOL;
  VW_AL_P1       : BOOL;
  VW_AL_P2       : BOOL;
  VW_AL_FLOW     : BOOL;
  VW_AL_DOEGN    : BOOL;
  VW_AL_AN       : BOOL;
  VW_AL_BEH_LAV  : BOOL;
  VW_AL_BEH_HOEJ : BOOL;
  VW_AL_TRIP     : BOOL;
  trin           : INT;
  trip           : BOOL;
  trip_now       : INT;
  want           : BOOL;
  perm           : BOOL;
  permrun        : BOOL;
  clvalid        : BOOL;
  ack            : BOOL;
  p1             : BOOL;
  p2             : BOOL;
  xv1            : BOOL;
  t_step         : REAL;
  t_run          : REAL;
  t_hi           : REAL;
  t_lo           : REAL;
  t_nf           : REAL;
  t_nd           : REAL;
  dt             : REAL;
END_VAR
BEGIN
  dt := 0.5 * MAX(g_speed, 1.0);
  VW_MODE := LIMIT(0, VW_MODE, 2);
  ack := VW_KVIT;
  VW_KVIT := FALSE;
  clvalid := (NOT g_f_an) AND (g_at2 >= 0.0);

  (* tilladelser: til at starte, og til at blive ved at koere *)
  perm := (g_well >= 3.0) AND (g_hypo >= 10.0) AND (NOT g_f_p1) AND (NOT g_f_p2) AND (g_vol < 2400.0) AND (NOT trip);
  permrun := (g_well >= 1.5) AND (g_hypo >= 5.0) AND (g_res < 97.0) AND (g_vol < 2400.0);

  (* timere til interlocks: klor i simuleret tid, hardware i rigtig tid (0,5 s pr. scan) *)
  IF g_p2_run THEN t_run := t_run + dt; ELSE t_run := 0.0; END_IF;
  IF clvalid AND (g_q > 1.0) AND (g_at2 > VW_SP_HOEJ) THEN t_hi := t_hi + dt; ELSE t_hi := 0.0; END_IF;
  IF clvalid AND g_p2_run AND (t_run >= 900.0) AND (g_at2 < VW_SP_LAV) THEN t_lo := t_lo + dt; ELSE t_lo := 0.0; END_IF;
  IF g_p1_cmd AND (g_q < 10.0) THEN t_nf := t_nf + 0.5; ELSE t_nf := 0.0; END_IF;
  IF g_p2_cmd AND (NOT g_p2_run) THEN t_nd := t_nd + 0.5; ELSE t_nd := 0.0; END_IF;

  (* trip: groeft aarsag i prioriteret raekkefoelge, laast til kvittering naar aarsagen er vaek *)
  trip_now := 0;
  IF g_p1_cmd AND (g_well < 1.0) THEN
    trip_now := 1;
  ELSIF g_p2_cmd AND ((g_hypo < 3.0) OR (t_nd >= 10.0)) THEN
    trip_now := 2;
  ELSIF (t_hi >= 30.0) OR (t_lo >= 600.0) THEN
    trip_now := 3;
  ELSIF (g_p1_cmd AND g_f_p1) OR (t_nf >= 20.0) THEN
    trip_now := 4;
  END_IF;
  IF (trip_now > 0) AND (NOT trip) THEN
    trip := TRUE;
    VW_TRIP := trip_now;
  END_IF;
  IF trip AND ack AND (trip_now = 0) THEN
    trip := FALSE;
    VW_TRIP := 0;
  END_IF;

  (* oensket drift i auto: niveau i hoejdebeholderen med hysterese *)
  IF VW_MODE = 1 THEN
    IF g_res <= VW_SP_START THEN want := TRUE; END_IF;
    IF g_res >= VW_SP_STOP THEN want := FALSE; END_IF;
  ELSE
    want := FALSE;
  END_IF;

  IF trip THEN
    trin := 0;
    p1 := FALSE;
    p2 := FALSE;
    xv1 := FALSE;
  ELSIF VW_MODE = 2 THEN
    (* manuel: interlocks gaelder stadig *)
    trin := 0;
    p1 := VW_MAN_P1 AND (g_well >= 1.5) AND (NOT g_f_p1);
    p2 := VW_MAN_P2 AND g_p1_run AND (g_hypo >= 3.0);
    xv1 := VW_MAN_XV1 AND (NOT p1);
  ELSIF trin = 0 THEN
    p1 := FALSE;
    p2 := FALSE;
    xv1 := FALSE;
    IF want AND perm THEN
      trin := 1;
      t_step := 0.0;
    END_IF;
  ELSIF trin = 1 THEN
    (* skyl: skylleventilen aaben i 30 s *)
    xv1 := TRUE;
    t_step := t_step + dt;
    IF (NOT want) OR (NOT permrun) THEN
      trin := 5;
      t_step := 0.0;
    ELSIF g_xv1_open AND (t_step >= 30.0) THEN
      trin := 2;
      t_step := 0.0;
    END_IF;
  ELSIF trin = 2 THEN
    (* broendpumpen starter, skylleventilen lukker, vent paa stabilt flow *)
    xv1 := FALSE;
    p1 := TRUE;
    t_step := t_step + dt;
    IF (NOT want) OR (NOT permrun) THEN
      trin := 5;
      t_step := 0.0;
    ELSIF (g_q >= 20.0) AND (t_step >= 15.0) THEN
      trin := 3;
      t_step := 0.0;
    END_IF;
  ELSIF trin = 3 THEN
    (* dosering starter *)
    p2 := TRUE;
    t_step := t_step + dt;
    IF (NOT want) OR (NOT permrun) THEN
      trin := 5;
      t_step := 0.0;
    ELSIF g_p2_run AND (t_step >= 10.0) THEN
      trin := 4;
      t_step := 0.0;
    END_IF;
  ELSIF trin = 4 THEN
    IF (NOT want) OR (NOT permrun) THEN
      trin := 5;
      t_step := 0.0;
    END_IF;
  ELSE
    (* stop: doseringen foerst, saa broendpumpen *)
    p2 := FALSE;
    t_step := t_step + dt;
    IF t_step >= 10.0 THEN p1 := FALSE; END_IF;
    IF t_step >= 20.0 THEN trin := 0; END_IF;
  END_IF;

  (* flow-proportional dosering: l/t = flow l/s * dosis mg/l * 3600 / 120000 (12 pct hypo er 120 g/l); trim fra AT2 *)
  IF VW_TRIM AND clvalid AND (t_run >= 900.0) THEN
    VW_DOSIS_EFF := LIMIT(0.2, VW_SP_DOSE + 0.5 * (VW_SP_RES - g_at2), 3.0);
  ELSE
    VW_DOSIS_EFF := VW_SP_DOSE;
  END_IF;
  VW_P2_PCT := LIMIT(0.0, g_q * VW_DOSIS_EFF * 0.03 / 5.0 * 100.0, 100.0);
  g_p2_pct := VW_P2_PCT;

  g_p1_cmd := p1;
  g_p2_cmd := p2;
  g_xv1_cmd := xv1;
  VW_KOM_P1 := p1;
  VW_KOM_P2 := p2;
  VW_KOM_XV1 := xv1;
  VW_TRIN := trin;

  IF trip THEN
    VW_STATUS := 4;
  ELSIF trin = 5 THEN
    VW_STATUS := 3;
  ELSIF (trin >= 1) AND (trin <= 3) THEN
    VW_STATUS := 1;
  ELSIF (trin = 4) OR (g_p1_run AND (VW_MODE = 2)) THEN
    VW_STATUS := 2;
  ELSE
    VW_STATUS := 0;
  END_IF;

  VW_AL_BROND := g_well < 2.0;
  VW_AL_BROND_LL := g_well < 1.0;
  VW_AL_HYPO := g_hypo < 15.0;
  VW_AL_HYPO_TOM := g_hypo < 3.0;
  VW_AL_KLOR_LAV := t_lo >= 120.0;
  VW_AL_KLOR_HOEJ := clvalid AND (g_at2 > VW_SP_HOEJ);
  VW_AL_P1 := g_f_p1;
  VW_AL_P2 := g_f_p2;
  VW_AL_FLOW := t_nf >= 10.0;
  VW_AL_DOEGN := g_vol > 2160.0;
  VW_AL_AN := g_f_an;
  VW_AL_BEH_LAV := g_res < 20.0;
  VW_AL_BEH_HOEJ := g_res > 95.0;
  VW_AL_TRIP := trip;
  VW_ALARMER := BOOL_TO_INT(VW_AL_BROND) + BOOL_TO_INT(VW_AL_BROND_LL) + BOOL_TO_INT(VW_AL_HYPO) + BOOL_TO_INT(VW_AL_HYPO_TOM)
              + BOOL_TO_INT(VW_AL_KLOR_LAV) + BOOL_TO_INT(VW_AL_KLOR_HOEJ) + BOOL_TO_INT(VW_AL_P1) + BOOL_TO_INT(VW_AL_P2)
              + BOOL_TO_INT(VW_AL_FLOW) + BOOL_TO_INT(VW_AL_DOEGN) + BOOL_TO_INT(VW_AL_AN) + BOOL_TO_INT(VW_AL_BEH_LAV)
              + BOOL_TO_INT(VW_AL_BEH_HOEJ) + BOOL_TO_INT(VW_AL_TRIP);
END_PROGRAM
