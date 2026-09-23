# Phase 8 census (snapshot 630)

Circuit: 685 projection neurons, 5177 Kenyon cells, 97 MBONs, 326 DANs, 4 APL + DPM; 570433 connections among them.

Plastic KC->MBON connections: 62177 (from 5177 KCs onto 96 MBONs, 256550 synapses) in 53 synapse groups (compartment set x hemisphere).

All KC->MBON connections in the data: 62177 (so every one is plastic; the 1 untyped MBON gets no KC input).

DANs that feed the dopamine signal: 305 (types PAM01..PPL106); not assigned: PPL107, PPL201-203 and 13 untyped DANs.


## KC->MBON synapses per MBON type and assigned compartment

| mbon_type | synapses by compartment |
|---|---|
| MBON01 | bp2a: 1357, g5: 7590, g5+bp2a: 9 |
| MBON02 | b2: 9251, bp2a: 681 |
| MBON03 | bp2m+bp2p: 15507 |
| MBON04 | bp2m+bp2p: 6232 |
| MBON05 | g4: 20402 |
| MBON06 | b1: 12214 |
| MBON07 | a1: 22762 |
| MBON09 | bp1: 10304, g3: 21851, g3+bp1: 3 |
| MBON10 | bp1: 1478 |
| MBON11 | g1: 12318, g1+pedc: 92, pedc: 5939 |
| MBON12 | ap1: 7230, g2: 5197 |
| MBON13 | ap2: 6236 |
| MBON14 | a3: 20408 |
| MBON15 | ap1: 425 |
| MBON15-like | ap1: 1221 |
| MBON16 | ap3: 2692 |
| MBON17 | ap3: 2018 |
| MBON17-like | ap3: 1277 |
| MBON18 | a2: 9904 |
| MBON19 | a2+a3: 859 |
| MBON20 | g1+g2: 1867 |
| MBON21 | g4+g5: 3121 |
| MBON22 | calyx: 12934 |
| MBON23 | a2: 3113 |
| MBON24 | b2: 3410, b2+g5: 3, g5: 111 |
| MBON25,MBON34 | g1+g2: 641 |
| MBON26 | bp2d: 3276 |
| MBON27 | g5: 2631 |
| MBON28 | ap3: 2024 |
| MBON29 | g4+g5: 1841 |
| MBON30 | g1+g2+g3: 5662 |
| MBON31 | ap1: 3270 |
| MBON32 | g2: 4726 |
| MBON33 | g2+g3: 588 |
| MBON35 | g2: 1875 |


## DAN hemisphere split (fraction of each DAN's KC synapses in the LEFT mushroom body)

Many DANs innervate both mushroom bodies in FlyWire, so dopamine is split by these measured fractions, not by the soma side.

| type | cells | mean_frac_left | min_frac_left | max_frac_left |
|---|---|---|---|---|
| PAM01 | 39 | 0.528 | 0.067 | 1.000 |
| PAM02 | 15 | 0.492 | 0.121 | 0.780 |
| PAM03 | 10 | 0.446 | 0.222 | 0.741 |
| PAM04 | 30 | 0.586 | 0.163 | 1.000 |
| PAM05 | 19 | 0.435 | 0.213 | 0.691 |
| PAM06 | 30 | 0.432 | 0.152 | 0.650 |
| PAM07 | 18 | 0.507 | 0.141 | 0.894 |
| PAM08 | 39 | 0.520 | 0.198 | 0.882 |
| PAM09 | 10 | 0.696 | 0.406 | 1.000 |
| PAM10 | 13 | 0.542 | 0.102 | 0.695 |
| PAM11 | 16 | 0.431 | 0.000 | 1.000 |
| PAM12 | 22 | 0.560 | 0.407 | 0.820 |
| PAM13 | 11 | 0.468 | 0.321 | 0.562 |
| PAM14 | 17 | 0.576 | 0.391 | 0.697 |
| PAM15 | 4 | 0.532 | 0.213 | 0.737 |
| PPL101 | 2 | 0.643 | 0.538 | 0.748 |
| PPL102 | 2 | 0.500 | 0.000 | 1.000 |
| PPL103 | 2 | 0.602 | 0.583 | 0.622 |
| PPL104 | 2 | 0.367 | 0.240 | 0.493 |
| PPL105 | 2 | 0.499 | 0.428 | 0.571 |
| PPL106 | 2 | 0.392 | 0.316 | 0.468 |


## Cross-check: DAN -> MBON synapses that join a DAN and an MBON sharing a compartment

Overall: 87.8% of 14459 synapses.


| dan | DAN->MBON synapses | to MBONs sharing a compartment | fraction | top target |
|---|---|---|---|---|
| PAM01 | 482 | 459 | 0.952 | MBON01 |
| PAM02 | 139 | 72 | 0.518 | MBON01 |
| PAM03 | 37 | 21 | 0.568 | MBON03 |
| PAM04 | 635 | 616 | 0.970 | MBON02 |
| PAM05 | 1279 | 686 | 0.536 | MBON26 |
| PAM06 | 1825 | 1756 | 0.962 | MBON03 |
| PAM07 | 563 | 506 | 0.899 | MBON05 |
| PAM08 | 1585 | 1205 | 0.760 | MBON05 |
| PAM09 | 229 | 183 | 0.799 | MBON06 |
| PAM10 | 1108 | 1060 | 0.957 | MBON06 |
| PAM11 | 1546 | 1461 | 0.945 | MBON07 |
| PAM12 | 582 | 503 | 0.864 | MBON09 |
| PAM13 | 217 | 189 | 0.871 | MBON09 |
| PAM14 | 276 | 252 | 0.913 | MBON09 |
| PAM15 | 63 | 39 | 0.619 | MBON27 |
| PPL101 | 1037 | 971 | 0.936 | MBON11 |
| PPL102 | 108 | 71 | 0.657 | MBON11 |
| PPL103 | 1424 | 1408 | 0.989 | MBON12 |
| PPL104 | 289 | 275 | 0.952 | MBON16 |
| PPL105 | 547 | 500 | 0.914 | MBON13 |
| PPL106 | 488 | 465 | 0.953 | MBON14 |
