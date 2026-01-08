"""
Good Regulator Embedding per Feala's Closed-Loop Manifesto.

"The Good Regulator theorem: a successful black-box controller necessarily
contains a model of its target system (embedded in weights). This decouples
competence from legible comprehension."

This module implements:
1. Extract implicit models from successful controllers
2. Analyze what the controller "knows" about the system
3. Compare implicit vs explicit models
4. Transfer knowledge between controllers

Key insight: Competence implies implicit comprehension.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple, Any
import numpy as np
from collections import defaultdict


@dataclass
class ControllerAction:
    """Record of a controller action and outcome."""
    state: np.ndarray           # State before action
    action: np.ndarray          # Action taken
    next_state: np.ndarray      # State after action
    reward: float               # Outcome
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImplicitModel:
    """
    Model implicit in controller behavior.

    Extracted by observing state-action-outcome patterns.
    """
    # State transition predictions
    transition_accuracy: float  # How well can we predict next_state from state+action
    reward_accuracy: float      # How well can we predict reward from state+action

    # Feature importance (what the controller "attends to")
    state_feature_importance: Dict[str, float]
    action_feature_importance: Dict[str, float]

    # Discovered rules
    extracted_rules: List[str]

    # Comparison to explicit model
    explicit_model_correlation: Optional[float] = None


class GoodRegulatorAnalyzer:
    """
    Analyze what a controller implicitly "knows" about its environment.

    Per Good Regulator theorem: successful control implies a model.
    """

    def __init__(self, state_dim: int, action_dim: int):
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Collected trajectories
        self.trajectories: List[ControllerAction] = []

        # Learned implicit model (simple linear for interpretability)
        self.transition_model = None  # state + action -> next_state
        self.reward_model = None      # state + action -> reward

    def record_action(
        self,
        state: np.ndarray,
        action: np.ndarray,
        next_state: np.ndarray,
        reward: float,
        info: Optional[Dict] = None
    ):
        """Record a controller action for analysis."""
        self.trajectories.append(ControllerAction(
            state=state.copy(),
            action=action.copy(),
            next_state=next_state.copy(),
            reward=reward,
            info=info or {}
        ))

    def extract_implicit_model(self) -> ImplicitModel:
        """
        Extract the implicit model from recorded trajectories.

        This reveals what the controller "knows" about the system.
        """
        if len(self.trajectories) < 10:
            raise ValueError("Need at least 10 trajectories for analysis")

        # Prepare data
        X = []  # state + action
        Y_transition = []  # next_state
        Y_reward = []  # reward

        for traj in self.trajectories:
            x = np.concatenate([traj.state, traj.action])
            X.append(x)
            Y_transition.append(traj.next_state)
            Y_reward.append(traj.reward)

        X = np.array(X)
        Y_transition = np.array(Y_transition)
        Y_reward = np.array(Y_reward)

        # Fit simple linear models (for interpretability)
        # Transition model: X -> Y_transition
        transition_accuracy = self._fit_and_evaluate(X, Y_transition)

        # Reward model: X -> Y_reward
        reward_accuracy = self._fit_and_evaluate(X, Y_reward.reshape(-1, 1))

        # Extract feature importance
        state_importance = self._compute_feature_importance(
            X[:, :self.state_dim], Y_reward,
            [f"state_{i}" for i in range(self.state_dim)]
        )
        action_importance = self._compute_feature_importance(
            X[:, self.state_dim:], Y_reward,
            [f"action_{i}" for i in range(self.action_dim)]
        )

        # Extract rules
        rules = self._extract_rules(X, Y_reward)

        return ImplicitModel(
            transition_accuracy=transition_accuracy,
            reward_accuracy=reward_accuracy,
            state_feature_importance=state_importance,
            action_feature_importance=action_importance,
            extracted_rules=rules
        )

    def _fit_and_evaluate(self, X: np.ndarray, Y: np.ndarray) -> float:
        """Fit linear model and return R^2 accuracy."""
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import cross_val_score

        model = Ridge(alpha=1.0)
        scores = cross_val_score(model, X, Y, cv=min(5, len(X)), scoring='r2')
        return max(0, np.mean(scores))  # Clip negative R^2

    def _compute_feature_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Compute feature importance using correlation."""
        importance = {}
        for i, name in enumerate(feature_names):
            corr = np.corrcoef(X[:, i], y)[0, 1]
            importance[name] = abs(corr) if not np.isnan(corr) else 0.0
        return importance

    def _extract_rules(self, X: np.ndarray, y: np.ndarray) -> List[str]:
        """Extract simple decision rules from data."""
        rules = []

        # Find high-reward vs low-reward patterns
        median_reward = np.median(y)
        high_reward_mask = y > median_reward

        for i in range(X.shape[1]):
            high_mean = X[high_reward_mask, i].mean()
            low_mean = X[~high_reward_mask, i].mean()

            if abs(high_mean - low_mean) > 0.3 * X[:, i].std():
                direction = "high" if high_mean > low_mean else "low"
                feature_type = "state" if i < self.state_dim else "action"
                idx = i if i < self.state_dim else i - self.state_dim
                rules.append(
                    f"When {feature_type}_{idx} is {direction}, reward tends to be higher"
                )

        return rules[:5]  # Limit to top 5 rules


