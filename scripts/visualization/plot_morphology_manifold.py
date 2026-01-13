from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

try:
    import umap  # pip install umap-learn
except Exception:
    umap = None


CHANNELS = ["er", "mito", "nucleus", "actin", "rna"]


def _load_records(path: Path) -> List[Dict[str, Any]]:
    with path.open("r") as f:
        obj = json.load(f)

    # Support either {"wells":[...]} or a raw list or {"observations":[...]}
    if isinstance(obj, list):
        return obj
    for k in ["wells", "observations", "records", "results"]:
        if k in obj and isinstance(obj[k], list):
            return obj[k]
    # Try raw_results as fallback
    if "raw_results" in obj:
        return obj["raw_results"]
    raise ValueError(f"Unrecognized JSON schema in {path}")


def _to_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for r in records:
        morph = r.get("morphology", {}) or {}
        row = {
            "well_id": r.get("well_id"),
            "row": r.get("row"),
            "col": r.get("col"),
            "cell_line": r.get("cell_line"),
            "compound": r.get("compound") or r.get("treatment"),
            "dose_uM": r.get("dose_uM", 0.0),
            "time_h": r.get("time_h", r.get("timepoint_hours", None)),
        }
        ok = True
        for ch in CHANNELS:
            v = morph.get(ch, None)
            if v is None:
                ok = False
                break
            row[ch] = float(v)
        if not ok:
            continue
        rows.append(row)

    df = pd.DataFrame(rows)

    # Filter out NO_CELLS and NONE line
    df = df[df["cell_line"].notna()]
    df = df[df["compound"].notna()]
    df = df[df["cell_line"] != "NONE"]
    df = df[df["compound"] != "NO_CELLS"]

    # Coerce dose
    df["dose_uM"] = pd.to_numeric(df["dose_uM"], errors="coerce").fillna(0.0)

    return df


def _compute_embeddings(X: np.ndarray, seed: int = 42) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}

    pca = PCA(n_components=3, random_state=seed)
    Z = pca.fit_transform(X)
    out["pca"] = Z
    out["pca_var"] = pca.explained_variance_ratio_

    if umap is not None:
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=15,
            min_dist=0.1,
            metric="euclidean",
            random_state=seed,
        )
        out["umap"] = reducer.fit_transform(X)
    else:
        out["umap"] = None

    return out


def _centroids(df: pd.DataFrame, Z_umap: np.ndarray | None) -> pd.DataFrame:
    # condition = (cell_line, compound, dose_uM)
    g = df.groupby(["cell_line", "compound", "dose_uM"], as_index=False)
    cent = g[CHANNELS].mean()
    cent = cent.sort_values(["cell_line", "compound", "dose_uM"])

    if Z_umap is not None:
        # Map centroid coords by averaging member well coords
        df2 = df.copy()
        df2["umap1"] = Z_umap[:, 0]
        df2["umap2"] = Z_umap[:, 1]
        cent2 = df2.groupby(["cell_line", "compound", "dose_uM"], as_index=False)[["umap1", "umap2"]].mean()
        cent = cent.merge(cent2, on=["cell_line", "compound", "dose_uM"], how="left")

    return cent


def _geometry_metrics(df: pd.DataFrame, X: np.ndarray) -> Dict[str, Any]:
    # replicate spread: within-condition distance to centroid
    cond_keys = ["cell_line", "compound", "dose_uM"]
    df_idx = df[cond_keys].astype(str).agg("|".join, axis=1).values

    # centroid in feature space
    cent = df.groupby(cond_keys)[CHANNELS].mean()
    # Handle MultiIndex properly
    cent_idx = ["|".join(map(str, idx)) for idx in cent.index]
    cent_map = {k: cent.iloc[i].values for i, k in enumerate(cent_idx)}

    d_within = []
    for i, key in enumerate(df_idx):
        c = cent_map.get(key)
        if c is None:
            continue
        d_within.append(float(np.linalg.norm(X[i] - c)))

    # condition separation: nearest neighbor between condition centroids
    C = cent.values
    if len(C) >= 2:
        D = np.sqrt(((C[:, None, :] - C[None, :, :]) ** 2).sum(axis=2))
        D += np.eye(len(C)) * 1e9
        nn = D.min(axis=1)
        separation_median = float(np.median(nn))
    else:
        separation_median = None

    spread_median = float(np.median(d_within)) if d_within else None
    ratio = None
    if separation_median is not None and spread_median not in (None, 0.0):
        ratio = float(separation_median / spread_median)

    return {
        "n_wells": int(len(df)),
        "n_conditions": int(cent.shape[0]),
        "replicate_spread_median": spread_median,
        "condition_separation_median": separation_median,
        "separation_over_spread": ratio,
    }


