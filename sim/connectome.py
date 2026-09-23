"""Phase 2: load the real fly brain (FlyWire release 783 by default, or 630).

Plain-English summary
---------------------
The fly brain wiring diagram comes as two lists:

* a list of **neurons** (one row per nerve cell, named by a long FlyWire ID
  number called a ``root_id``), and
* a list of **connections** ("neuron A sends N synapses to neuron B").

This module reads both lists, attaches a label to every neuron (its cell type,
its broad class, its predicted chemical messenger and where its cell body sits
in 3D), and turns the connections into a table and a big grid of numbers
(a "connection matrix") that the simulator can use.

Every neuron gets a fixed row number (0, 1, 2, ...). The order is exactly the
order used by the reference paper's own files, so row 5 here is row 5 there.
That matters for Phase 3, where we compare our results with theirs.

Two snapshots
-------------
FlyWire has released the brain more than once, and neuron ids change between
releases. ``load_connectome("783")`` (the default) loads public release 783,
the one current labels are made for. ``load_connectome("630")`` loads the
older release 630, which the Shiu et al. 2024 paper actually used: Phase 3
uses 630 so every neuron id in the paper exists (six of them are gone in 783).

Where the data comes from (see README.md for URLs and citations)
------------------------------------------------------------------
1. ``data/reference/``: the reference paper's preprocessed connection list
   and neuron list (and its row order) for each release
   (github.com/philshiu/Drosophila_brain_model): ``Connectivity_783.parquet``
   + ``Completeness_783.csv``, and ``2023_03_23_connectivity_630_final.parquet``
   + ``2023_03_23_completeness_630_final.csv``.
2. ``data/flywire/``: per-neuron labels from Schlegel et al. 2024
   (github.com/flyconnectome/flywire_annotations), downloaded without an
   account: tag v3.1.0 for release 783, tag v1.1.0 for release 630.

The sign assumption (read this)
-------------------------------
Each connection gets a **weight = number of synapses** and a **sign**:
``+1`` (excitatory: makes the next neuron more likely to fire) or ``-1``
(inhibitory: makes it less likely). The sign comes from the chemical the
*sending* neuron is predicted to release (Eckstein et al. 2024, a machine
learning prediction from the electron microscope images, not a measurement):

* acetylcholine -> excitatory (+1)
* GABA          -> inhibitory (-1)
* glutamate     -> inhibitory (-1)
* dopamine, serotonin, octopamine, or no prediction -> excitatory (+1)

This is **the reference paper's assumption** (Shiu et al. 2024), not a fact of
biology. The last line is what the reference file actually does: we checked
that 99.9% of dopamine, serotonin and octopamine neurons carry +1 in it.
The paper decided each neuron's sign slightly differently from us: it gave
each of the neuron's output synapses its own top prediction and called the
neuron inhibitory if more than half were GABA or glutamate. We use the single
per-neuron label (``top_nt``) from Schlegel et al., so the two disagree for
about 4% of neurons in 783 (1.5% in 630), almost all low-confidence ones.
Real limits: glutamate excites at some fly synapses (e.g. at muscles), one
neuron can release more than one chemical, modulators like dopamine act slowly
through other receptors rather than as simple +/- inputs, and the prediction
itself is sometimes wrong (it is least reliable for low-confidence neurons).

Two sign columns are kept side by side so they can be compared:
``sign`` (derived here from the neurotransmitter label) and ``ref_sign``
(the reference file's own ``Excitatory`` column). Phase 3 should use
``ref_sign`` when matching the paper exactly.

Units: positions are in nanometres, converted from FlyWire voxel coordinates
(one voxel = 4 x 4 x 40 nm).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

# ---------------------------------------------------------------------------
# Locations and pinned sources
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REF_DIR = PROJECT_ROOT / "data" / "reference"
FLYWIRE_DIR = PROJECT_ROOT / "data" / "flywire"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"

_ANN_REPO = "https://raw.githubusercontent.com/flyconnectome/flywire_annotations"


@dataclass(frozen=True)
class Snapshot:
    """One FlyWire data release and the files that describe it.

    FlyWire neuron ids (``root_id``) change whenever a neuron is edited, so
    the neuron list, the connection list and the labels must all come from
    the same release. The labels for each release are pinned to an exact
    commit of the Schlegel et al. annotation repository.
    """

    name: str
    connectivity: Path
    completeness: Path
    annotations: Path
    annotations_version: str
    annotations_url: str
    annotations_sha256: str


SNAPSHOTS: dict[str, Snapshot] = {
    # Public release 783 (Oct 2023 snapshot): the default for this project.
    "783": Snapshot(
        name="783",
        connectivity=REF_DIR / "Connectivity_783.parquet",
        completeness=REF_DIR / "Completeness_783.csv",
        annotations=FLYWIRE_DIR / "Supplemental_file1_neuron_annotations.tsv",
        annotations_version="v3.1.0",
        annotations_url=(f"{_ANN_REPO}/8587524c1748ce5ef2080822a2fc890fc03bf597"
                         "/supplemental_files/"
                         "Supplemental_file1_neuron_annotations.tsv"),
        annotations_sha256=("9a4f8b2f843196074431ebd7cd883536"
                            "afa1be86c8a4ce90970441e8be81d1be"),
    ),
    # Release 630: the snapshot the Shiu et al. 2024 paper actually used.
    # Phase 3 uses this one so the paper's neuron ids all exist.
    "630": Snapshot(
        name="630",
        connectivity=REF_DIR / "2023_03_23_connectivity_630_final.parquet",
        completeness=REF_DIR / "2023_03_23_completeness_630_final.csv",
        annotations=FLYWIRE_DIR / "Supplemental_file1_annotations_v1.1.0_630.tsv",
        annotations_version="v1.1.0",
        annotations_url=(f"{_ANN_REPO}/df6bb136f5b3d91c3992df4e8de2642329e2a384"
                         "/supplemental_files/Supplemental_file1_annotations.tsv"),
        annotations_sha256=("55c99c61eecf8db6cc36f1a684b35e4c"
                            "4208afbab02197d753ccc8dc2a6e2e76"),
    ),
}
DEFAULT_SNAPSHOT = "783"

# Backwards-friendly names for the default (783) files.
REF_CONNECTIVITY = SNAPSHOTS["783"].connectivity
REF_COMPLETENESS = SNAPSHOTS["783"].completeness
ANNOTATIONS_FILE = SNAPSHOTS["783"].annotations

# Official list of the 139,255 proofread neurons in release 783 (Zenodo,
# CC-BY 4.0). Only used for cross-checks, never needed to load.
PROOFREAD_IDS_FILE = FLYWIRE_DIR / "proofread_root_ids_783.npy"
PROOFREAD_IDS_URL = (
    "https://zenodo.org/records/10676866/files/proofread_root_ids_783.npy"
)

# Bump this whenever the cached tables change shape or meaning.
CACHE_VERSION = "phase2-v1"
_CACHE_NEURONS = "connectome_{}_neurons.parquet"
_CACHE_EDGES = "connectome_{}_edges.parquet"
_CACHE_KEY = "connectome_{}_key.json"

# FlyWire voxel size in nanometres (x, y, z).
VOXEL_NM = (4.0, 4.0, 40.0)

# ---------------------------------------------------------------------------
# Neurotransmitter -> sign (the reference paper's assumption; see docstring)
# ---------------------------------------------------------------------------
NT_SIGN: dict[str, int] = {
    "acetylcholine": +1,
    "gaba": -1,
    "glutamate": -1,
    # Modulators: the reference file treats these as excitatory.
    "dopamine": +1,
    "serotonin": +1,
    "octopamine": +1,
}
UNKNOWN_NT_SIGN = +1  # no prediction (neuron has no output synapses)

# Annotation columns carried into the neuron table.
_ANNOTATION_TEXT_COLS = [
    "flow", "super_class", "cell_class", "cell_sub_class", "cell_type",
    "hemibrain_type", "ito_lee_hemilineage", "side", "nerve", "top_nt",
    "known_nt", "synonyms",
]


def nt_to_sign(nt) -> int:
    """Return +1 (excitatory) or -1 (inhibitory) for a neurotransmitter name.

    Follows the reference paper's assumption (Shiu et al. 2024): acetylcholine
    excites; GABA and glutamate inhibit; everything else, including dopamine,
    serotonin, octopamine and a missing prediction, is treated as excitatory.
    Case-insensitive; ``"GABA"`` and ``"gaba"`` are the same.
    """
    if nt is None or (isinstance(nt, float) and np.isnan(nt)) or nt is pd.NA:
        return UNKNOWN_NT_SIGN
    return NT_SIGN.get(str(nt).strip().lower(), UNKNOWN_NT_SIGN)


def nt_series_to_sign(nt: pd.Series) -> np.ndarray:
    """Vectorised :func:`nt_to_sign` for a whole column; returns int8."""
    lowered = nt.astype("string").str.strip().str.lower()
    signs = lowered.map(NT_SIGN).astype("Float64").fillna(UNKNOWN_NT_SIGN)
    return signs.to_numpy(dtype=np.int8)


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_snapshot(version: str = DEFAULT_SNAPSHOT) -> Snapshot:
    """Look up a snapshot by name ("783" or "630")."""
    try:
        return SNAPSHOTS[str(version)]
    except KeyError:
        raise ValueError(f"unknown snapshot {version!r}; "
                         f"choose from {sorted(SNAPSHOTS)}") from None


def ensure_annotations(version: str = DEFAULT_SNAPSHOT,
                       verify: bool = False) -> Path:
    """Download the pinned Schlegel et al. annotation table if it is missing.

    No account is needed. With ``verify=True`` the file's SHA-256 checksum is
    compared with the pinned value (fails loudly if the file changed).
    """
    snap = get_snapshot(version)
    path = snap.annotations
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(snap.annotations_url, tmp)
        tmp.replace(path)
        verify = True
    if verify:
        got = _sha256(path)
        if got != snap.annotations_sha256:
            raise RuntimeError(
                f"{path} checksum {got} does not match the pinned "
                f"{snap.annotations_version} file ({snap.annotations_sha256})."
            )
    return path


def ensure_proofread_ids() -> Path:
    """Download FlyWire's official list of proofread neuron ids (1 MB)."""
    if not PROOFREAD_IDS_FILE.exists():
        FLYWIRE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PROOFREAD_IDS_FILE.with_suffix(".part")
        urllib.request.urlretrieve(PROOFREAD_IDS_URL, tmp)
        tmp.replace(PROOFREAD_IDS_FILE)
    return PROOFREAD_IDS_FILE


