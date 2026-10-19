# Third-party notices

## Drosophila_brain_model (Shiu & Spiller)

`sim/shiu_model.py` is a port of, and `sim/fast_engine.py` re-implements and copies constants
from, the whole-brain model code of Shiu et al. 2024:
https://github.com/philshiu/Drosophila_brain_model (commit 91bdd1e). Both files carry the
notice below in their header. The code is used under the MIT License:

```
MIT License

Copyright (c) 2023 Philip Shiu and Nico Spiller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Their code and preprocessed connectome files are downloaded into `data/reference/` at setup
time and are not part of this repository.

## Data

FlyWire-derived data (CC BY-NC 4.0) and DoOR-derived tables (CC BY-SA 4.0) are covered in
[DATA_LICENSE.md](DATA_LICENSE.md).

## Python dependencies (installed, not vendored)

Installed with pip from `requirements.txt` / `requirements-body.txt`; none of their code is
copied into this repository. Notable licences: brian2 (CeCILL-2.1, a GPL-compatible copyleft
licence), numpy, scipy, pandas, numba, uvicorn (BSD), pyarrow, mujoco, FlyGym/NeuroMechFly
(Apache-2.0), fastapi (MIT), matplotlib (PSF-style). The optional body environment's
imageio-ffmpeg downloads an ffmpeg binary (LGPL/GPL) for local video rendering only.