def main():
    in_path = Path("results/calibration_plates/CAL_384_RULES_WORLD_v2_results_seed42.json")
    out_dir = Path("results/manifold")
    out_dir.mkdir(parents=True, exist_ok=True)

    records = _load_records(in_path)
    df = _to_df(records)

    # Features
    Xraw = df[CHANNELS].values.astype(float)

    # Optional log1p to reduce skew
    X = np.log1p(Xraw)

    X = StandardScaler().fit_transform(X)

    emb = _compute_embeddings(X, seed=42)
    Zp = emb["pca"]
    Zumap = emb["umap"]

    cent = _centroids(df, Zumap)
    metrics = _geometry_metrics(df, X)

    # Plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # PCA by cell line
    ax = axes[0, 0]
    for cl in sorted(df["cell_line"].unique()):
        m = df["cell_line"] == cl
        ax.scatter(Zp[m, 0], Zp[m, 1], s=14, alpha=0.6, label=cl)
    ax.set_title("PCA PC1 vs PC2 (colored by cell_line)")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(loc="best", fontsize=9)

    # PCA by compound
    ax = axes[0, 1]
    for comp in sorted(df["compound"].unique()):
        m = df["compound"] == comp
        ax.scatter(Zp[m, 1], Zp[m, 2], s=14, alpha=0.6, label=comp)
    ax.set_title("PCA PC2 vs PC3 (colored by compound)")
    ax.set_xlabel("PC2")
    ax.set_ylabel("PC3")
    ax.legend(loc="best", fontsize=9)

    # UMAP by compound
    ax = axes[1, 0]
    if Zumap is None:
        ax.text(0.5, 0.5, "UMAP not available. pip install umap-learn", ha="center", va="center")
        ax.axis("off")
    else:
        for comp in sorted(df["compound"].unique()):
            m = df["compound"] == comp
            ax.scatter(Zumap[m, 0], Zumap[m, 1], s=14, alpha=0.6, label=comp)
        ax.set_title("UMAP (colored by compound)")
        ax.set_xlabel("UMAP1")
        ax.set_ylabel("UMAP2")
        ax.legend(loc="best", fontsize=9)

    # UMAP trajectories
    ax = axes[1, 1]
    if Zumap is None:
        ax.axis("off")
    else:
        ax.scatter(Zumap[:, 0], Zumap[:, 1], s=10, alpha=0.15, color='gray')

        # centroid points + dose lines per (cell_line, compound)
        for (cl, comp), sub in cent.groupby(["cell_line", "compound"]):
            sub = sub.dropna(subset=["umap1", "umap2"]).sort_values("dose_uM")
            if len(sub) < 2:
                continue
            ax.plot(sub["umap1"].values, sub["umap2"].values, linewidth=2, alpha=0.9, label=f"{cl}/{comp}")
            ax.scatter(sub["umap1"].values, sub["umap2"].values, s=60, alpha=0.9)

        ax.set_title("UMAP with dose trajectories (centroids)")
        ax.set_xlabel("UMAP1")
        ax.set_ylabel("UMAP2")
        ax.legend(loc="best", fontsize=8)

    caption = (
        f"n_wells={metrics['n_wells']}, n_conditions={metrics['n_conditions']}\n"
        f"spread_med={metrics['replicate_spread_median']:.4f}, sep_med={metrics['condition_separation_median']:.4f}\n"
        f"sep/spread={metrics['separation_over_spread']:.2f}\n"
        f"PCA var explained: {np.round(emb['pca_var'], 3).tolist()}"
    )
    fig.suptitle("Morphology manifold overview (raw, log1p + zscore)", fontsize=14)
    fig.text(0.01, 0.01, caption, fontsize=10, family='monospace')

    out_png = out_dir / "manifold_overview_raw_seed42.png"
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    out_json = out_dir / "manifold_metrics_raw_seed42.json"
    out_json.write_text(json.dumps(metrics, indent=2))

    print(f"Wrote: {out_png}")
    print(f"Wrote: {out_json}")
    print(f"\nMetrics:")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
