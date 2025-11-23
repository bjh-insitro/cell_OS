# Automation and Parameterization Summary

## Automation Feasibility Analysis

The automation analysis module provides comprehensive assessment of protocol automation feasibility.

### Key Metrics

**Automation Percentage**: Percentage of steps that can be automated (automation_fit >= 1)

**Labor Cost Estimation**:
- Based on staff_attention scores (0=none, 1=5min, 2=15min, 3=30min per step)
- Default technician rate: $50/hour
- Includes manual bottleneck identification

**Cost-Benefit Analysis**:
- Compares labor cost vs automation/instrument cost
- Identifies when automation saves money
- Highlights manual bottlenecks that prevent full automation

### Results

#### Dissociation Methods
| Method | Automation % | Manual Steps | Labor Cost |
|--------|--------------|--------------|------------|
| **Trypsin** | 100% | 0 | $4.17 |
| **Accutase** | 100% | 0 | $4.17 |
| **Versene** | 100% | 0 | $4.17 |
| **Scraping** | 88.9% | 1 | $29.17 |

**Key Finding**: Scraping has 1 manual bottleneck ("Scrape Cells") that adds $25 in labor cost and prevents full automation.

#### Cell Counting Methods
| Method | Cost | Automation | Labor Cost | Total Cost |
|--------|------|------------|------------|------------|
| **Automated Counter** | $3.50 | ✓ Yes | $4.17 | $7.67 |
| **Hemocytometer** | $2.00 | ✗ No | $25.00 | $27.00 |
| **Flow Cytometer** | $5.50 | ✓ Yes | $4.17 | $9.67 |

**Key Finding**: Hemocytometer is cheapest in materials ($2.00) but most expensive overall ($27.00) due to high labor cost ($25.00). Automated counter offers best value at $7.67 total.

#### Freezing Operations
| Media | Material Cost | Labor Cost | Total Cost | Automation |
|-------|---------------|------------|------------|------------|
| **FBS+DMSO** | $36.03 | $4.17 | $40.19 | 100% |
| **CryoStor** | $66.33 | $4.17 | $70.50 | 100% |
| **Bambanker** | $86.33 | $4.17 | $90.50 | 100% |

**Key Finding**: All freezing methods are fully automatable. Labor cost is constant ($4.17), so material cost differences are the primary factor.

---

## New Parameterizations

### 1. Cell Counting Methods

**`op_count(vessel_id, method="automated")`**

Three methods available:

#### Automated Counter (Default)
- **Cost**: $3.50 (cassette + trypan blue)
- **Time**: Fast (time_score=1)
- **Automation**: ✓ Yes
- **Best for**: Routine counting, high throughput

#### Hemocytometer
- **Cost**: $2.00 (trypan blue only)
- **Time**: Slow (time_score=2)
- **Automation**: ✗ No (manual only)
- **Labor**: High (staff_attention=3)
- **Best for**: Budget-constrained, low throughput

#### Flow Cytometer
- **Cost**: $5.50 (counting beads)
- **Time**: Fast (time_score=1)
- **Automation**: ✓ Yes
- **Best for**: High accuracy required, viability assessment

### 2. Centrifugation Presets

**`op_centrifuge(vessel_id, preset="standard")`**

Three presets available:

#### Soft Spin
- **Parameters**: 300g, 5 minutes
- **Use case**: Fragile cells (stem cells, neurons)
- **Example**: `ops.op_centrifuge("tube", preset="soft")`

#### Standard Spin (Default)
- **Parameters**: 500g, 5 minutes
- **Use case**: Most cell types
- **Example**: `ops.op_centrifuge("tube", preset="standard")`

#### Hard Spin
- **Parameters**: 1000g, 10 minutes
- **Use case**: Pellet compaction, debris removal
- **Example**: `ops.op_centrifuge("tube", preset="hard")`

**Note**: Can still override with explicit parameters:
```python
ops.op_centrifuge("tube", duration_min=7, g_force=800)
```

---

## Automation Recommendations

### Fully Automatable Workflows
✓ **HEK293 Passage** (Trypsin): 100% automatable, $22.01 total cost
✓ **iPSC Passage** (Versene): 100% automatable, $19.06 total cost
✓ **Cell Freezing** (any media): 100% automatable

### Workflows with Manual Bottlenecks
⚠ **Primary Neuron Passage** (Scraping): 88.9% automatable
- Bottleneck: Manual scraping step
- Labor cost: $29.17 (vs $4.17 for automated methods)
- **Recommendation**: Use enzymatic dissociation if cell type permits

⚠ **Hemocytometer Counting**: 0% automatable
- Labor cost: $25.00
- **Recommendation**: Switch to automated counter ($7.67 total) for >3 samples/day

### Cost-Benefit Analysis
For operations performed >10x per month:
- **Automated counting** saves ~$19/count vs hemocytometer
- **Enzymatic dissociation** saves ~$25/passage vs scraping
- **ROI**: Automation pays for itself within 1-2 months for high-throughput labs

---

## Usage Examples

```python
from src.automation_analysis import analyze_unit_op_automation, generate_automation_report

# Analyze a single operation
passage_op = ops.op_passage("plate_6well", dissociation_method="trypsin")
analysis = analyze_unit_op_automation(passage_op)

print(f"Automation: {analysis.automation_percentage:.1f}%")
print(f"Labor cost: ${analysis.labor_cost_usd:.2f}")

# Generate detailed report
print(generate_automation_report(passage_op))

# Use new counting methods
count_auto = ops.op_count("tube", method="automated")      # $7.67 total
count_hemo = ops.op_count("tube", method="hemocytometer")  # $27.00 total
count_flow = ops.op_count("tube", method="flow_cytometer") # $9.67 total

# Use centrifuge presets
spin_soft = ops.op_centrifuge("tube", preset="soft")      # 300g, 5min
spin_std = ops.op_centrifuge("tube", preset="standard")   # 500g, 5min
spin_hard = ops.op_centrifuge("tube", preset="hard")      # 1000g, 10min
```
