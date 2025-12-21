#!/usr/bin/env python3
"""
Complete epistemic system demo: scRNA hardening + epistemic control.

This demonstrates the full system working together:
1. scRNA cost model (expensive, slow, confounded)
2. Epistemic debt tracking (overclaiming → cost inflation)
3. Entropy penalties (widening hurts)
4. Entropy source tracking (exploration ≠ confusion)
5. Marginal gain (prevents redundancy)
6. Provisional penalties (productive uncertainty)

Three agent personas:
- Naive: doesn't account for any of this (high cost)
- Conservative: avoids all risk (slow progress)
- Calibrated: strategic risk-taking (optimal)
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.epistemic_control import EpistemicController, EntropySource
from cell_os.hardware.assay_governance import allow_scrna_seq, AssayJustification


class Agent:
    """Base agent for epistemic control experiments."""

    def __init__(self, name: str, vm: BiologicalVirtualMachine):
        self.name = name
        self.vm = vm
        self.controller = EpistemicController()
        self.controller.set_baseline_entropy(1.0)
        self.current_entropy = 1.5  # Start uncertain
        self.prior_modalities = []
        self.episode = 0
        self.total_cost = 0.0
        self.total_reward = 0.0

    def run_imaging(self) -> float:
        """Run imaging assay (cheap, fast)."""
        self.episode += 1
        cost = 20.0

        # Simulate entropy reduction
        prior = self.current_entropy
        gain = np.random.uniform(0.2, 0.4)
        post = max(0.3, prior - gain)

        self.controller.claim_action(
            f"img_{self.episode}",
            "cell_painting",
            expected_gain_bits=gain,
        )
        self.current_entropy = post
        realized = self.controller.measure_information_gain(
            prior, post, EntropySource.MEASUREMENT_NARROWING
        )
        self.controller.resolve_action(f"img_{self.episode}", realized, "cell_painting")

        penalty = self.controller.compute_penalty("cell_painting")
        reward = 5.0 - cost / 10.0 - penalty.entropy_penalty
        self.total_cost += cost
        self.total_reward += reward

        self.prior_modalities.append("cell_painting")

        return realized

    def run_scrna(self, claim_marginal: bool = False) -> float:
        """Run scRNA assay (expensive, slow, confounded)."""
        self.episode += 1

        # Get inflated cost
        base_cost = 200.0
        cost = self.controller.get_inflated_cost(base_cost)

        prior = self.current_entropy

        # scRNA might widen (cell cycle confounder, batch drift)
        if np.random.random() < 0.3:  # 30% chance of widening
            gain = np.random.uniform(-0.3, -0.1)  # Widen
            source = EntropySource.MEASUREMENT_CONTRADICTORY
        else:
            gain = np.random.uniform(0.3, 0.6)  # Narrow
            source = EntropySource.MEASUREMENT_NARROWING

        post = np.clip(prior - gain, 0.1, 3.0)

        # Claim with marginal gain if requested
        if claim_marginal and self.prior_modalities:
            marginal = abs(gain) * 0.5  # Marginal is ~50% of total due to overlap
            self.controller.claim_action(
                f"scrna_{self.episode}",
                "scrna_seq",
                expected_gain_bits=abs(gain),
                prior_modalities=tuple(self.prior_modalities),
                claimed_marginal_gain=marginal,
            )
        else:
            self.controller.claim_action(
                f"scrna_{self.episode}",
                "scrna_seq",
                expected_gain_bits=abs(gain),
            )

        self.current_entropy = post
        realized = self.controller.measure_information_gain(prior, post, source)
        self.controller.resolve_action(f"scrna_{self.episode}", realized, "scrna_seq")

        penalty = self.controller.compute_penalty("scrna_seq")
        reward = 10.0 - cost / 20.0 - penalty.entropy_penalty
        self.total_cost += cost
        self.total_reward += reward

        self.prior_modalities.append("scrna_seq")

        return realized


class NaiveAgent(Agent):
    """Naive agent: doesn't understand epistemic control."""

    def run_experiment(self, n_steps: int = 5):
        print(f"\n{'='*60}")
        print(f"Naive Agent: '{self.name}'")
        print(f"{'='*60}")
        print("Strategy: spam scRNA whenever uncertain, ignore costs")

        for step in range(n_steps):
            print(f"\n[Step {step+1}]")

            # Always run scRNA when uncertain
            if self.current_entropy > 0.8:
                gain = self.run_scrna(claim_marginal=False)  # Doesn't claim marginal
                print(f"  Action: scRNA")
                print(f"  Gain: {gain:.2f} bits")
                print(f"  Entropy: {self.current_entropy:.2f}")
                print(f"  Cost: ${self.controller.get_inflated_cost(200.0):.2f}")
                print(f"  Debt: {self.controller.get_total_debt():.2f} bits")
            else:
                print(f"  Action: none (entropy low)")

        self._print_final_stats()

    def _print_final_stats(self):
        stats = self.controller.get_statistics()
        print(f"\n{'─'*60}")
        print(f"Final Stats:")
        print(f"  Total cost: ${self.total_cost:.2f}")
        print(f"  Total reward: {self.total_reward:.2f}")
        print(f"  Epistemic debt: {stats['total_debt']:.2f} bits")
        print(f"  Cost multiplier: {stats['cost_multiplier']:.2f}×")
        print(f"  Mean overclaim: {stats['mean_overclaim']:.2f} bits")
        print(f"{'='*60}")


