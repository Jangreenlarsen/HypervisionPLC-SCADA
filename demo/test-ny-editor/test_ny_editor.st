PROGRAM TestNyEditor
(* Testprogram til SCADA-tegningen test_ny_editor. Ingen fysisk I/O.
   SCADA laeser og skriver variablerne over REST, kilde logic:NR:NAVN.
   Hovedpumpe og reservepumpe staar parallelt. Reservepumpen starter af sig selv, naar hovedpumpen er kommanderet uden
   tilbagemelding og alarmen er laast (TNE_RESERVE slaar det til/fra), og stopper igen ved kvittering.
   TNE_AUTO TRUE: trinene i programmet (10 s hver) styrer kommandoerne. FALSE: TNE_CMD_x styres fra SCADA.
   Ventiler: 0 er A til AB, 1 er B til AB. Interval 500 ms. *)
VAR
  TNE_TXT        : STRING;
  TNE_AUTO       : BOOL := TRUE;
  TNE_RESERVE    : BOOL := TRUE;
  TNE_CMD_PUMPE  : BOOL;
  TNE_CMD_PUMPE2 : BOOL;
  TNE_CMD_V1     : BOOL;
  TNE_CMD_V2     : BOOL;
  TNE_CMD_V3     : BOOL;
  TNE_CMD_MV     : BOOL;
  TNE_CMD_LAMPE  : BOOL;
  TNE_FEJL       : BOOL;
  TNE_FEJL2      : BOOL;
  TNE_KVIT       : BOOL;
  TNE_RATE       : REAL := 1.0;
  TNE_FB_PUMPE   : BOOL;
  TNE_FB_PUMPE2  : BOOL;
  TNE_FB_V1      : BOOL;
  TNE_FB_V2      : BOOL;
  TNE_FB_V3      : BOOL;
  TNE_FB_MV      : BOOL;
  TNE_STATUS     : INT;
  TNE_STATUS2    : INT;
  TNE_SYSTEM     : INT;
  TNE_SCEN       : INT;
  TNE_TRIN       : INT;
  TNE_ALARM      : BOOL;
  TNE_ALARM2     : BOOL;
  TNE_TRYK_HOEJ  : BOOL;
  TNE_TEMP       : REAL;
  TNE_TRYK       : REAL;
  TNE_NIVEAU     : REAL;
  TNE_FLOW       : REAL;
  tq             : BOOL;
  sq             : BOOL;
  kv             : BOOL;
  blk            : BOOL;
  run2           : BOOL;
  dem            : BOOL;
  c1             : INT;
  c2             : INT;
  m              : INT;
  ph             : REAL;
