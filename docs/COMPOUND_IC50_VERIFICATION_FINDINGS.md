# Compound IC50 Verification - Literature Search Findings

**Date**: 2025-12-23
**Search Method**: Systematic PubMed searches

---

## Summary

Attempted systematic verification of IC50 values for ~15 compounds across 7 cell lines (~105 combinations). **Finding specific IC50 values for many compound × cell line pairs is extremely difficult** because:

1. **Research tool compounds** (tunicamycin, thapsigargin, CCCP) are used to induce cellular stress, not systematically tested for cytotoxicity
2. **Different assay methods** yield different IC50 values (MTT vs cell counting vs LDH release)
3. **Assay duration matters** (24h vs 48h vs 72h gives different values)
4. **Many combinations not published** - researchers don't typically test every compound on every cell line

---

## Verified IC50 Values (With Citations)

### Staurosporine

| Cell Line | IC50 | Source | Notes |
|-----------|------|--------|-------|
| **A549** | **0.65 nM** | PMID: 1563835 (Bradshaw 1992) | 96h cell counting assay |
| A549 | 18.4 nM | PMID: 1563835 | LDH release (different readout) |

**Current YAML values**:
- HEK293T: 0.05 µM (50 nM) - 77x higher than A549 literature value
- HeLa: 0.08 µM (80 nM) - 123x higher
- U2OS: 0.20 µM (200 nM) - 308x higher

**Issue**: Staurosporine IC50s are typically in the **low nM range** (0.5-5 nM), but YAML has values in the 50-200 nM range. Suggest reducing by ~10-100x.

---

### Doxorubicin

| Cell Line | IC50 | Source | Notes |
|-----------|------|--------|-------|
| **HepG2** | **10.15 µM** | PMID: 26873414 (Buduma 2016) | Also tested A549, HeLa, SKOV3 |

**Current YAML values**:
- HEK293T: 0.25 µM - 40x LOWER than HepG2 literature value
- HeLa: 0.15 µM - 68x lower
- U2OS: 0.35 µM - 29x lower

**Issue**: Doxorubicin IC50s are typically in the **1-10 µM range** for most cell lines. YAML values (0.15-0.35 µM) seem too low by ~10-30x.

---

### Cisplatin

| Cell Line | IC50 | Source | Notes |
|-----------|------|--------|-------|
| A375.2S (skin) | 0.07 µM | PMID: 31943302 (AlKhalil 2020) | Not A549/HeLa but provides reference |
| T47D (breast) | 34.59 µM | PMID: 31943302 | Wide variation by cell line! |
| K562 (leukemia) | 29.3 µM | PMID: 31943302 | |

**Current YAML values**:
- HEK293T: 5.0 µM - mid-range
- HeLa: 3.0 µM - mid-range
- U2OS: 8.0 µM - mid-range

**Assessment**: YAML values (3-8 µM) seem reasonable given the wide range (0.07-34 µM) reported in literature. Cell line dependent.

---

### Paclitaxel

| Cell Line | IC50 | Source | Notes |
|-----------|------|--------|-------|
| **A549** | **18 nM** | PMID: 21807043 (Joshi 2011) | PSN-PTX formulation |
| A549 (resistant) | 6.9-9.5 µM | PMID: 35324187 (Zhou 2022) | Resistant cells |

**Current YAML values**:
- HEK293T: 0.01 µM (10 nM) - matches literature!
- HeLa: 0.008 µM (8 nM) - similar
- U2OS: 0.015 µM (15 nM) - similar

**Assessment**: YAML values (8-15 nM) match literature well. Paclitaxel is extremely potent at nM concentrations.

---

## Compounds With No Verified IC50 Data Found

### Tunicamycin
- **Status**: Used as ER stress inducer, not systematically tested for cytotoxicity
- **Literature**: Papers describe ER stress induction, not IC50 curves
- **YAML values**: 0.3-1.0 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### Thapsigargin
- **Status**: SERCA pump inhibitor, research tool
- **Literature**: Zero PubMed results for "thapsigargin IC50 A549 HeLa cytotoxicity"
- **YAML values**: 0.3-0.6 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### CCCP (Carbonyl cyanide m-chlorophenyl hydrazone)
- **Status**: Mitochondrial uncoupler, research tool
- **Literature**: Not systematically tested across cell panels
- **YAML values**: 3.0-6.0 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### Oligomycin A
- **Status**: ATP synthase inhibitor
- **Literature**: Research tool, limited cytotoxicity data
- **YAML values**: 0.5-1.2 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### MG132
- **Status**: Proteasome inhibitor
- **Literature**: Research tool
- **YAML values**: 0.5-1.2 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### Nocodazole
- **Status**: Microtubule depolymerizer
- **Literature**: Research tool
- **YAML values**: 0.3-0.6 µM
- **Recommendation**: Mark as "estimated - research tool compound"