# ---------------------------------------------------------------------------
# The Connectome object
# ---------------------------------------------------------------------------
@dataclass
class Connectome:
    """The whole fly brain wiring diagram, ready to use.

    ``neurons``: one row per neuron. The row number *is* the neuron index used
    everywhere (matrix rows/columns, the simulator, the reference files).
    Key columns: ``root_id`` (FlyWire id), ``cell_type``, ``super_class``,
    ``top_nt`` (predicted neurotransmitter), ``sign``, ``ref_sign``,
    ``soma_x_nm``/``soma_y_nm``/``soma_z_nm`` (cell body position), and counts
    ``n_pre_partners``, ``n_post_partners``, ``in_synapses``, ``out_synapses``.

    ``edges``: one row per connection "pre -> post". Columns ``pre`` and
    ``post`` are neuron indices, ``syn_count`` is the number of synapses
    (the weight), ``sign`` is from the neurotransmitter label and
    ``ref_sign`` is the reference file's own sign.
    """

    neurons: pd.DataFrame
    edges: pd.DataFrame
    version: str = DEFAULT_SNAPSHOT
    load_seconds: float = 0.0
    from_cache: bool = False
    _matrices: dict = field(default_factory=dict, repr=False)
    _id_index: pd.Index | None = field(default=None, repr=False)

    # -- sizes ---------------------------------------------------------------
    @property
    def n_neurons(self) -> int:
        return len(self.neurons)

    @property
    def n_connections(self) -> int:
        return len(self.edges)

    @property
    def n_synapses(self) -> int:
        return int(self.edges["syn_count"].to_numpy().sum(dtype=np.int64))

    # -- id <-> index --------------------------------------------------------
    @property
    def _ids(self) -> pd.Index:
        if self._id_index is None:
            self._id_index = pd.Index(self.neurons["root_id"].to_numpy())
        return self._id_index

    def index_of(self, root_ids) -> np.ndarray:
        """FlyWire root_id(s) -> row index(es). Raises KeyError if unknown."""
        ids = np.atleast_1d(np.asarray(root_ids, dtype=np.int64))
        idx = self._ids.get_indexer(ids)
        if (idx < 0).any():
            missing = ids[idx < 0][:10].tolist()
            raise KeyError(f"root_id(s) not in the connectome: {missing}")
        return idx

    def root_id_of(self, indices) -> np.ndarray:
        """Row index(es) -> FlyWire root_id(s)."""
        return self.neurons["root_id"].to_numpy()[np.asarray(indices)]

    def neuron(self, root_id) -> pd.Series:
        """All stored information about one neuron."""
        return self.neurons.iloc[int(self.index_of(root_id)[0])]

    # -- lookups -------------------------------------------------------------
    def by_cell_type(self, name: str,
                     columns=("cell_type", "hemibrain_type")) -> pd.DataFrame:
        """Neurons whose cell type is exactly ``name`` (ignoring case)."""
        target = name.strip().lower()
        hit = np.zeros(self.n_neurons, dtype=bool)
        for col in columns:
            hit |= (self.neurons[col].astype("string").str.lower()
                    == target).fillna(False).to_numpy()
        return self.neurons[hit]

    def search(self, text: str,
               columns=("cell_type", "hemibrain_type", "cell_class",
                        "cell_sub_class", "super_class", "synonyms")
               ) -> pd.DataFrame:
        """Neurons whose name/type labels contain ``text`` (ignoring case)."""
        hit = np.zeros(self.n_neurons, dtype=bool)
        for col in columns:
            hit |= (self.neurons[col].astype("string")
                    .str.contains(text, case=False, regex=False)
                    .fillna(False).to_numpy())
        return self.neurons[hit]

    # -- matrices ------------------------------------------------------------
    def weights(self, sign_source: str = "nt") -> np.ndarray:
        """Signed weight per edge = sign x synapse count (int32).

        ``sign_source="nt"`` uses our neurotransmitter-derived sign,
        ``"reference"`` uses the reference file's own sign, ``"none"`` gives
        the plain (unsigned) synapse count.
        """
        count = self.edges["syn_count"].to_numpy(dtype=np.int32)
        if sign_source == "none":
            return count
        col = {"nt": "sign", "reference": "ref_sign"}[sign_source]
        return count * self.edges[col].to_numpy(dtype=np.int32)

    def matrix(self, sign_source: str = "nt") -> sp.csr_matrix:
        """Sparse connection matrix M, shape (n_neurons, n_neurons).

        ``M[i, j]`` = signed synapse count from neuron ``i`` (sender, row) to
        neuron ``j`` (receiver, column); 0 means "not connected". Built once
        per ``sign_source`` and then reused.
        """
        if sign_source not in self._matrices:
            n = self.n_neurons
            pre = self.edges["pre"].to_numpy()
            post = self.edges["post"].to_numpy()
            order = None
            if not (np.diff(pre) >= 0).all():  # CSR needs rows grouped
                order = np.argsort(pre, kind="stable")
                pre, post = pre[order], post[order]
            data = self.weights(sign_source)
            if order is not None:
                data = data[order]
            indptr = np.zeros(n + 1, dtype=np.int64)
            np.cumsum(np.bincount(pre, minlength=n), out=indptr[1:])
            m = sp.csr_matrix((data, post.astype(np.int32), indptr),
                              shape=(n, n))
            m.sort_indices()
            self._matrices[sign_source] = m
        return self._matrices[sign_source]

    def partners(self, root_id, direction: str = "out",
                 top: int = 10) -> pd.DataFrame:
        """Strongest partners of one neuron, by synapse count.

        ``direction="out"``: who it sends to; ``"in"``: who sends to it.
        """
        i = int(self.index_of(root_id)[0])
        col_self, col_other = (("pre", "post") if direction == "out"
                               else ("post", "pre"))
        sub = self.edges[self.edges[col_self].to_numpy() == i]
        sub = sub.nlargest(top, "syn_count")
        info = self.neurons.iloc[sub[col_other].to_numpy()][
            ["root_id", "cell_type", "super_class", "top_nt"]
        ].reset_index(drop=True)
        info.insert(1, "syn_count", sub["syn_count"].to_numpy())
        info.insert(2, "sign", sub["sign"].to_numpy())
        return info