END_VAR
BEGIN
  (* 1 s taktgiver: analoge vaerdier og ventilernes gangtid (2 s) *)
  TON(IN := NOT tq, PT := T#1s, Q => tq);
  IF tq THEN
    ph := ph + 0.1;
    IF ph > 6.2832 THEN ph := ph - 6.2832; END_IF;
    TNE_TEMP := 50.0 + 40.0 * SIN(ph);
    TNE_TRYK := 3.5 + 2.5 * SIN(3.0 * ph);
    IF TNE_FB_PUMPE OR TNE_FB_PUMPE2 THEN
      TNE_NIVEAU := TNE_NIVEAU + 2.0;
      TNE_FLOW := 60.0 + 10.0 * SIN(5.0 * ph);
    ELSE
      TNE_NIVEAU := TNE_NIVEAU - 1.0;
      TNE_FLOW := 0.0;
    END_IF;
    TNE_NIVEAU := LIMIT(0.0, TNE_NIVEAU, 100.0);
    IF TNE_CMD_V1 XOR TNE_FB_V1 THEN
      c1 := c1 + 1;
      IF c1 >= 2 THEN TNE_FB_V1 := TNE_CMD_V1; c1 := 0; END_IF;
    ELSE
      c1 := 0;
    END_IF;
    IF TNE_CMD_V2 XOR TNE_FB_V2 THEN
      c2 := c2 + 1;
      IF c2 >= 2 THEN TNE_FB_V2 := TNE_CMD_V2; c2 := 0; END_IF;
    ELSE
      c2 := 0;
    END_IF;
  END_IF;
  TNE_TRYK_HOEJ := HYSTERESIS(TNE_TRYK, 5.5, 5.0);

  (* Auto: trin 0-11, 10 s hver. Bit: 0 pumpe, 1 V1, 2 V2, 3 V3, 4 motorventil, 5 lampe, 6 hovedpumpe doer, 7 kvittering *)
  TON(IN := TNE_AUTO AND NOT sq, PT := T#10s, Q => sq);
  IF sq THEN
    TNE_TRIN := TNE_TRIN + 1;
    IF TNE_TRIN > 11 THEN TNE_TRIN := 0; END_IF;
  END_IF;
  CASE TNE_TRIN OF
    0: m := 0;
    1: m := 16#15;
    2: m := 16#19;
    3: m := 16#1B;
    4: m := 16#17;
    5: m := 16#01;
    6: m := 16#35;
    7: m := 16#55;
    8: m := 16#55;
    9: m := 16#15;
    10: m := 16#95;
    11: m := 16#20;
  END_CASE;
  IF TNE_TRIN = 0 OR TNE_TRIN = 11 THEN TNE_SCEN := 0;
  ELSIF TNE_TRIN < 7 THEN TNE_SCEN := 1;
  ELSIF TNE_TRIN = 7 THEN TNE_SCEN := 2;
  ELSIF TNE_TRIN < 10 THEN TNE_SCEN := 3;
  ELSE TNE_SCEN := 4;
  END_IF;
  IF TNE_AUTO THEN
    TNE_CMD_PUMPE := BIT_TST(m, 0);
    TNE_CMD_V1 := BIT_TST(m, 1);
    TNE_CMD_V2 := BIT_TST(m, 2);
    TNE_CMD_V3 := BIT_TST(m, 3);
    TNE_CMD_MV := BIT_TST(m, 4);
    TNE_CMD_LAMPE := BIT_TST(m, 5);
    TNE_CMD_PUMPE2 := FALSE;
    TNE_KVIT := TNE_KVIT OR (BIT_TST(m, 7) AND sq);
  END_IF;
  blk := TNE_FEJL OR (TNE_AUTO AND BIT_TST(m, 6));

  (* Reservepumpen: kommanderet fra SCADA, eller automatisk naar hovedpumpen er kommanderet og alarmen er laast *)
  run2 := TNE_CMD_PUMPE2 OR (TNE_CMD_PUMPE AND TNE_RESERVE AND TNE_ALARM);
  dem := TNE_CMD_PUMPE OR run2;

  (* Tilbagemeldinger: pumperne 2 s forsinket (udebliver ved fejl), V3 og motorventil straks *)
  TON(IN := TNE_CMD_PUMPE AND NOT blk, PT := T#2s, Q => TNE_FB_PUMPE);
  TON(IN := run2 AND NOT TNE_FEJL2, PT := T#2s, Q => TNE_FB_PUMPE2);
  TNE_FB_V3 := TNE_CMD_V3;
  TNE_FB_MV := TNE_CMD_MV;

  (* Pumpealarmer: kommanderet, men ingen tilbagemelding i 4 s, laast til kvittering *)
  kv := TNE_KVIT;
  TNE_KVIT := FALSE;
  TNE_ALARM := SR(TON(TNE_CMD_PUMPE AND NOT TNE_FB_PUMPE, T#4s), kv);
  TNE_ALARM2 := SR(TON(run2 AND NOT TNE_FB_PUMPE2, T#4s), kv);

  (* Status pr. pumpe: 0 Stop, 1 Starter, 2 Koerer, 3 Fejl, 4 Stopper *)
  IF TNE_ALARM THEN TNE_STATUS := 3;
  ELSIF TNE_CMD_PUMPE AND TNE_FB_PUMPE THEN TNE_STATUS := 2;
  ELSIF TNE_CMD_PUMPE THEN TNE_STATUS := 1;
  ELSIF TNE_FB_PUMPE THEN TNE_STATUS := 4;
  ELSE TNE_STATUS := 0;
  END_IF;
  IF TNE_ALARM2 THEN TNE_STATUS2 := 3;
  ELSIF run2 AND TNE_FB_PUMPE2 THEN TNE_STATUS2 := 2;
  ELSIF run2 THEN TNE_STATUS2 := 1;
  ELSIF TNE_FB_PUMPE2 THEN TNE_STATUS2 := 4;
  ELSE TNE_STATUS2 := 0;
  END_IF;

  (* Systemet: 0 Stoppet, 1 Normal drift, 2 Reserve overtager, 3 Ingen pumpe, 4 Starter *)
  IF NOT dem AND NOT TNE_FB_PUMPE AND NOT TNE_FB_PUMPE2 THEN TNE_SYSTEM := 0;
  ELSIF TNE_FB_PUMPE AND NOT TNE_ALARM THEN TNE_SYSTEM := 1;
  ELSIF TNE_FB_PUMPE2 THEN TNE_SYSTEM := 2;
  ELSIF TNE_ALARM OR TNE_ALARM2 THEN TNE_SYSTEM := 3;
  ELSE TNE_SYSTEM := 4;
  END_IF;
  CASE TNE_SYSTEM OF
    0: TNE_TXT := 'Stoppet';
    1: TNE_TXT := 'Normal drift';
    2: TNE_TXT := 'Reserve kører';
    3: TNE_TXT := 'Ingen pumpe';
    4: TNE_TXT := 'Starter';
  END_CASE;
END_PROGRAM
