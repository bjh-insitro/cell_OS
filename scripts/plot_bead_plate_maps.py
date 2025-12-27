#!/usr/bin/env python3
import argparse
import json
import math
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

WELL_RE_384 = re.compile(r"^([A-P])(\d{1,2})$")  # 16 rows (A-P), 24 cols (1-24)

CHANNELS = ["er", "mito", "nucleus", "actin", "rna"]


def well_to_rc(well_id: str) -> tuple[int, int]:
    m = WELL_RE_384.match(well_id.strip())
    if not m:
        raise ValueError(f"Bad well_id for 384 plate: {well_id}")
    r = ord(m.group(1)) - ord("A")
    c = int(m.group(2)) - 1
    if not (0 <= r < 16 and 0 <= c < 24):
        raise ValueError(f"Well out of 384 bounds: {well_id}")
    return r, c


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def plate_array(records: list[dict], value_fn, default=np.nan) -> np.ndarray:
    arr = np.full((16, 24), default, dtype=float)
    for r in records:
        well = r.get("well_id") or r.get("well_position")
        if not well:
            continue
        rr, cc = well_to_rc(well)
        arr[rr, cc] = value_fn(r)
    return arr


def save_heatmap(arr: np.ndarray, title: str, outpath: Path) -> None:
    plt.figure()
    plt.imshow(arr, aspect="auto")
    plt.title(title)
    plt.xlabel("Column (1–24)")
    plt.ylabel("Row (A–P)")
    plt.colorbar()
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, dpi=200)
    plt.close()


def any_channel_saturated(det_md: dict) -> float:
    # Try a few common shapes
    if det_md is None:
        return np.nan
    v = det_md.get("is_saturated")
    if v is None:
        v = det_md.get("saturated")
    if isinstance(v, dict):
        return float(any(bool(x) for x in v.values()))
    if v is None:
        return np.nan
    return float(bool(v))


def get_snr_floor_proxy(det_md: dict) -> float:
    if det_md is None:
        return np.nan
    v = det_md.get("snr_floor_proxy")
    if v is None:
        return np.nan
    try:
        return float(v)
    except Exception:
        return np.nan


def safe_mean(xs: list[float]) -> float:
    vals = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return float(np.mean(vals)) if vals else float("nan")


def safe_cv(xs: list[float]) -> float:
    vals = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(vals) < 2:
        return float("nan")
    m = float(np.mean(vals))
    if m == 0.0:
        return float("nan")
    s = float(np.std(vals, ddof=1))
    return s / m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to observations.jsonl")
    ap.add_argument("--outdir", required=True, help="Directory to write plots + summary")
    args = ap.parse_args()

    inpath = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    records = read_jsonl(inpath)
    if len(records) != 384:
        print(f"Warning: expected 384 records, found {len(records)}")

    # Heatmaps for morphology channels
    for ch in CHANNELS:
        arr = plate_array(
            records,
            lambda r, ch=ch: float((r.get("morphology") or {}).get(ch, np.nan))
        )
        save_heatmap(arr, f"{ch} intensity", outdir / f"plate_{ch}.png")

    # Saturation heatmap (any channel)
    sat = plate_array(records, lambda r: any_channel_saturated(r.get("detector_metadata") or {}))
    save_heatmap(sat, "Saturation flag (any channel)", outdir / "plate_saturation_any.png")

    # SNR floor proxy heatmap
    snr = plate_array(records, lambda r: get_snr_floor_proxy(r.get("detector_metadata") or {}))
    save_heatmap(snr, "SNR floor proxy", outdir / "plate_snr_floor_proxy.png")

    # Summary stats by material assignment (or fallback token)
    buckets = defaultdict(list)
    for r in records:
        mat = (
            r.get("material_assignment")
            or r.get("material")
            or r.get("compound")  # if you overloaded it
            or "UNKNOWN"
        )
        buckets[str(mat)].append(r)

    # Build CSV
    lines = []
    header = ["material", "n_wells"] + [f"{ch}_mean" for ch in CHANNELS] + [f"{ch}_cv" for ch in CHANNELS] + [
        "saturation_frac_any",
        "snr_floor_proxy_mean",
    ]
    lines.append(",".join(header))

    for mat, recs in sorted(buckets.items(), key=lambda x: x[0]):
        n = len(recs)
        ch_vals = {ch: [] for ch in CHANNELS}
        sat_vals = []
        snr_vals = []

        for r in recs:
            morph = r.get("morphology") or {}
            for ch in CHANNELS:
                v = morph.get(ch)
                if v is None:
                    continue
                ch_vals[ch].append(float(v))

            md = r.get("detector_metadata") or {}
            s = any_channel_saturated(md)
            if not (isinstance(s, float) and math.isnan(s)):
                sat_vals.append(s)

            p = get_snr_floor_proxy(md)
            if not (isinstance(p, float) and math.isnan(p)):
                snr_vals.append(p)

        row = [mat, str(n)]
        for ch in CHANNELS:
            row.append(f"{safe_mean(ch_vals[ch]):.6g}")
        for ch in CHANNELS:
            row.append(f"{safe_cv(ch_vals[ch]):.6g}")

        sat_frac = float(np.mean(sat_vals)) if sat_vals else float("nan")
        row.append(f"{sat_frac:.6g}")

        row.append(f"{safe_mean(snr_vals):.6g}")
        lines.append(",".join(row))

    csv_path = outdir / "material_summary.csv"
    csv_path.write_text("\n".join(lines))

    print(f"Wrote plots to: {outdir}")
    print(f"Wrote summary to: {csv_path}")


if __name__ == "__main__":
    main()
