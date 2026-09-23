"""Neuron IDs used in this experiment (FlyWire snapshot 630, int64).

Copied from experiments/fast_engine/benchmark.py, which copied them from the
reference repository's figures.ipynb (Figure 1 cell): the 21 labellar
sugar-sensing gustatory receptor neurons (GRNs) of one hemisphere, and the two
MN9 motor neurons (proboscis extension / feeding).
"""
SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
MN9 = 720575940660219265     # MN9 contralateral to the stimulated GRNs (the paper's readout)
MN9_B = 720575940645521262   # the other MN9 (ipsilateral; exists in v630 only)
