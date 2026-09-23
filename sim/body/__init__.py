"""Phase 9: the closed brain-body loop (the whole-brain model steering a
physics-simulated fly body).

Plain-English map of this package
---------------------------------
* ``brain_stepper``  runs the brain in short time windows while KEEPING its
  state (voltages, pending spikes) from one window to the next. The project's
  ``FastBrain`` always starts every run from rest, so this is needed for a
  loop. It is tested to give spike-for-spike the same result as one
  uninterrupted ``FastBrain`` run.
* ``odor``           the smell world: odor sources and the published
  "strength falls off with 1 / distance squared" rule, measured at the two
  antennae.
* ``mapping``        the two translation tables of the loop, written out
  explicitly: antenna odor strength -> firing rate of the smell neurons
  (ORNs), and descending-neuron firing -> the body's two-number
  (left, right) walking drive. Also the hand-written "body only" steering
  rule (NOT brain-driven), used as a comparison.
* ``loop``           the loop itself (needs FlyGym, so it only works in the
  separate ``.venv-body`` environment).

Only ``loop`` imports FlyGym; everything else runs in the main ``.venv`` too.
"""
