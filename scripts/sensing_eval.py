"""Train and score the on-scooter riding-safety model -> reports/sensing_dev.json (and sensing_heldout.json).

dev:      gen6 hardware, dev-city pavements; the slowdown threshold is chosen on val, scored on dev-test
heldout:  gen7 hardware (stiffer mount, noisier sensor) in the held-out city's pavements, once

The scooter acts on rides, not windows: it warns and slows after `consecutive` sidewalk windows in a row.
Ride-level scores: share of sidewalk stretches caught, seconds to catch them, and false slowdowns per 100 km
of legal riding.
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from mde import config
from mde.sensing.model import RideNet, fit, predict
from mde.world import imu

MODEL = config.DATA / "sensing" / "ridenet.pt"


def rides(n: int, length: int, hw: str, city: str, seed: int):
    """Ride sequences: road with sidewalk and cobblestone stretches (Markov), some rides two-up."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        tandem = rng.random() < 0.12
        s, seq = 0, []
        for _ in range(length):
            u = rng.random()
            if s == 0:
                s = 1 if u < 0.03 else (2 if u < 0.045 else 0)
            elif s == 1:
                s = 0 if u < 0.12 else 1
            else:
                s = 0 if u < 0.2 else 2
            seq.append(s)
        X = np.stack([imu.window(si, tandem, imu.HARDWARE[hw], imu.CITIES[city], rng) for si in seq])
        out.append((X, np.array(seq), tandem))
    return out


def ride_policy(p_side: np.ndarray, tau: float, k: int) -> np.ndarray:
    """Slow-down state per window: on after k consecutive windows over tau, off after one below."""
    over = p_side >= tau
    run = np.zeros(len(over), int)
    for i, o in enumerate(over):
        run[i] = run[i - 1] + 1 if (o and i) else int(o)
    return run >= k


def ride_scores(model, ride_set, tau: float, k: int) -> dict:
    caught, delays, n_stretch, false_on, legal_km, tandem_p, tandem_y = 0, [], 0, 0, 0.0, [], []
    for X, seq, tandem in ride_set:
        ps, pt = predict(model, X)
        slow = ride_policy(ps[:, 1], tau, k)
        km = X[:, 4, :].mean(axis=1) / 3.6 * 2 / 1000          # km per window
        legal = seq != 1
        legal_km += float(km[legal].sum())
        starts = np.where(slow & ~np.concatenate([[False], slow[:-1]]))[0]
        false_on += int(sum(1 for i in starts if seq[i] != 1))
        i = 0
        while i < len(seq):
            if seq[i] == 1:
                j = i
                while j < len(seq) and seq[j] == 1:
                    j += 1
                if j - i >= 5:                                   # stretches of 10 s or more
                    n_stretch += 1
                    hit = np.where(slow[i:j])[0]
                    if len(hit):
                        caught += 1
                        delays.append(2 * (hit[0] + 1))
                i = j
            else:
                i += 1
        tandem_p.append(float(np.median(pt)))
        tandem_y.append(int(tandem))
    return {"sidewalk_stretches": n_stretch, "caught_share": caught / max(1, n_stretch),
            "median_seconds_to_catch": float(np.median(delays)) if delays else None,
            "false_slowdowns_per_100km": 100 * false_on / max(legal_km, 1e-9), "legal_km": legal_km,
            "ride_tandem_auroc": float(roc_auc_score(tandem_y, tandem_p)) if len(set(tandem_y)) > 1 else None}


def choose_tau(model, val_rides, k: int, limit: float) -> float:
    for tau in np.round(np.arange(0.30, 0.995, 0.01), 2):
        if ride_scores(model, val_rides, float(tau), k)["false_slowdowns_per_100km"] <= limit:
            return float(tau)
    return 0.99


def window_scores(model, X, ys, yt, tandem_tau: float | None = None) -> dict:
    ps, pt = predict(model, X)
    pred = ps.argmax(1)
    out = {"surface_macro_f1": float(f1_score(ys, pred, average="macro")),
           "sidewalk_precision": float(precision_score(ys == 1, pred == 1)),
           "sidewalk_recall": float(recall_score(ys == 1, pred == 1)),
           "tandem_auroc": float(roc_auc_score(yt, pt))}
    if tandem_tau is not None:
        out["tandem_precision"] = float(precision_score(yt, pt >= tandem_tau, zero_division=0))
        out["tandem_recall"] = float(recall_score(yt, pt >= tandem_tau))
    return out, pt


