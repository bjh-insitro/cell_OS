"""
scRNA-seq simulation layer.

Reads vessel latent state (stress axes, viability, subpopulations) and generates
single-cell UMI count matrices with realistic technical artifacts.

Philosophy:
- Biology lives in VesselState (latent stress, subpops, viability)
- This module transforms latent → counts with measurement noise
- Batch effects, dropout, ambient RNA are MEASUREMENT nuisances, not biology
- Separation of concerns: don't duct-tape transcriptomics onto morphology
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class ScRNASeqResult:
    """
    Single-cell RNA-seq measurement result.

    Attributes:
        gene_names: Ordered list of gene symbols
        cell_ids: Ordered list of cell identifiers
        counts: UMI count matrix (n_cells × n_genes), dtype int32
        meta: Per-cell metadata + run metadata
    """
    gene_names: List[str]
    cell_ids: List[str]
    counts: np.ndarray              # shape (n_cells, n_genes), int32
    meta: Dict[str, Any]            # per-cell arrays + run metadata


def _load_yaml(path: str | Path) -> Dict[str, Any]:
    """Load YAML config file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _sigmoid_hill(x: np.ndarray, hill: float) -> np.ndarray:
    """
    Hill equation for program activation: x^h / (1 + x^h)

    Args:
        x: Normalized activation level (0-1)
        hill: Hill coefficient (steepness)

    Returns:
        Activated fraction [0, 1]
    """
    x = np.clip(x, 0.0, None)
    return (x ** hill) / (1.0 + (x ** hill))


def _dropout_prob(expected_umi: np.ndarray, alpha: float, x0: float) -> np.ndarray:
    """
    Dropout probability model: genes with low expression are more likely undetected.

    p_dropout = 1 / (1 + (expected_umi / x0)^alpha)

    Args:
        expected_umi: Expected UMI count per gene per cell
        alpha: Dropout strength (higher = more aggressive)
        x0: Midpoint (UMI level with 50% dropout)

    Returns:
        Dropout probability [0, 1]
    """
    expected_umi = np.clip(expected_umi, 1e-8, None)
    return 1.0 / (1.0 + (expected_umi / x0) ** alpha)


def _apply_contact_program(
    expected: np.ndarray,
    p: float,
    gene_names: List[str],
    gene_index: Dict[str, int],
    scale: float = 0.35,
) -> np.ndarray:
    """
    Apply contact inhibition program (YAP/TAZ, Hippo pathway, metabolic shifts).

    This is a MEASUREMENT CONFOUNDER. High confluence shifts expression globally,
    independent of compound mechanism. Creates systematic bias that forces agents
    to control for density or suffer false mechanism attribution.

    For now, use a simple low-rank program (1 factor). Can be replaced later with
    curated gene loadings from real density time-course data.

    Args:
        expected: Expected expression (n_cells × n_genes)
        p: Contact pressure [0, 1]
        gene_names: List of gene symbols
        gene_index: Map {gene: index}
        scale: Program strength (default 0.35 = 35% modulation at full pressure)

    Returns:
        Modified expected expression

    Contract:
    - Deterministic (loadings are reproducible per gene set)
    - No RNG dependence (uses stable hash, not process hash())
    - Monotonic (higher p → consistent systematic shift)
    """
    import hashlib

    n_cells, n_genes = expected.shape

    # Synthetic per-gene loading vector (deterministic per gene set)
    # Use stable hash (sha256) so loadings are reproducible across runs
    key = ("|".join(sorted(gene_names))).encode("utf-8")
    seed_for_loadings = int.from_bytes(hashlib.sha256(key).digest()[:4], "little")
    rng_loadings = np.random.Generator(np.random.PCG64(seed_for_loadings))

    # Low-rank program: single factor with small variance
    # Most genes: weak response. A few genes: strong response (creates structure)
    beta = rng_loadings.normal(loc=0.0, scale=0.15, size=n_genes)

    # Apply: log_mu += (scale * p) * beta
    # Equivalent to: expected *= exp((scale * p) * beta)
    fold = np.exp((scale * p) * beta[None, :])
    return expected * fold


