PROGRAM TestNyEditor
(* Testprogram til SCADA-tegningen test_ny_editor. Ingen fysisk I/O.
   SCADA laeser og skriver variablerne over REST, kilde logic:NR:NAVN.
   TNE_AUTO TRUE: trinene i programmet (10 s hver) styrer kommandoerne.
   TNE_AUTO FALSE: kommandoerne TNE_CMD_x styres fra SCADA.
   Ventiler: 0 er A til AB, 1 er B til AB. Interval 500 ms. *)
VAR
  TNE_TXT       : STRING;
  TNE_AUTO      : BOOL := TRUE;
  TNE_CMD_PUMPE : BOOL;
  TNE_CMD_V1    : BOOL;
  TNE_CMD_V2    : BOOL;
  TNE_CMD_V3    : BOOL;
  TNE_CMD_MV    : BOOL;
  TNE_CMD_LAMPE : BOOL;
  TNE_FEJL      : BOOL;
  TNE_KVIT      : BOOL;
  TNE_RATE      : REAL := 1.0;
  TNE_FB_PUMPE  : BOOL;
  TNE_FB_V1     : BOOL;
  TNE_FB_V2     : BOOL;
  TNE_FB_V3     : BOOL;
  TNE_FB_MV     : BOOL;
  TNE_STATUS    : INT;
  TNE_TRIN      : INT;
  TNE_ALARM     : BOOL;
  TNE_TRYK_HOEJ : BOOL;
  TNE_TEMP      : REAL;
  TNE_TRYK      : REAL;
  TNE_NIVEAU    : REAL;
  TNE_FLOW      : REAL;
  tq            : BOOL;
  sq            : BOOL;
  v1u           : BOOL;
  v1d           : BOOL;
  v2u           : BOOL;
  v2d           : BOOL;
  kv            : BOOL;
  blk           : BOOL;
  m             : INT;
  ph            : REAL;
END_VAR
BEGIN
  (* 1 s taktgiver: analoge vaerdier *)
  TON(IN := NOT tq, PT := T#1s, Q => tq);
  IF tq THEN
    ph := ph + 0.1;
    IF ph > 6.2832 THEN ph := ph - 6.2832; END_IF;
    TNE_TEMP := 50.0 + 40.0 * SIN(ph);
    TNE_TRYK := 3.5 + 2.5 * SIN(3.0 * ph);
    IF TNE_FB_PUMPE THEN
      TNE_NIVEAU := TNE_NIVEAU + 2.0;
      TNE_FLOW := 60.0 + 10.0 * SIN(5.0 * ph);
    ELSE
      TNE_NIVEAU := TNE_NIVEAU - 1.0;
      TNE_FLOW := 0.0;
    END_IF;
    TNE_NIVEAU := LIMIT(0.0, TNE_NIVEAU, 100.0);
  END_IF;
  TNE_TRYK_HOEJ := HYSTERESIS(TNE_TRYK, 5.5, 5.0);

  (* Auto: trin 0-8, 10 s hver. Bit: 0 pumpe, 1 V1, 2 V2, 3 V3, 4 motorventil, 5 lampe, 6 pumpefejl *)
  TON(IN := TNE_AUTO AND NOT sq, PT := T#10s, Q => sq);
  IF sq THEN
    TNE_TRIN := TNE_TRIN + 1;
    IF TNE_TRIN > 8 THEN TNE_TRIN := 0; END_IF;
  END_IF;
  CASE TNE_TRIN OF
    0: m := 0;
    1: m := 16#05;
    2: m := 16#09;
    3: m := 16#0B;
    4: m := 16#07;
    5: m := 16#01;
    6: m := 16#35;
    7: m := 16#41;
    8: m := 16#20;
  END_CASE;
  IF TNE_AUTO THEN
    TNE_CMD_PUMPE := BIT_TST(m, 0);
    TNE_CMD_V1 := BIT_TST(m, 1);
    TNE_CMD_V2 := BIT_TST(m, 2);
    TNE_CMD_V3 := BIT_TST(m, 3);
    TNE_CMD_MV := BIT_TST(m, 4);
    TNE_CMD_LAMPE := BIT_TST(m, 5);
    TNE_KVIT := TNE_KVIT OR (TNE_TRIN = 0 AND sq);
  END_IF;
  blk := TNE_FEJL OR (TNE_AUTO AND BIT_TST(m, 6));

  (* Tilbagemeldinger: pumpe 2 s forsinket (og udebliver ved fejl), V1/V2 2 s gangtid begge veje, V3/motorventil straks *)
  TON(IN := TNE_CMD_PUMPE AND NOT blk, PT := T#2s, Q => TNE_FB_PUMPE);
  TON(IN := TNE_CMD_V1, PT := T#2s, Q => v1u);
  TOF(IN := TNE_CMD_V1, PT := T#2s, Q => v1d);
  TNE_FB_V1 := v1u OR (v1d AND TNE_FB_V1);
  TON(IN := TNE_CMD_V2, PT := T#2s, Q => v2u);
  TOF(IN := TNE_CMD_V2, PT := T#2s, Q => v2d);
  TNE_FB_V2 := v2u OR (v2d AND TNE_FB_V2);
  TNE_FB_V3 := TNE_CMD_V3;
  TNE_FB_MV := TNE_CMD_MV;

  (* Pumpealarm: kommanderet, men ingen tilbagemelding i 4 s -> laast til kvittering *)
  kv := TNE_KVIT;
  TNE_KVIT := FALSE;
  TNE_ALARM := SR(TON(TNE_CMD_PUMPE AND NOT TNE_FB_PUMPE, T#4s), kv);

  (* Status: 0 Stop, 1 Starter, 2 Koerer, 3 Fejl, 4 Stopper *)
  IF TNE_ALARM THEN TNE_STATUS := 3;
  ELSIF TNE_CMD_PUMPE AND TNE_FB_PUMPE THEN TNE_STATUS := 2;
  ELSIF TNE_CMD_PUMPE THEN TNE_STATUS := 1;
  ELSIF TNE_FB_PUMPE THEN TNE_STATUS := 4;
  ELSE TNE_STATUS := 0;
  END_IF;
  CASE TNE_STATUS OF
    0: TNE_TXT := 'Stop';
    1: TNE_TXT := 'Starter';
    2: TNE_TXT := 'Kører';
    3: TNE_TXT := 'Fejl';
    4: TNE_TXT := 'Stopper';
  END_CASE;
END_PROGRAM
