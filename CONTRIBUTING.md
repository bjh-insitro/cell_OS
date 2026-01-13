# Contributing to cell_OS

Thank you for your interest in contributing to cell_OS! This document provides guidelines for contributing to this epistemic control research testbed.

## What This Project Is

cell_OS is a **research testbed** for studying epistemic honesty in autonomous experimental agents. It generates **100% synthetic cell biology data** to test whether agents can maintain calibrated uncertainty estimates.

**The research contribution is the epistemic machinery** (debt tracking, conservation laws, provenance ledgers), not the biology simulator.

## What We Accept

### Encouraged Contributions

- **Epistemic control mechanisms** - New debt variants, penalty functions, calibration requirements
- **Conservation law extensions** - Energy balance, stoichiometry, additional physical constraints
- **Provenance improvements** - Better ledger systems, cryptographic commitments
- **Test coverage** - Especially for epistemic invariants
- **Documentation** - Clarifications, examples, tutorials
- **Bug fixes** - Especially for silent failures (conservation violations, RNG coupling)

### Not Accepting

- **Wet-lab integration** - Scope too large, needs separate project
- **Biological accuracy improvements** - Unless they have epistemic relevance
- **Performance optimizations** - Unless they fix correctness issues
- **UI/UX changes** - Unless they improve epistemic transparency

## Development Setup

```bash
# Clone the repository
git clone https://github.com/brighart/cell_OS.git
cd cell_OS

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Run tests to verify setup
pytest
```

## Code Standards

### Style

- **Python**: Follow PEP 8, use type hints
- **Docstrings**: Google style
- **Line length**: 100 characters max
- **Imports**: Sorted, grouped (stdlib, third-party, local)

### Commit Messages

Use conventional commits:

```
feat: add provisional penalty tracking
fix: prevent debt overflow on repeated overclaiming
docs: update epistemic control API reference
refactor: consolidate simulation modules
test: add debt repayment edge cases
chore: update dependencies
```

### Testing

All contributions must include tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/cell_os tests/

# Run specific category
pytest tests/phase6a/  # Epistemic control
pytest tests/unit/     # Component tests
```

**Test Philosophy**:
- Tests verify **epistemic invariants**, not biological accuracy
- Conservation violations should **crash**, not warn
- Same seed must produce **identical results**

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. **Make changes** following the code standards
4. **Add tests** for new functionality
5. **Run the test suite**:
   ```bash
   pytest
   ```
6. **Update documentation** if needed
7. **Commit** with conventional commit messages
8. **Push** to your fork
9. **Open a PR** against `main`

### PR Checklist

- [ ] Tests pass locally
- [ ] New code has test coverage
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventions
- [ ] No hardcoded paths or secrets
- [ ] Conservation laws still enforced

## Project Structure

```
src/cell_os/
├── epistemic_agent/     # Agent + epistemic control (core contribution)
├── hardware/            # Synthetic data generator
├── biology/             # Pure biology models
├── simulation/          # Simulation executors
├── posh/                # POSH workflow
├── imaging/             # Imaging workflow
└── ...

scripts/
├── runners/             # Entry points
├── analysis/            # Analysis scripts
├── validation/          # Verification scripts
└── ...

tests/
├── unit/                # Component tests
├── integration/         # End-to-end tests
├── phase6a/             # Epistemic control tests
└── ...
```

## Key Invariants

When contributing, ensure these invariants are preserved:

1. **Death Conservation**: `viable + Σ(deaths) = 1.0 ± 1e-9`
2. **Observer Independence**: Measurement doesn't affect cell fate
3. **Determinism**: Same seed → identical results
4. **Debt Accumulation**: Overclaiming increases cost
5. **Evidence Provenance**: Every belief change has a receipt

## Getting Help

- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: See `docs/DEVELOPER_REFERENCE.md`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to epistemic control research!