def _sample_library_sizes(rng: np.random.Generator, n: int, mean: float, logsigma: float) -> np.ndarray:
    """
    Sample library sizes (total UMIs per cell) from lognormal distribution.

    Args:
        rng: Random number generator
        n: Number of cells
        mean: Target mean library size
        logsigma: Log-space standard deviation

    Returns:
        Library sizes (UMIs per cell)
    """
    # Lognormal: E[X] = exp(mu + 0.5*sigma^2)
    # Solve for mu: mu = log(E) - 0.5*sigma^2
    mu = np.log(mean) - 0.5 * (logsigma ** 2)
    return rng.lognormal(mean=mu, sigma=logsigma, size=n)


def _make_batch_effects(
    rng: np.random.Generator,
    n_genes: int,
    shared_sigma: float,
    gene_sigma: float,
) -> np.ndarray:
    """
    Generate batch-specific multiplicative effects per gene.

    Composed of:
    - Shared latent (affects all genes in batch)
    - Gene-specific noise

    Args:
        rng: Random number generator
        n_genes: Number of genes
        shared_sigma: Shared latent variance (log-space)
        gene_sigma: Gene-specific variance (log-space)

    Returns:
        Multiplicative batch effects per gene (exp of log-space sum)
    """
    shared = rng.normal(loc=0.0, scale=shared_sigma)
    gene = rng.normal(loc=0.0, scale=gene_sigma, size=n_genes)
    # Log space → multiplicative
    return np.exp(shared + gene)