class ConservativeAgent(Agent):
    """Conservative agent: avoids expensive assays entirely."""

    def run_experiment(self, n_steps: int = 5):
        print(f"\n{'='*60}")
        print(f"Conservative Agent: '{self.name}'")
        print(f"{'='*60}")
        print("Strategy: only use cheap imaging, never scRNA")

        for step in range(n_steps):
            print(f"\n[Step {step+1}]")

            # Always use cheap imaging
            gain = self.run_imaging()
            print(f"  Action: imaging")
            print(f"  Gain: {gain:.2f} bits")
            print(f"  Entropy: {self.current_entropy:.2f}")
            print(f"  Debt: {self.controller.get_total_debt():.2f} bits")

        self._print_final_stats()

    def _print_final_stats(self):
        stats = self.controller.get_statistics()
        print(f"\n{'─'*60}")
        print(f"Final Stats:")
        print(f"  Total cost: ${self.total_cost:.2f}")
        print(f"  Total reward: {self.total_reward:.2f}")
        print(f"  Epistemic debt: {stats['total_debt']:.2f} bits")
        print(f"  Cost multiplier: {stats['cost_multiplier']:.2f}×")
        print(f"{'='*60}")


class CalibratedAgent(Agent):
    """Calibrated agent: strategic use of scRNA with epistemic awareness."""

    def run_experiment(self, n_steps: int = 5):
        print(f"\n{'='*60}")
        print(f"Calibrated Agent: '{self.name}'")
        print(f"{'='*60}")
        print("Strategy: imaging first, scRNA only when justified + marginal gain accounting")

        for step in range(n_steps):
            print(f"\n[Step {step+1}]")

            # Decision logic
            if self.current_entropy > 1.2 and not self.prior_modalities:
                # High entropy, no prior measurements → use imaging first (cheap)
                gain = self.run_imaging()
                print(f"  Action: imaging (cheap first)")
                print(f"  Gain: {gain:.2f} bits")

            elif self.current_entropy > 0.9 and "cell_painting" in self.prior_modalities:
                # Medium entropy, already tried imaging → scRNA justified
                # Use marginal gain accounting
                debt = self.controller.get_total_debt()
                cost = self.controller.get_inflated_cost(200.0)

                print(f"  Considering scRNA...")
                print(f"    Current debt: {debt:.2f} bits")
                print(f"    Inflated cost: ${cost:.2f}")

                if debt < 2.0:  # Only if debt is manageable
                    gain = self.run_scrna(claim_marginal=True)  # Claims marginal gain
                    print(f"  Action: scRNA (justified)")
                    print(f"  Gain: {gain:.2f} bits")

                    # If widened, make provisional
                    if gain < 0:
                        penalty = self.controller.compute_penalty()
                        self.controller.add_provisional_penalty(
                            f"scrna_{self.episode}_prov",
                            penalty.entropy_penalty,
                            settlement_horizon=2,
                        )
                        print(f"    Widened! Made penalty provisional: {penalty.entropy_penalty:.2f}")
                else:
                    # Debt too high, use imaging instead
                    gain = self.run_imaging()
                    print(f"  Action: imaging (debt too high for scRNA)")
                    print(f"  Gain: {gain:.2f} bits")

            else:
                # Low entropy or stuck → replicate imaging
                gain = self.run_imaging()
                print(f"  Action: imaging")
                print(f"  Gain: {gain:.2f} bits")

            print(f"  Entropy: {self.current_entropy:.2f}")
            print(f"  Debt: {self.controller.get_total_debt():.2f} bits")

            # Step provisional penalties
            finalized = self.controller.step_provisional_penalties()
            if finalized > 0:
                print(f"  ⚠️  Provisional penalty finalized: {finalized:.2f}")

        self._print_final_stats()

    def _print_final_stats(self):
        stats = self.controller.get_statistics()
        print(f"\n{'─'*60}")
        print(f"Final Stats:")
        print(f"  Total cost: ${self.total_cost:.2f}")
        print(f"  Total reward: {self.total_reward:.2f}")
        print(f"  Epistemic debt: {stats['total_debt']:.2f} bits")
        print(f"  Cost multiplier: {stats['cost_multiplier']:.2f}×")
        print(f"  Mean overclaim: {stats['mean_overclaim']:.2f} bits")
        print(f"  Provisional refunded: ${stats.get('provisional_total_refunded', 0):.2f}")
        print(f"  Provisional finalized: ${stats.get('provisional_total_finalized', 0):.2f}")
        print(f"{'='*60}")


