"""
Identifiability design builder for Phase 2C.1.

Builds simulation plan from config that tests:
1. Phase 1 smooth RE identifiability (Plate A - low stress)
2. Phase 2A commitment identifiability (Plate C - high stress)
3. Joint model validation (Plate B - held-out prediction)
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


@dataclass
class RegimeAction:
    """Single action in a regime (seed or treat)."""
    action_type: str  # "seed" or "treat"
    vessel_id: str
    params: Dict[str, Any]


@dataclass
class RegimePlan:
    """Plan for one regime (A/B/C)."""
    regime_name: str
    plate_id_prefix: str
    actions: List[RegimeAction]
    timepoints: List[float]
    metrics: List[str]
    description: str


class IdentifiabilityDesign:
    """Loads and builds identifiability calibration design."""

    def __init__(self, config_path: str):
        """
        Load design config from YAML.

        Args:
            config_path: Path to identifiability_2c1.yaml or equivalent
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Design config not found: {config_path}")

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.global_config = self.config['global']
        self.regimes_config = self.config['regimes']
        self.timepoints = self.config['timepoints']
        self.metrics = self.config['metrics']
        self.truth = self.config['truth']
        self.acceptance = self.config['acceptance']

    def get_bio_noise_config(self) -> Dict[str, Any]:
        """
        Build bio_noise_config dict from truth block.

        Returns:
            Config dict for BiologicalVirtualMachine(..., bio_noise_config=...)
        """
        phase1 = self.truth['phase1']
        phase2a_er = self.truth['phase2a_er']
        phase2a_mito = self.truth['phase2a_mito']

        config = {
            # Phase 1
            'enabled': phase1['enabled'],
            'growth_cv': phase1['growth_cv'],
            'stress_sensitivity_cv': phase1['stress_sensitivity_cv'],
            'hazard_scale_cv': phase1['hazard_scale_cv'],
            'plate_level_fraction': phase1['plate_level_fraction'],

            # Phase 2A ER
            'er_commitment_enabled': phase2a_er['enabled'],
            'er_commitment_threshold': phase2a_er['threshold'],
            'er_commitment_baseline_hazard_per_h': phase2a_er['baseline_hazard_per_h'],
            'er_commitment_sharpness_p': phase2a_er['sharpness_p'],
            'er_commitment_hazard_cap_per_h': phase2a_er['hazard_cap_per_h'],
            'er_committed_death_hazard_per_h': phase2a_er['committed_death_hazard_per_h'],

            # Phase 2A Mito
            'mito_commitment_enabled': phase2a_mito['enabled'],
        }

        return config

    def build_regime_plan(self, regime_name: str) -> RegimePlan:
        """
        Build regime plan (list of actions) for given regime.

        Supports:
        - Single compound (compound + dose_uM)
        - Compound combo (compound_combo list)
        - Multiple doses (doses list with n_wells_per_dose)

        Args:
            regime_name: Regime key from regimes_config

        Returns:
            RegimePlan with vessel seeding and treatment actions
        """
        regime_cfg = self.regimes_config[regime_name]
        actions = []

        # Case 1: Multiple doses (stratified design)
        if 'doses' in regime_cfg:
            n_wells_per_dose = regime_cfg['n_wells_per_dose']
            doses = regime_cfg['doses']

            well_idx = 0
            for dose_idx, dose_spec in enumerate(doses):
                for replicate in range(n_wells_per_dose):
                    vessel_id = self._make_vessel_id(
                        regime_cfg['plate_id_prefix'],
                        well_idx
                    )

                    # Seed action
                    actions.append(RegimeAction(
                        action_type="seed",
                        vessel_id=vessel_id,
                        params={
                            'cell_line': self.global_config['cell_line'],
                            'initial_count': self.global_config['initial_count'],
                        }
                    ))

                    # Treat action
                    actions.append(RegimeAction(
                        action_type="treat",
                        vessel_id=vessel_id,
                        params={
                            'compound': dose_spec['compound'],
                            'dose_uM': dose_spec['dose_uM'],
                        }
                    ))

                    well_idx += 1

        # Case 2: Compound combo (multiple compounds per well)
        elif 'compound_combo' in regime_cfg:
            n_wells = regime_cfg['n_wells']
            compound_combo = regime_cfg['compound_combo']

            for well_idx in range(n_wells):
                vessel_id = self._make_vessel_id(
                    regime_cfg['plate_id_prefix'],
                    well_idx
                )

                # Seed action
                actions.append(RegimeAction(
                    action_type="seed",
                    vessel_id=vessel_id,
                    params={
                        'cell_line': self.global_config['cell_line'],
                        'initial_count': self.global_config['initial_count'],
                    }
                ))

                # Treat actions (one per compound in combo)
                for compound_spec in compound_combo:
                    actions.append(RegimeAction(
                        action_type="treat",
                        vessel_id=vessel_id,
                        params={
                            'compound': compound_spec['compound'],
                            'dose_uM': compound_spec['dose_uM'],
                        }
                    ))

        # Case 3: Single compound, single dose
        else:
            n_wells = regime_cfg['n_wells']
            compound = regime_cfg['compound']
            dose_uM = regime_cfg['dose_uM']

            for well_idx in range(n_wells):
                vessel_id = self._make_vessel_id(
                    regime_cfg['plate_id_prefix'],
                    well_idx
                )

                # Seed action
                actions.append(RegimeAction(
                    action_type="seed",
                    vessel_id=vessel_id,
                    params={
                        'cell_line': self.global_config['cell_line'],
                        'initial_count': self.global_config['initial_count'],
                    }
                ))

                # Treat action (skip if DMSO control)
                if compound.lower() != "dmso" or dose_uM > 0:
                    actions.append(RegimeAction(
                        action_type="treat",
                        vessel_id=vessel_id,
                        params={
                            'compound': compound,
                            'dose_uM': dose_uM,
                        }
                    ))

        return RegimePlan(
            regime_name=regime_name,
            plate_id_prefix=regime_cfg['plate_id_prefix'],
            actions=actions,
            timepoints=self.timepoints,
            metrics=self.metrics,
            description=regime_cfg['description']
        )

    def build_all_regimes(self) -> List[RegimePlan]:
        """Build plans for all regimes defined in config."""
        return [
            self.build_regime_plan(regime_name)
            for regime_name in self.regimes_config.keys()
        ]

    def build_scout_regime(
        self,
        compound: str,
        dose_range: Tuple[float, float],
        n_doses: int,
        n_wells_per_dose: int
    ) -> RegimePlan:
        """
        Build dose ladder scout regime for empirical tuning.

        Args:
            compound: e.g., "tunicamycin"
            dose_range: (min_uM, max_uM) log-spaced
            n_doses: Number of dose levels to test
            n_wells_per_dose: Replicates per dose

        Returns:
            RegimePlan for scout run
        """
        import numpy as np

        doses_uM = np.logspace(
            np.log10(dose_range[0]),
            np.log10(dose_range[1]),
            n_doses
        )

        actions = []
        well_idx = 0

        for dose_uM in doses_uM:
            for _ in range(n_wells_per_dose):
                vessel_id = self._make_vessel_id("Scout", well_idx)

                # Seed
                actions.append(RegimeAction(
                    action_type="seed",
                    vessel_id=vessel_id,
                    params={
                        'cell_line': self.global_config['cell_line'],
                        'initial_count': self.global_config['initial_count'],
                    }
                ))

                # Treat
                actions.append(RegimeAction(
                    action_type="treat",
                    vessel_id=vessel_id,
                    params={
                        'compound': compound,
                        'dose_uM': float(dose_uM),
                    }
                ))

                well_idx += 1

        return RegimePlan(
            regime_name="scout",
            plate_id_prefix="Scout",
            actions=actions,
            timepoints=self.timepoints,
            metrics=self.metrics,
            description=f"Dose ladder scout: {compound} {dose_range[0]:.3f}-{dose_range[1]:.1f} µM"
        )

    def _make_vessel_id(self, plate_prefix: str, well_idx: int) -> str:
        """
        Generate vessel_id from plate prefix and well index.

        Uses standard 96-well format: A01-H12 (8 rows × 12 cols = 96 wells).
        For >96 wells, uses multiple plates.

        Args:
            plate_prefix: e.g., "PlateA", "PlateB", "PlateC"
            well_idx: 0-based well index

        Returns:
            vessel_id: e.g., "PlateA1_A01", "PlateA1_B03", "PlateA2_A01"
        """
        wells_per_plate = 96
        plate_num = (well_idx // wells_per_plate) + 1
        well_in_plate = well_idx % wells_per_plate

        row_idx = well_in_plate // 12
        col_idx = (well_in_plate % 12) + 1

        row_letter = chr(ord('A') + row_idx)
        well_pos = f"{row_letter}{col_idx:02d}"

        return f"{plate_prefix}{plate_num}_{well_pos}"
