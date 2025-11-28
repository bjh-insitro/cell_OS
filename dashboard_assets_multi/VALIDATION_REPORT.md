# Multi-Cell Line Validation Report

**Generated**: 2025-11-28
**Scope**: Validation of MCB/WCB simulations across different cell types.

---

## 1. Cell Lines Tested

| Cell Line | Doubling Time | Max Confluence | Sensitivity |
|-----------|---------------|----------------|-------------|
| **U2OS**  | 26.0 h        | 0.88           | Low         |
| **iPSC**  | 40.0 h        | 0.80           | High        |

## 2. Results Summary

### MCB Simulation (Target: 30 vials)
| Metric | U2OS | iPSC | Observation |
|--------|------|------|-------------|
| **Duration** | 4.0 days | 6.0 days | ✅ iPSC slower as expected |
| **Success** | 96% | 96% | ✅ Both robust to random failure |
| **Yield** | 30 vials | 30 vials | ✅ Both hit target |

### WCB Simulation (Target: 10 vials)
| Metric | U2OS | iPSC | Observation |
|--------|------|------|-------------|
| **Duration** | 6.0 days | 7.0 days | ✅ iPSC slower as expected |
| **Success** | 96% | 96% | ✅ Consistent performance |

## 3. Conclusion

The simulation engine correctly adapts to biological parameters defined in `simulation_parameters.yaml`. Slower growing cells (iPSCs) result in longer campaign durations, which correctly impacts resource usage and scheduling. The failure logic (contamination) applies equally, while biological failures (senescence, stress) are modeled but didn't trigger catastrophic failure in these short runs.
