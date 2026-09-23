"""Phase 2: the fly brain loader (sim/connectome.py).

Fast tests use a made-up 4-neuron brain. Tests marked ``slow`` load the whole
FlyWire connectome (snapshots 783 and 630) from data/ (``pytest -m slow``).
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from sim import connectome as C


# ---------------------------------------------------------------------------
# Neurotransmitter -> sign
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nt, expected", [
    ("acetylcholine", +1),
    ("gaba", -1),
    ("GABA", -1),
    ("glutamate", -1),
    (" Glutamate ", -1),
    ("dopamine", +1),     # reference convention: modulators count as +1
    ("serotonin", +1),
    ("octopamine", +1),
    ("histamine", +1),    # not in the table -> default
    (None, +1),           # no prediction -> default
    (float("nan"), +1),
    (pd.NA, +1),
])
def test_nt_to_sign_known_examples(nt, expected):
    assert C.nt_to_sign(nt) == expected


def test_nt_series_to_sign_matches_scalar_version():
    names = pd.Series(["acetylcholine", "gaba", "glutamate", "dopamine",
                       None, "Serotonin", "octopamine"], dtype="string")
    got = C.nt_series_to_sign(names)
    assert got.dtype == np.int8
    assert got.tolist() == [C.nt_to_sign(x) for x in names.tolist()]
    assert got.tolist() == [1, -1, -1, 1, 1, 1, 1]


# ---------------------------------------------------------------------------
# A tiny made-up brain to test the Connectome object without the real data
# ---------------------------------------------------------------------------
def _tiny():
    neurons = pd.DataFrame({
        "root_id": np.array([720575940000000010, 720575940000000020,
                             720575940000000030, 720575940000000040],
                            dtype=np.int64),
        "cell_type": pd.array(["KCg-m", "APL", "MBON11", pd.NA],
                              dtype="string"),
        "hemibrain_type": pd.array([pd.NA, "APL", "MBON11", pd.NA],
                                   dtype="string"),
        "cell_class": pd.array(["Kenyon_Cell", "MB_extrinsic",
                                "MBON", pd.NA], dtype="string"),
        "cell_sub_class": pd.array([pd.NA] * 4, dtype="string"),
        "super_class": pd.array(["central"] * 3 + ["optic"], dtype="string"),
        "synonyms": pd.array([pd.NA, "anterior paired lateral", pd.NA,
                              pd.NA], dtype="string"),
        "top_nt": pd.array(["acetylcholine", "gaba", "glutamate", pd.NA],
                           dtype="string"),
    })
    neurons["sign"] = C.nt_series_to_sign(neurons["top_nt"])
    neurons["ref_sign"] = np.array([1, -1, 1, 0], dtype=np.int8)
    edges = pd.DataFrame({
        "pre": np.array([0, 0, 1, 2], dtype=np.int32),
        "post": np.array([1, 2, 0, 3], dtype=np.int32),
        "syn_count": np.array([5, 7, 3, 2], dtype=np.int32),
    })
    edges["sign"] = neurons["sign"].to_numpy()[edges["pre"]]
    edges["ref_sign"] = neurons["ref_sign"].to_numpy()[edges["pre"]]
    return C.Connectome(neurons=neurons, edges=edges)


def test_id_index_round_trip_small():
    c = _tiny()
    ids = c.neurons["root_id"].to_numpy()
    assert c.index_of(ids).tolist() == [0, 1, 2, 3]
    assert c.root_id_of(c.index_of(ids[::-1])).tolist() == ids[::-1].tolist()
    assert c.index_of(ids[2]).tolist() == [2]            # single id works too
    assert c.neuron(ids[1])["cell_type"] == "APL"


def test_unknown_root_id_raises():
    with pytest.raises(KeyError):
        _tiny().index_of([123])


def test_matrix_is_signed_synapse_count():
    c = _tiny()
    m = c.matrix("nt").toarray()
    assert m.shape == (4, 4)
    assert m[0, 1] == 5 and m[0, 2] == 7      # acetylcholine: +
    assert m[1, 0] == -3                      # GABA: -
    assert m[2, 3] == -2                      # glutamate: -
    assert (m != 0).sum() == c.n_connections
    assert c.matrix("reference").toarray()[2, 3] == 2   # ref file says +
    assert c.matrix("none").sum() == c.n_synapses == 17


def test_lookups_small():
    c = _tiny()
    assert c.by_cell_type("apl")["root_id"].tolist() == [720575940000000020]
    assert len(c.by_cell_type("nope")) == 0
    assert set(c.search("mbon")["cell_type"]) == {"MBON11"}
    assert c.search("paired lateral")["cell_type"].tolist() == ["APL"]
    out = c.partners(720575940000000010, "out")
    assert out["syn_count"].tolist() == [7, 5]


def test_cache_round_trip_small(tmp_path):
    c = _tiny()
    key = {"cache_version": "test", "x": [1, 2]}
    C.write_cache(c.neurons, c.edges, key, tmp_path)
    got = C.read_cache(key, tmp_path)
    assert got is not None
    pd.testing.assert_frame_equal(got[0], c.neurons)
    pd.testing.assert_frame_equal(got[1], c.edges)
    # A changed source file (different key) must not reuse the old cache.
    assert C.read_cache({"cache_version": "test", "x": [1, 3]},
                        tmp_path) is None
    assert C.read_cache(key, tmp_path / "missing") is None


# ---------------------------------------------------------------------------
# The real brain (slow: loads 15 million connections)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def brain():
    return C.load_connectome()


@pytest.mark.slow
def test_full_shapes_and_dtypes(brain):
    comp = pd.read_csv(C.REF_COMPLETENESS, index_col=0)
    assert brain.n_neurons == len(comp) == 138_639
    assert brain.n_connections == 15_091_983
    assert brain.n_synapses == 54_492_922
    e = brain.edges
    assert list(e.columns) == ["pre", "post", "syn_count", "sign", "ref_sign"]
    assert e["pre"].dtype == np.int32 and e["post"].dtype == np.int32
    assert e["syn_count"].dtype == np.int32
    assert e["sign"].dtype == np.int8 and e["ref_sign"].dtype == np.int8
    assert e["pre"].min() >= 0 and e["pre"].max() < brain.n_neurons
    assert e["post"].min() >= 0 and e["post"].max() < brain.n_neurons
    assert e["syn_count"].min() >= 1
    assert set(np.unique(e["sign"])) == {-1, 1}
    assert brain.neurons["root_id"].dtype == np.int64
    assert brain.neurons["root_id"].is_unique


@pytest.mark.slow
def test_full_index_order_matches_reference(brain):
    comp = pd.read_csv(C.REF_COMPLETENESS, index_col=0)
    ids = brain.neurons["root_id"].to_numpy()
    assert np.array_equal(ids, comp.index.to_numpy())
    idx = np.arange(brain.n_neurons)
    assert np.array_equal(brain.index_of(brain.root_id_of(idx)), idx)
    # First row of the reference connection file, by id and by index.
    # (read one row group only, not the whole 1 GB table)
    ref = pq.ParquetFile(C.REF_CONNECTIVITY).read_row_group(
        0, columns=["Presynaptic_ID", "Postsynaptic_ID", "Presynaptic_Index",
                    "Postsynaptic_Index"]).slice(0, 1).to_pandas()
    assert brain.index_of(ref["Presynaptic_ID"])[0] == \
        ref["Presynaptic_Index"].iloc[0]
    assert brain.index_of(ref["Postsynaptic_ID"])[0] == \
        ref["Postsynaptic_Index"].iloc[0]


@pytest.mark.slow
def test_full_signs_on_known_neurons(brain):
    # APL: the big GABA neuron of the mushroom body -> inhibitory.
    apl = brain.by_cell_type("APL")
    assert len(apl) == 2
    assert (apl["sign"] == -1).all() and (apl["ref_sign"] == -1).all()
    # Labellar sugar-sensing taste neurons (Shiu et al. Fig. 1 inputs):
    # cholinergic -> excitatory.
    sugar = brain.neurons.iloc[brain.index_of(
        [720575940624963786, 720575940630233916, 720575940637568838])]
    assert (sugar["cell_sub_class"] == "sugar/water").all()
    assert (sugar["sign"] == 1).all() and (sugar["ref_sign"] == 1).all()
    # Edge signs are the sender's sign.
    e = brain.edges.iloc[:1000]
    assert np.array_equal(e["sign"].to_numpy(),
                          brain.neurons["sign"].to_numpy()[e["pre"]])


@pytest.mark.slow
def test_full_matrix_matches_edges(brain):
    m = brain.matrix("nt")
    assert m.shape == (brain.n_neurons, brain.n_neurons)
    assert m.nnz == brain.n_connections
    e = brain.edges.iloc[123_456]
    assert m[int(e["pre"]), int(e["post"])] == int(e["sign"]) * int(
        e["syn_count"])
    assert int(abs(brain.matrix("reference")).sum()) == brain.n_synapses


@pytest.mark.slow
def test_full_sign_agreement_with_reference(brain):
    senders = brain.neurons[brain.neurons["ref_sign"] != 0]
    agree = (senders["sign"] == senders["ref_sign"]).mean()
    assert agree > 0.95


@pytest.mark.slow
def test_full_cache_round_trip(tmp_path, brain):
    cold = C.load_connectome(rebuild=True, cache_dir=tmp_path)
    assert not cold.from_cache
    warm = C.load_connectome(cache_dir=tmp_path)
    assert warm.from_cache
    pd.testing.assert_frame_equal(warm.edges, cold.edges)
    pd.testing.assert_frame_equal(warm.neurons, cold.neurons,
                                  check_dtype=False)
    pd.testing.assert_frame_equal(warm.edges, brain.edges)


def test_cache_versions_do_not_collide(tmp_path):
    c = _tiny()
    key = {"cache_version": "test"}
    C.write_cache(c.neurons, c.edges, key, tmp_path, version="783")
    assert C.read_cache(key, tmp_path, version="630") is None
    assert C.read_cache(key, tmp_path, version="783") is not None


def test_unknown_snapshot_rejected():
    assert C.get_snapshot("630").name == "630"
    with pytest.raises(ValueError):
        C.get_snapshot("999")


@pytest.mark.slow
def test_full_snapshot_630_loads_with_paper_ids(brain):
    b = C.load_connectome("630")
    assert b.version == "630"
    assert b.n_neurons == 127_400          # the paper's neuron count
    assert b.n_connections == 14_687_178
    comp = pd.read_csv(C.get_snapshot("630").completeness, index_col=0)
    assert np.array_equal(b.neurons["root_id"].to_numpy(),
                          comp.index.to_numpy())
    # Paper ids that exist in 630 but not in 783 (docs/reference-notes.md):
    # a sugar GRN and the second MN9.
    for rid in (720575940620900446, 720575940645521262):
        assert b.index_of(rid).size == 1
        with pytest.raises(KeyError):
            brain.index_of(rid)                   # brain = snapshot 783
    # The main MN9 exists in both.
    assert b.index_of(720575940660219265).size == 1
    assert b.neurons["root_id"].dtype == np.int64