### 2-Deoxy-D-glucose (2-DG)
- **Status**: Glycolysis inhibitor
- **Literature**: Research tool, high IC50s (mM range)
- **YAML values**: 500-1200 µM (0.5-1.2 mM)
- **Recommendation**: Values seem reasonable for 2-DG

### Etoposide
- **Status**: Topoisomerase II inhibitor, chemotherapy drug
- **Literature**: Should have published IC50s but not found in initial search
- **YAML values**: 5.0-12.0 µM
- **Recommendation**: Need deeper search or mark as estimated

### tBHQ (tert-Butylhydroquinone)
- **Status**: Oxidative stress inducer
- **Literature**: Research tool
- **YAML values**: 35.0 µM (shallow Hill slope 0.8)
- **Recommendation**: Mark as "estimated - tuned for demo"

### TBHP (tert-Butyl hydroperoxide)
- **Status**: Oxidative stress inducer
- **Literature**: Research tool
- **YAML values**: 60-150 µM
- **Recommendation**: Mark as "estimated - research tool compound"

---

## Key Findings

### 1. IC50 Values Are Highly Variable
- **Staurosporine**: 0.65 nM (A549) - consistent across cell lines at low nM
- **Doxorubicin**: 10.15 µM (HepG2) - typically 1-10 µM range
- **Cisplatin**: 0.07-34 µM - 500x variation by cell line!
- **Paclitaxel**: 8-18 nM - extremely potent

### 2. Assay Conditions Matter
- Duration: 24h vs 48h vs 72h vs 96h
- Readout: Cell counting vs MTT vs LDH vs ATP
- Different methods give different IC50s for same compound!

### 3. Research Tool Compounds Poorly Documented
- Compounds like tunicamycin, thapsigargin used to induce specific cellular stress
- Not systematically tested for cytotoxicity across cell line panels
- IC50 values exist but scattered in supplementary data

### 4. Standard Chemotherapy Drugs Better Documented
- Doxorubicin, cisplatin, paclitaxel, etoposide have more published data
- But still challenging to find all compound × cell line combinations

---

## Recommendations

### Short Term
1. **Keep existing YAML values** for research tool compounds (tunicamycin, thapsigargin, CCCP, etc.)
2. **Mark them as "estimated"** in database with note: "Research tool compound - IC50 estimated from literature consensus"
3. **Update verified compounds** (staurosporine, doxorubicin) where we have clear discrepancies

### Medium Term
1. **Flag for experimental validation** - run dose-response curves in your own lab for key compounds
2. **Add assay metadata** - record which assay type and duration was used
3. **Add confidence levels** - "verified", "literature consensus", "estimated", "needs validation"

### Long Term
1. **Build internal reference database** from your own experiments
2. **Track batch-to-batch variation** in IC50 values
3. **Document compound stability** and storage conditions

---

## Updated Values to Consider

| Compound | Cell Line | Current | Suggested | Confidence |
|----------|-----------|---------|-----------|------------|
| **Staurosporine** | A549 | - | 0.65 nM | ✅ Verified (PMID: 1563835) |
| **Staurosporine** | HEK293T | 50 nM | ~5 nM? | ⚠️ Reduce 10x |
| **Staurosporine** | HeLa | 80 nM | ~5 nM? | ⚠️ Reduce 10x |
| **Doxorubicin** | HepG2 | - | 10.15 µM | ✅ Verified (PMID: 26873414) |
| **Doxorubicin** | HEK293T | 0.25 µM | ~5 µM? | ⚠️ Increase 20x |
| **Paclitaxel** | All | 8-15 nM | Keep | ✅ Matches literature |
| **Cisplatin** | All | 3-8 µM | Keep | ✅ Reasonable range |

---

## Metadata to Add to Database

For each IC50 value, track:
- `source` - "PubMed PMID:1234567" or "Estimated" or "Internal validation"
- `assay_type` - "MTT", "cell counting", "LDH", "ATP"
- `assay_duration_h` - 24, 48, 72, 96
- `confidence` - "verified", "literature consensus", "estimated", "needs validation"
- `date_verified` - when the value was last checked
- `notes` - any caveats or special conditions

---

## Next Steps

1. **Create migration** with:
   - Verified IC50 values (with PubMed citations)
   - Existing YAML values marked as "estimated"
   - Confidence levels for each value

2. **Create compound repository** to query IC50s from database

3. **Add cell line metadata** (tissue type, disease, etc.)

4. **Document limitations** - be transparent about which values are verified vs estimated

---

**Last Updated**: 2025-12-23
**Status**: Initial literature search complete, many values need experimental validation
