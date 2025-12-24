"""
Shared helper for loading and normalizing JSONL ledgers in tests.

This prevents every integration test from writing its own parser.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LedgerArtifacts:
    """Bundle of all ledger files from an epistemic loop run."""
    evidence: List[Dict[str, Any]]
    decisions: List[Dict[str, Any]]
    diagnostics: List[Dict[str, Any]]
    refusals: List[Dict[str, Any]]
    mitigation: List[Dict[str, Any]]
    summary: Dict[str, Any]

    def decision_templates(self) -> List[str]:
        """Extract unique template names from decisions."""
        templates = []
        for dec in self.decisions:
            if 'chosen_template' in dec and dec['chosen_template']:
                templates.append(dec['chosen_template'])
        return templates

    def compounds_tested(self) -> List[str]:
        """Extract unique compounds from decisions (if available)."""
        compounds = set()
        for dec in self.decisions:
            kwargs = dec.get('chosen_kwargs', {})
            if isinstance(kwargs, dict) and 'compound' in kwargs:
                compounds.add(kwargs['compound'])
        return list(compounds)

    def debt_trajectory(self) -> List[float]:
        """Extract epistemic debt over time from diagnostics."""
        debt_values = []
        for diag in self.diagnostics:
            if diag.get('event_type') == 'epistemic_debt_status':
                debt_values.append(diag.get('debt_bits', 0.0))
        return debt_values

    def qc_flags_count(self) -> int:
        """Count QC flags from diagnostics or summary."""
        # Could be in diagnostics or observation records
        count = 0
        for diag in self.diagnostics:
            if 'qc_flag' in str(diag).lower() or 'morans_i' in str(diag).lower():
                count += 1
        return count

    def mitigation_cycles(self) -> List[int]:
        """Extract cycle numbers where mitigation occurred."""
        cycles = []
        for mit in self.mitigation:
            if 'cycle' in mit:
                cycles.append(mit['cycle'])
        return cycles


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file, return list of dicts. Empty list if missing."""
    if not path.exists():
        return []

    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    # Log warning but continue
                    print(f"Warning: Failed to parse line in {path}: {e}")
    return records


def load_ledgers(log_dir: Path, run_id: str) -> LedgerArtifacts:
    """Load all ledger artifacts from a run directory."""
    evidence = load_jsonl(log_dir / f"{run_id}_evidence.jsonl")
    decisions = load_jsonl(log_dir / f"{run_id}_decisions.jsonl")
    diagnostics = load_jsonl(log_dir / f"{run_id}_diagnostics.jsonl")
    refusals = load_jsonl(log_dir / f"{run_id}_refusals.jsonl")
    mitigation = load_jsonl(log_dir / f"{run_id}_mitigation.jsonl")

    # Load summary JSON
    summary_path = log_dir / f"{run_id}.json"
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            summary = json.load(f)
    else:
        summary = {}

    return LedgerArtifacts(
        evidence=evidence,
        decisions=decisions,
        diagnostics=diagnostics,
        refusals=refusals,
        mitigation=mitigation,
        summary=summary
    )


def normalize_for_comparison(data: Any, strip_nondeterministic: bool = True) -> Any:
    """
    Normalize data for comparison, optionally stripping nondeterministic fields.

    Strips:
    - Timestamps (ISO format or unix epoch)
    - Absolute file paths
    - UUIDs
    - Temp directory paths

    Does NOT strip scientific content (decisions, values, QC flags).
    """
    if not strip_nondeterministic:
        return data

    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            # Skip nondeterministic keys entirely
            if key in ['timestamp', 'timestamp_utc', 'created_at', 'updated_at']:
                continue

            # Normalize paths
            if key in ['log', 'json', 'evidence', 'decisions', 'diagnostics', 'paths']:
                if isinstance(value, str):
                    # Strip absolute path, keep just filename
                    value = Path(value).name
                elif isinstance(value, dict):
                    # Recursively normalize path dict
                    value = {k: Path(v).name if isinstance(v, str) else v for k, v in value.items()}

            normalized[key] = normalize_for_comparison(value, strip_nondeterministic)
        return normalized

    elif isinstance(data, list):
        return [normalize_for_comparison(item, strip_nondeterministic) for item in data]

    elif isinstance(data, str):
        # Strip UUIDs (8-4-4-4-12 hex pattern)
        data = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', data, flags=re.IGNORECASE)

        # Strip absolute paths (anything starting with /)
        data = re.sub(r'/[^\s]+/', 'PATH/', data)

        # Strip ISO timestamps
        data = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'TIMESTAMP', data)

        return data

    else:
        return data


def find_latest_run_id(log_dir: Path) -> Optional[str]:
    """Find the most recent run_id in a log directory based on JSON files.

    Excludes episode_summary files to find the actual run manifest.
    """
    json_files = list(log_dir.glob("run_*.json"))
    if not json_files:
        return None

    # Filter out episode_summary files
    json_files = [f for f in json_files if '_episode_summary' not in f.stem]

    if not json_files:
        return None

    # Sort by modification time, newest first
    json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Extract run_id from filename
    run_id = json_files[0].stem  # e.g., "run_20251223_143022"
    return run_id