# ---------------------------------------------------------------------------
# Building from the source files (slow path) and the parquet cache (fast)
# ---------------------------------------------------------------------------
def _source_key(version: str = DEFAULT_SNAPSHOT) -> dict:
    """Fingerprint of the inputs; the cache is reused only if it matches."""
    snap = get_snapshot(version)
    key = {"cache_version": CACHE_VERSION, "snapshot": snap.name,
           "annotations_version": snap.annotations_version}
    for p in (snap.connectivity, snap.completeness, snap.annotations):
        st = p.stat()
        key[p.name] = [st.st_size, st.st_mtime_ns]
    return key


def _load_annotations(version: str = DEFAULT_SNAPSHOT) -> pd.DataFrame:
    """Per-neuron labels. Columns missing from older releases become empty."""
    path = ensure_annotations(version)
    header = pd.read_csv(path, sep="\t", nrows=0).columns
    wanted = (["root_id", "soma_x", "soma_y", "soma_z", "pos_x", "pos_y",
               "pos_z", "top_nt_conf"] + _ANNOTATION_TEXT_COLS)
    present = [c for c in wanted if c in header]
    ann = pd.read_csv(path, sep="\t", usecols=present,
                      dtype={c: "string" for c in _ANNOTATION_TEXT_COLS
                             if c in present} | {"root_id": "int64"})
    for c in wanted:
        if c not in ann.columns:
            ann[c] = pd.array([pd.NA] * len(ann), dtype="string")
    # The v1.1.0 (630) table lists a few non-neuron fragments more than once
    # (82 rows, all super_class "not_a_neuron", none in the reference neuron
    # list). Keep one row per id so the join stays one-to-one.
    ann = ann.drop_duplicates("root_id", keep="first")
    return ann[wanted]