def simulate_scrna_counts(
    *,
    cell_line: str,
    vessel_latents: Dict[str, float],
    viability: float,
    n_cells: int,
    rng: np.random.Generator,
    params_path: str | Path,
    batch_id: Optional[str] = None,
    subpop_fractions: Optional[Dict[str, float]] = None,
    run_context_latent: Optional[float] = None,
) -> ScRNASeqResult:
    """
    Simulate single-cell RNA-seq UMI counts from vessel latent state.

    Physics → Measurement transformation:
    1. Baseline expression per cell line
    2. Stress program activation from vessel latents (er_stress, mito_dysfunction, etc.)
    3. Subpopulation heterogeneity (program gain + baseline noise)
    4. Viability effects (apoptosis gene modulation)
    5. Library size normalization + sampling
    6. Batch effects (multiplicative per-gene biases)
    7. Dropout (low-expression genes randomly undetected)
    8. Ambient RNA contamination
    9. Poisson sampling (UMI counting noise)

    Args:
        cell_line: Cell line name (e.g., "A549")
        vessel_latents: Latent stress states {axis_name: level}
        viability: Vessel viability [0, 1]
        n_cells: Number of cells to profile
        rng: Random number generator (use assay RNG for observer independence)
        params_path: Path to scrna_seq_params.yaml
        batch_id: Optional batch identifier for batch effects
        subpop_fractions: Optional subpop mixture {subpop_name: fraction}
        run_context_latent: Optional RunContext coupling for correlated batch drift

    Returns:
        ScRNASeqResult with counts matrix + metadata
    """
    params = _load_yaml(params_path)
    programs = _load_yaml(params["stress_programs_ref"])

    baseline_map = params["cell_line_baseline"].get(cell_line)
    if baseline_map is None:
        raise ValueError(f"cell line '{cell_line}' not in scrna params")

    # Assemble gene list from baseline keys plus any program genes
    gene_set = set(baseline_map.keys())
    for prog in programs.values():
        for direction in ("up", "down"):
            for g in prog.get(direction, {}).keys():
                gene_set.add(g)

    gene_names = sorted(gene_set)
    n_genes = len(gene_names)

    baseline = np.array([float(baseline_map.get(g, 0.2)) for g in gene_names], dtype=np.float64)
    baseline = np.clip(baseline, 1e-6, None)

    # Program activation from vessel latents
    hill = float(params["dose_response"]["hill"])
    latent_sat = float(params["dose_response"]["latent_saturation"])

    # Normalize latents into activation scalars (0..1)
    latents = {k: float(vessel_latents.get(k, 0.0)) for k in programs.keys()}
    act = {k: _sigmoid_hill(np.array([latents[k] / max(latent_sat, 1e-8)]), hill=hill)[0] for k in latents}

    # Build per-gene fold-change vector from activated programs
    fold = np.ones(n_genes, dtype=np.float64)
    gene_index = {g: i for i, g in enumerate(gene_names)}

    for axis, prog in programs.items():
        a = act.get(axis, 0.0)
        if a <= 0.0:
            continue

        for g, fc in prog.get("up", {}).items():
            if g not in gene_index:
                continue
            i = gene_index[g]
            # Linear interpolation: fold = 1 + a * (fc - 1)
            fold[i] *= (1.0 + a * (float(fc) - 1.0))

        for g, fc in prog.get("down", {}).items():
            if g not in gene_index:
                continue
            i = gene_index[g]
            fold[i] *= (1.0 + a * (float(fc) - 1.0))

    # Viability modulates apoptosis genes
    # Low viability → increase pro-apoptotic (BAX, BBC3), decrease anti-apoptotic (BCL2)
    viab = float(np.clip(viability, 0.0, 1.0))
    apoptosis = set(params["genesets"].get("apoptosis", []))
    for g in apoptosis:
        if g not in gene_index:
            continue
        i = gene_index[g]
        if g in ("BAX", "BBC3"):  # Pro-apoptotic
            fold[i] *= (1.0 + (1.0 - viab) * 4.0)
        if g == "BCL2":  # Anti-apoptotic
            fold[i] *= (1.0 - (1.0 - viab) * 0.5)

    # Subpopulation sampling
    if subpop_fractions is None:
        subpop_fractions = {"sensitive": 0.25, "typical": 0.50, "resistant": 0.25}

    subpops = list(subpop_fractions.keys())
    p = np.array([subpop_fractions[s] for s in subpops], dtype=np.float64)
    p = p / p.sum()

    cell_subpop = rng.choice(subpops, size=n_cells, p=p)

    subpop_cfg = params["subpop_effects"]
    program_gain = np.array([float(subpop_cfg[s]["program_gain"]) for s in cell_subpop], dtype=np.float64)
    baseline_cv = np.array([float(subpop_cfg[s]["baseline_noise_cv"]) for s in cell_subpop], dtype=np.float64)

    # Per-cell baseline noise (lognormal, captures cell-to-cell variation)
    # mu = -0.5*sigma^2 to preserve mean=1
    mu = -0.5 * (baseline_cv ** 2)
    noise = np.exp(rng.normal(loc=mu[:, None], scale=baseline_cv[:, None], size=(n_cells, n_genes)))
    expected = baseline[None, :] * noise

    # Apply stress programs with subpop-specific gain
    # Sensitive cells: program_gain > 1 (stronger response)
    # Resistant cells: program_gain < 1 (weaker response)
    expected *= (fold[None, :] ** program_gain[:, None])

    # Contact inhibition confounder: high confluence shifts expression systematically
    # This is NOT a stress axis - it's a measurement confounder that creates false attribution
    contact_pressure = float(vessel_latents.get("contact_inhibition", 0.0))
    if contact_pressure > 0.01:
        expected = _apply_contact_program(expected, contact_pressure, gene_names, gene_index)

    # Cell cycle confounder: cycling cells show high cycle markers + suppressed stress markers
    # This creates realistic ambiguity: "recovered or just dividing?"
    cc = params.get("cell_cycle", {})
    cycling_score = None
    if cc:
        frac_map = cc.get("cycling_fraction_by_cell_line", {})
        cycling_frac = float(frac_map.get(cell_line, 0.3))

        # Sample per-cell cycling state (0/1) then convert to continuous score
        cycling_binary = (rng.random(n_cells) < cycling_frac).astype(np.float64)
        cycling_score = cycling_binary * rng.uniform(0.6, 1.0, size=n_cells)

        # Upregulate cell cycle program genes
        cc_prog = cc.get("cycling_program", {})
        for g, fc in cc_prog.items():
            if g in gene_index:
                i = gene_index[g]
                # Linear interpolation: 1.0 + cycling_score * (fc - 1.0)
                expected[:, i] *= (1.0 + cycling_score * (float(fc) - 1.0))

        # CRITICAL: Antagonize stress markers when cycling is high
        # This creates false "recovery" signal in proliferating cells
        # Resource competition: dividing cells suppress stress response
        ant = cc.get("stress_antagonism", {})
        for g, mult in ant.items():
            if g in gene_index:
                i = gene_index[g]
                # Cycling suppresses stress markers: mult < 1.0
                # expected[cycling] *= (1.0 - cycling_score * (1.0 - mult))
                # When cycling_score = 1.0, gene *= mult
                # When cycling_score = 0.0, gene *= 1.0
                expected[:, i] *= (1.0 - cycling_score * (1.0 - float(mult)))

    # Library size scaling: normalize per-cell sum, then scale to sampled library size
    tech = params["technical_noise"]
    lib = _sample_library_sizes(
        rng,
        n_cells,
        mean=float(tech["umi_depth_mean"]),
        logsigma=float(tech["umi_depth_logsigma"]),
    )
    expected_sum = np.clip(expected.sum(axis=1), 1e-8, None)
    expected = expected / expected_sum[:, None] * lib[:, None]

    # Batch effects (multiplicative per-gene biases)
    # CRITICAL: Batch effects must be deterministic per batch_id, not just RNG state
    # Use stable seeding like cell_painting_assay to ensure same batch_id → same effects
    batch_mult = np.ones(n_genes, dtype=np.float64)
    if batch_id is not None:
        # Create batch-specific RNG from batch_id hash (deterministic)
        import hashlib
        batch_seed = int.from_bytes(
            hashlib.blake2s(f"scrna_batch_{batch_id}".encode(), digest_size=4).digest(),
            "little"
        )
        rng_batch = np.random.default_rng(batch_seed)

        batch_mult = _make_batch_effects(
            rng_batch,  # Use batch-specific RNG, not measurement RNG
            n_genes=n_genes,
            shared_sigma=float(tech["batch_shared_sigma"]),
            gene_sigma=float(tech["batch_gene_lognormal_sigma"]),
        )
        # Optional: couple to RunContext global latent (correlated drift)
        if run_context_latent is not None:
            batch_mult *= np.exp(float(run_context_latent) * 0.10)

    expected *= batch_mult[None, :]

    # Dropout: low-expression genes randomly undetected
    p_do = _dropout_prob(expected, alpha=float(tech["dropout_alpha"]), x0=float(tech["dropout_x0"]))
    dropout_mask = rng.random(size=expected.shape) < p_do
    expected = np.where(dropout_mask, 0.0, expected)

    # Ambient RNA: add small fraction of mean profile (cell-free RNA in supernatant)
    ambient_frac = float(tech.get("ambient_fraction", 0.0))
    if ambient_frac > 0:
        ambient_profile = expected.mean(axis=0)
        expected = (1.0 - ambient_frac) * expected + ambient_frac * ambient_profile[None, :]

    # Sample UMI counts: Poisson is the minimal honest model
    counts = rng.poisson(lam=np.clip(expected, 0.0, None)).astype(np.int32)

    cell_ids = [f"cell_{i:05d}" for i in range(n_cells)]

    meta = {
        "cell_line": cell_line,
        "batch_id": batch_id,
        "cell_subpop": cell_subpop.tolist(),
        "library_size": lib.astype(np.int32).tolist(),
        "latents": latents,
        "viability": viab,
        "program_activation": act,
        "cycling_score": cycling_score.tolist() if cc else None,
    }

    return ScRNASeqResult(
        gene_names=gene_names,
        cell_ids=cell_ids,
        counts=counts,
        meta=meta,
    )
