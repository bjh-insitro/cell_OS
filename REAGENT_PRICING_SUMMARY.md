# Reagent Pricing Summary

All missing reagents have been added to `data/raw/pricing.yaml`.

## Dissociation Enzymes

| Reagent | Price/mL | Vendor | Use Case |
|---------|----------|--------|----------|
| **Versene (EDTA)** | $0.18 | Thermo | Ultra-gentle, EDTA only, cheapest |
| **Trypsin-EDTA 0.25%** | $0.22 | Thermo | Classic, harsh but cheap |
| **TrypLE Express** | $0.35 | Thermo | Gentle alternative to trypsin |
| **Accutase** | $0.75 | Thermo | Gentlest enzyme, most expensive |

## Freezing Media

| Reagent | Price/mL | Vendor | Use Case |
|---------|----------|--------|----------|
| **DMSO** | $0.45 | Sigma | Classic cryoprotectant (use with FBS) |
| **CryoStor CS10** | $4.00 | STEMCELL | DMSO-free, expensive |
| **Bambanker** | $6.00 | Wako | Serum-free, ready-to-use |
| **mFreSR** | $6.00 | STEMCELL | Optimized for stem cells |

**Note:** FBS+DMSO combo (90% FBS + 10% DMSO) = ~$0.95/mL vs CryoStor at $4.00/mL

## Transfection Reagents

| Reagent | Price/Unit | Vendor | Use Case |
|---------|------------|--------|----------|
| **PEI MAX** | $2.00/mg | Polysciences | Cheap, for HEK293 |
| **Opti-MEM** | $0.10/mL | Thermo | Reduced serum media for transfection |
| **Lipofectamine 3000** | $300/mL | Thermo | High efficiency, expensive |
| **FuGENE HD** | $250/mL | Promega | Gentle, for sensitive cells |
| **Nucleofection Buffer** | $200/mL | Lonza | For electroporation |
| **Calcium Chloride** | $0.40/mL | Sigma | For calcium phosphate transfection |
| **HEPES Buffered Saline** | $0.35/mL | Sigma | For calcium phosphate transfection |

## Consumables

| Item | Price/Unit | Vendor |
|------|------------|--------|
| **Cell Scraper** | $0.80/each | Corning |

## Cost Impact Summary

### Passage (6-well plate)
- **Versene**: $14.89 (cheapest, 18% savings vs Accutase)
- **Trypsin**: $17.84 (2% savings vs Accutase)
- **TrypLE**: $17.94 (1% savings vs Accutase)
- **Accutase**: $18.18 (most expensive, but gentlest)
- **Scraping**: $17.00 (manual, no automation)

### Freeze (10 vials)
- **FBS+DMSO**: $36.03 (cheapest, 46% savings vs CryoStor)
- **CryoStor**: $66.33 (DMSO-free)
- **Bambanker/mFreSR**: $86.33 (most expensive, but serum-free)

### Transfection (T175 flask)
- **Calcium Phosphate**: $15.31 (cheapest)
- **PEI**: $18.38 (cheap, good for HEK293)
- **Lipofectamine**: $24.12 (high efficiency)
- **FuGENE**: $34.17 (gentle)
- **Nucleofection**: $42.35 (best for hard-to-transfect cells)

### Transduction (24-well plate)
- **Spinoculation**: $7.22 (48% savings vs passive)
- **Passive**: $13.92 (standard method)