def build_from_sources(version: str = DEFAULT_SNAPSHOT
                       ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the reference + annotation files and build both tables."""
    snap = get_snapshot(version)
    # 1. Neuron order: exactly the reference Completeness file's order.
    comp = pd.read_csv(snap.completeness, index_col=0)
    root_ids = comp.index.to_numpy(dtype=np.int64)
    if not comp.index.is_unique:
        raise ValueError("duplicate root_ids in the reference neuron list")
    n = len(root_ids)

    # 2. Connections. Check the reference's own index columns agree with the
    #    neuron order, then keep compact integer columns only.
    con = pd.read_parquet(snap.connectivity, columns=[
        "Presynaptic_ID", "Postsynaptic_ID", "Presynaptic_Index",
        "Postsynaptic_Index", "Connectivity", "Excitatory"])
    pre = con["Presynaptic_Index"].to_numpy().astype(np.int32)
    post = con["Postsynaptic_Index"].to_numpy().astype(np.int32)
    if not (np.array_equal(root_ids[pre], con["Presynaptic_ID"].to_numpy())
            and np.array_equal(root_ids[post],
                               con["Postsynaptic_ID"].to_numpy())):
        raise ValueError("reference index columns disagree with neuron order")
    syn = con["Connectivity"].to_numpy().astype(np.int32)
    ref_sign_edge = con["Excitatory"].to_numpy().astype(np.int8)
    del con

    # 3. Per-neuron labels from the annotation table (left join: every
    #    reference neuron is kept, in order, even if it has no label).
    ann = _load_annotations(version)
    neurons = pd.DataFrame({"root_id": root_ids})
    neurons = neurons.merge(ann, on="root_id", how="left", validate="1:1",
                            indicator=True)
    neurons["in_annotations"] = neurons.pop("_merge").eq("both").to_numpy()
    for axis, scale in zip("xyz", VOXEL_NM):
        neurons[f"soma_{axis}_nm"] = (neurons.pop(f"soma_{axis}")
                                      * scale).astype("float32")
        neurons[f"anchor_{axis}_nm"] = (neurons.pop(f"pos_{axis}")
                                        * scale).astype("float32")
    neurons["top_nt_conf"] = neurons["top_nt_conf"].astype("float32")
    neurons["sign"] = nt_series_to_sign(neurons["top_nt"])

    # Reference sign per neuron (0 = neuron sends no connections).
    ref_sign = np.zeros(n, dtype=np.int8)
    ref_sign[pre] = ref_sign_edge
    neurons["ref_sign"] = ref_sign

    # Degree and synapse totals.
    neurons["n_post_partners"] = np.bincount(pre, minlength=n).astype(np.int32)
    neurons["n_pre_partners"] = np.bincount(post, minlength=n).astype(np.int32)
    neurons["out_synapses"] = np.bincount(pre, weights=syn,
                                          minlength=n).astype(np.int64)
    neurons["in_synapses"] = np.bincount(post, weights=syn,
                                         minlength=n).astype(np.int64)

    edges = pd.DataFrame({
        "pre": pre, "post": post, "syn_count": syn,
        "sign": neurons["sign"].to_numpy()[pre],
        "ref_sign": ref_sign_edge,
    })
    return neurons, edges


def _cache_paths(cache_dir: Path, version: str):
    d = Path(cache_dir)
    return (d / _CACHE_NEURONS.format(version), d / _CACHE_EDGES.format(version),
            d / _CACHE_KEY.format(version))


def write_cache(neurons: pd.DataFrame, edges: pd.DataFrame, key: dict,
                cache_dir: Path = CACHE_DIR,
                version: str = DEFAULT_SNAPSHOT) -> None:
    """Save both tables as parquet plus a small fingerprint file."""
    p_neu, p_edg, p_key = _cache_paths(cache_dir, version)
    p_neu.parent.mkdir(parents=True, exist_ok=True)
    p_key.unlink(missing_ok=True)  # never leave a key next to half a cache
    neurons.to_parquet(p_neu, index=False)
    edges.to_parquet(p_edg, index=False, compression="zstd")
    p_key.write_text(json.dumps(key, indent=1))


def read_cache(key: dict, cache_dir: Path = CACHE_DIR,
               version: str = DEFAULT_SNAPSHOT):
    """Return (neurons, edges) from the cache, or None if stale/missing."""
    p_neu, p_edg, p_key = _cache_paths(cache_dir, version)
    try:
        stored = json.loads(p_key.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if stored != key:
        return None
    try:
        return pd.read_parquet(p_neu), pd.read_parquet(p_edg)
    except (FileNotFoundError, OSError):
        return None


def load_connectome(version: str = DEFAULT_SNAPSHOT, rebuild: bool = False,
                    cache_dir: Path = CACHE_DIR) -> Connectome:
    """Load the whole fly brain. Uses the parquet cache when it is current.

    ``version``: "783" (default, the public release the labels are made for)
    or "630" (the release the Shiu et al. 2024 paper used; use it in Phase 3
    so the paper's neuron ids exist). ``rebuild=True`` ignores the cache,
    rebuilds from the source files and rewrites the cache.
    """
    version = get_snapshot(version).name
    t0 = time.perf_counter()
    ensure_annotations(version)
    key = _source_key(version)
    cached = None if rebuild else read_cache(key, cache_dir, version)
    if cached is None:
        neurons, edges = build_from_sources(version)
        write_cache(neurons, edges, key, cache_dir, version)
        from_cache = False
    else:
        neurons, edges = cached
        from_cache = True
    return Connectome(neurons=neurons, edges=edges, version=version,
                      load_seconds=time.perf_counter() - t0,
                      from_cache=from_cache)
