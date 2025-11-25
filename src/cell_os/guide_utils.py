from typing import List

import pandas as pd


def _maybe_rename(df: pd.DataFrame, candidates: List[str], target: str) -> pd.DataFrame:
    """If any of `candidates` exists, rename it to `target`."""
    for c in candidates:
        if c in df.columns and c != target:
            return df.rename(columns={c: target})
    return df


def format_library(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Normalize a guide repository dataframe into the expected schema.

    Expected columns after formatting:
      - 'sgRNA'       : guide sequence
      - 'Start'       : genomic start (int)
      - 'End'         : genomic end (int)
      - gene id col   : whatever your config uses for 'gene_identifier_column'
      - optional score: whatever your config uses for 'score_name'

    We keep everything else and just tidy the basics.
    """
    df = df.copy()

    # Attach provenance
    df["repository_source"] = source_name

    # Normalize sequence column
    df = _maybe_rename(
        df,
        [
            "sgRNA",           # already normalized
            "sgRNA Sequence",  # CRISPick
            "sequence",
            "protospacer",
            "guide",
            "sgRNA_sequence",
        ],
        "sgRNA",
    )

    # Normalize genomic coordinates
    df = _maybe_rename(df, ["Start", "start", "Start_pos", "genomic_start"], "Start")
    df = _maybe_rename(df, ["End", "end", "End_pos", "genomic_end"], "End")

    # Basic sanity checks; these will fail loudly if something is off
    required = ["sgRNA", "Start", "End"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Repository {source_name} is missing required columns: {missing}. "
            "Update src/guide_utils.format_library to map your columns correctly."
        )

    return df