def export(model: RideNet, X_cal: np.ndarray) -> dict:
    path = config.DATA / "sensing"
    fp, q = path / "ridenet.onnx", path / "ridenet.int8.onnx"
    torch.onnx.export(model, torch.from_numpy(X_cal[:1]), str(fp), input_names=["imu"], output_names=["surface", "tandem"],
                      opset_version=17, dynamo=False)

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.it = iter([{"imu": X_cal[i : i + 1]} for i in range(200)])

        def get_next(self):
            return next(self.it, None)

    quantize_static(str(fp), str(q), Reader(), quant_format=QuantFormat.QDQ, activation_type=QuantType.QInt8,
                    weight_type=QuantType.QInt8)
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    res = {"params": int(sum(p.numel() for p in model.parameters())), "onnx_kb": fp.stat().st_size / 1024,
           "int8_kb": q.stat().st_size / 1024}
    for name, f in (("float", fp), ("int8", q)):
        s = ort.InferenceSession(str(f), so, providers=["CPUExecutionProvider"])
        t0 = time.perf_counter()
        for i in range(300):
            s.run(None, {"imu": X_cal[i % len(X_cal) : i % len(X_cal) + 1]})
        res[f"{name}_ms_per_window"] = (time.perf_counter() - t0) / 300 * 1000
    return res


def int8_agreement(X: np.ndarray) -> float:
    s = ort.InferenceSession(str(config.DATA / "sensing" / "ridenet.int8.onnx"), providers=["CPUExecutionProvider"])
    f = ort.InferenceSession(str(config.DATA / "sensing" / "ridenet.onnx"), providers=["CPUExecutionProvider"])
    a = np.concatenate([s.run(None, {"imu": X[i : i + 1]})[0].argmax(1) for i in range(len(X))])
    b = np.concatenate([f.run(None, {"imu": X[i : i + 1]})[0].argmax(1) for i in range(len(X))])
    return float((a == b).mean())


def main(split: str) -> None:
    c = config.decide()["sensing"]
    torch.set_num_threads(2)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    if split == "dev":
        X, ys, yt = imu.dataset(c["train_windows"], "gen6", "dev", 1)
        model = RideNet()
        losses = fit(model, X, ys, yt, c["epochs"], c["lr"], c["batch"], c["seed"])
        torch.save(model.state_dict(), MODEL)
        Xv, ysv, ytv = imu.dataset(c["val_windows"], "gen6", "dev", 2)
        val_rides = rides(c["rides"] // 2, c["ride_windows"], "gen6", "dev", 12)
        tau = choose_tau(model, val_rides, c["consecutive"], c["max_false_slowdowns_per_100km"])
        _, ptv = predict(model, Xv)
        target = c["tandem_precision_target"]
        cands = [t for t in np.arange(0.5, 0.99, 0.01) if precision_score(ytv, ptv >= t, zero_division=0) >= target]
        tandem_tau = float(min(cands)) if cands else 0.99
        Xt, yst, ytt = imu.dataset(c["test_windows"], "gen6", "dev", 3)
        win, _ = window_scores(model, Xt, yst, ytt, tandem_tau)
        ride = ride_scores(model, rides(c["rides"], c["ride_windows"], "gen6", "dev", 13), tau, c["consecutive"])
        edge = export(model, Xv[:400])
        edge["int8_top1_agreement"] = int8_agreement(Xt[:1000])
        out = {"split": "dev-test", "hardware": "gen6", "train_loss": losses, "slowdown_threshold": tau,
               "tandem_threshold": tandem_tau, "windows": win, "rides": ride, "edge": edge}
        (config.REPORTS / "sensing_thresholds.json").write_text(json.dumps({"slowdown": tau, "tandem": tandem_tau}))
    else:
        model = RideNet()
        model.load_state_dict(torch.load(MODEL, weights_only=True))
        model.eval()
        th = json.loads((config.REPORTS / "sensing_thresholds.json").read_text())
        Xh, ysh, yth = imu.dataset(c["test_windows"], "gen7", "heldout", 4)
        win, _ = window_scores(model, Xh, ysh, yth, th["tandem"])
        ride = ride_scores(model, rides(c["rides"], c["ride_windows"], "gen7", "heldout", 14), th["slowdown"], c["consecutive"])
        out = {"split": "heldout", "hardware": "gen7", "slowdown_threshold": th["slowdown"], "windows": win, "rides": ride}
    (config.REPORTS / f"sensing_{split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "train_loss"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
