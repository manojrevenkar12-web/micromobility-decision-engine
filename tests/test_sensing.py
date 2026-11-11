"""The riding-safety model and the ride policy around it."""

import hashlib
from pathlib import Path

import numpy as np
import torch

from mde.sensing.model import RideNet, fit, predict
from mde.world import imu

ROOT = Path(__file__).resolve().parents[1]


def test_model_shapes_and_a_quick_fit_beats_chance():
    torch.set_num_threads(1)
    X, ys, yt = imu.dataset(800, "gen6", "dev", 9)
    m = RideNet(width=16)
    fit(m, X, ys, yt, epochs=6, lr=0.01, batch=64, seed=0)
    ps, pt = predict(m, X)
    assert ps.shape == (800, 3) and pt.shape == (800,)
    majority = np.bincount(ys).max() / len(ys)
    assert (ps.argmax(1) == ys).mean() > majority + 0.15


def test_ride_policy_needs_consecutive_windows():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from sensing_eval import ride_policy

    p = np.array([0.9, 0.1, 0.9, 0.9, 0.9, 0.9, 0.1])
    assert ride_policy(p, 0.5, 3).tolist() == [False, False, False, False, True, True, False]


def test_onnx_export_matches_torch(tmp_path):
    m = RideNet(width=8).eval()
    x = torch.randn(2, 5, imu.WINDOW)
    torch.onnx.export(m, x[:1], str(tmp_path / "m.onnx"), input_names=["imu"], opset_version=17, dynamo=False)
    import onnxruntime as ort

    s = ort.InferenceSession(str(tmp_path / "m.onnx"), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = m(x[:1])[0].numpy()
    assert np.abs(s.run(None, {"imu": x[:1].numpy()})[0] - ref).max() < 1e-4


def test_heldout_is_pinned():
    lock = (ROOT / "config" / "heldout.lock").read_text().split()
    files = [ROOT / "config" / "world.toml", ROOT / "src" / "mde" / "world" / "imu.py"]
    assert lock == [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