class ImplicitKnowledgeTransfer:
    """
    Transfer implicit knowledge from one controller to another.

    If controller A is successful, its implicit model can bootstrap controller B.
    """

    def __init__(self):
        self.source_models: Dict[str, ImplicitModel] = {}

    def register_successful_controller(
        self,
        name: str,
        analyzer: GoodRegulatorAnalyzer
    ):
        """Register a successful controller's implicit model."""
        model = analyzer.extract_implicit_model()
        self.source_models[name] = model

    def get_prior_knowledge(self, target_task: str) -> Dict[str, float]:
        """
        Get prior knowledge for a new task based on similar controllers.

        Returns feature importance weights to guide new controller.
        """
        if not self.source_models:
            return {}

        # Average feature importance across source models
        combined = defaultdict(list)
        for model in self.source_models.values():
            for k, v in model.state_feature_importance.items():
                combined[k].append(v)
            for k, v in model.action_feature_importance.items():
                combined[k].append(v)

        return {k: np.mean(v) for k, v in combined.items()}

    def get_suggested_rules(self) -> List[str]:
        """Get rules extracted from successful controllers."""
        all_rules = []
        for model in self.source_models.values():
            all_rules.extend(model.extracted_rules)
        return list(set(all_rules))[:10]


def demonstrate_good_regulator():
    """
    Demonstrate Good Regulator theorem in action.

    A successful controller implicitly learns a model of its environment.
    """
    # Simple environment: state = [x, v], action = [force]
    # Dynamics: x' = x + v*dt, v' = v + (force - friction*v)*dt
    # Goal: keep x near 0

    state_dim = 2  # [position, velocity]
    action_dim = 1  # [force]

    analyzer = GoodRegulatorAnalyzer(state_dim, action_dim)

    # Simulate a successful PD controller
    rng = np.random.default_rng(42)
    dt = 0.1
    friction = 0.1

    for episode in range(20):
        x, v = rng.uniform(-1, 1), rng.uniform(-0.5, 0.5)

        for step in range(50):
            state = np.array([x, v])

            # PD control (successful controller)
            force = -2.0 * x - 0.5 * v + rng.normal(0, 0.1)
            action = np.array([force])

            # Dynamics
            x_new = x + v * dt
            v_new = v + (force - friction * v) * dt
            next_state = np.array([x_new, v_new])

            # Reward: minimize distance from origin
            reward = -abs(x_new)

            analyzer.record_action(state, action, next_state, reward)

            x, v = x_new, v_new

    # Extract what controller "knows"
    implicit_model = analyzer.extract_implicit_model()

    print("Good Regulator Analysis")
    print("=" * 50)
    print(f"Transition prediction accuracy: {implicit_model.transition_accuracy:.2%}")
    print(f"Reward prediction accuracy: {implicit_model.reward_accuracy:.2%}")
    print("\nState feature importance:")
    for k, v in sorted(implicit_model.state_feature_importance.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v:.3f}")
    print("\nExtracted rules:")
    for rule in implicit_model.extracted_rules:
        print(f"  - {rule}")

    return implicit_model
