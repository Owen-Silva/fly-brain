"""Steering / walking descending neurons, as snapshot-630 root IDs.

Where they come from: docs/phase9-body-research.md section 5 lists these
neurons with snapshot-783 IDs. Each 783 ID was checked against the 630 label
table (data/cache/connectome_630_neurons.parquet):

* DNa02: both IDs identical in 630 (630 label: hemibrain_type DNa02).
* DNa01: right ID identical in 630 (cell_type DNa01). The left 783 ID is
  missing from 630; the 630 neuron with cell_type DNa01 on the left side is
  720575940623860202 (matched by LABEL, not by wiring fingerprint).
* DNg100 (= BDN2): called ``DNge162`` in the 630 labels. Right ID identical;
  the left one is matched by label (720575940612364530).
* DNp09 (= P9): both IDs identical (630 hemibrain_type DNp09). Caution from
  the Phase 9 doc: the 630 type DNpe060 also carries hemibrain_type DNp09;
  it is listed separately below.
* DNb08: 783 cell_type DNb08 = 630 types DNbe009 + DNbe010 (3 of 4 IDs
  identical; the left DNbe010 matched by label).
* MDN (moonwalker, backward walking): 630 cell_type DNpe078, 4 cells.
* DNa03: steering-related (upstream of DNa02 in Rayshubskiy et al. 2025),
  added as an extra read-out.

"left"/"right" are the ``side`` column of the same label table that labels
the ORNs, so "same side" comparisons are consistent.
"""

STEERING = {
    "DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
    "DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551,
    "DNa03_L": 720575940620918789, "DNa03_R": 720575940630085583,
    "DNg100_L": 720575940612364530, "DNg100_R": 720575940647228468,
    "DNp09_L": 720575940635872101, "DNp09_R": 720575940627652358,
    "DNpe060_L": 720575940619498968, "DNpe060_R": 720575940633095137,
    "DNb08a_L": 720575940630334658, "DNb08a_R": 720575940634459290,
    "DNb08b_L": 720575940611749730, "DNb08b_R": 720575940621068464,
    "MDN_L1": 720575940616026939, "MDN_L2": 720575940631082808,
    "MDN_R1": 720575940610236514, "MDN_R2": 720575940640331472,
}