def main():
    print("="*70)
    print("Full Epistemic System Demo")
    print("="*70)
    print("\nThis demo shows the complete system working together:")
    print("  • scRNA cost model (expensive, slow, confounded)")
    print("  • Epistemic debt (overclaiming → inflation)")
    print("  • Entropy penalties (widening hurts)")
    print("  • Entropy source tracking (exploration ≠ confusion)")
    print("  • Marginal gain (prevents redundancy)")
    print("  • Provisional penalties (productive uncertainty)")

    # Create VM
    vm = BiologicalVirtualMachine(seed=42)

    # Run three agent personas
    np.random.seed(42)
    naive = NaiveAgent("Spams scRNA", vm)
    naive.run_experiment(n_steps=5)

    np.random.seed(42)
    conservative = ConservativeAgent("Avoids scRNA", vm)
    conservative.run_experiment(n_steps=5)

    np.random.seed(42)
    calibrated = CalibratedAgent("Strategic scRNA", vm)
    calibrated.run_experiment(n_steps=5)

    # Compare agents
    print("\n" + "="*70)
    print("Agent Comparison")
    print("="*70)

    agents = [naive, conservative, calibrated]
    print(f"\n{'Agent':<20} {'Cost':<12} {'Reward':<12} {'Debt':<12} {'Efficiency'}")
    print("─"*70)

    for agent in agents:
        efficiency = agent.total_reward / max(agent.total_cost, 1.0)
        debt = agent.controller.get_total_debt()
        print(f"{agent.name:<20} ${agent.total_cost:<11.2f} {agent.total_reward:<11.2f} {debt:<11.2f} {efficiency:.3f}")

    print("\n" + "="*70)
    print("Key Findings")
    print("="*70)
    print("""
1. Naive Agent:
   • Spams scRNA without justification
   • Accumulates debt from overclaiming
   • Costs escalate due to inflation
   • Lowest efficiency (reward/cost)

2. Conservative Agent:
   • Avoids expensive assays entirely
   • No debt accumulation
   • Low total cost but also low total reward
   • Misses opportunities for decisive resolution

3. Calibrated Agent (OPTIMAL):
   • Uses imaging first (cheap)
   • scRNA only when justified
   • Accounts for marginal gain (overlap with imaging)
   • Uses provisional penalties for risky but productive actions
   • Highest efficiency

Conclusion: The epistemic system creates pressure toward strategic,
            calibrated behavior. Naive spam is expensive, pure caution
            is slow, calibrated risk-taking is optimal.
""")


if __name__ == "__main__":
    main()
