# Cell Painting Simulation Results Architecture

## Overview

Created a complete, reusable system for displaying Cell Painting simulation results on calibration plates.

## What's Been Built

### 1. Reusable Components

#### **SentinelChart** (`src/components/shared/SentinelChart.tsx`)
Statistical Process Control (SPC) chart for sequential well measurements.

**Features:**
- Line chart with control limits (mean ± 3σ)
- Automatic outlier detection (red dots for values outside UCL/LCL)
- Statistics summary panel (mean, std dev, UCL, LCL, outlier count)
- Outlier reporting section
- Status badge (In Control / Out of Control)
- Dark/Light mode support
- Optional live mode with pulsing animation

**When to use:**
- Display measurement values across wells sequentially
- Identify spatial patterns or artifacts
- QC monitoring for any channel measurement

---

#### **PlateResultsViewer** (`src/components/shared/PlateResultsViewer.tsx`)
Complete results visualization combining plate map + sentinel chart.

**Features:**
- Interactive plate map colored by measurement intensity
- Channel selector for 5 Cell Painting channels:
  - **DNA (Hoechst)** - Blue - Nucleus
  - **ER (Concanavalin A)** - Green - Endoplasmic Reticulum
  - **AGP (WGA)** - Amber - Golgi & Plasma Membrane
  - **Mito (MitoTracker)** - Red - Mitochondria
  - **RNA (SYTO)** - Purple - Nucleoli & Cytoplasmic RNA
- Automatic color gradient based on min/max values
- Integrated sentinel chart below plate map
- Well tooltips showing channel values + metadata (cell line, treatment, dose)
- Statistics summary (min, mean, max)
- Works with 96/384/1536-well plates
- Clickable wells (onWellClick callback)

**When to use:**
- Display complete simulation results
- Compare multiple channels on same plate
- Identify outliers and spatial patterns

---

### 2. Simulate Button Integration

All 4 calibration plate viewers now have a green **"Simulate"** button:
- CAL_384_RULES_WORLD_v1
- CAL_384_RULES_WORLD_v2
- CAL_384_MICROSCOPE_BEADS_DYES_v1
- CAL_384_LH_ARTIFACTS_v1

**Current behavior:**
- Shows alert explaining simulation flow
- Logs plate data to console
- Placeholder for backend integration

**Future behavior:**
```typescript
// In CalibrationPlatePage.tsx
const handleSimulate = async (plateData: any) => {
  // 1. Call Cell OS simulation API
  const response = await fetch('/api/simulate/cell-painting', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      plateDesign: plateData,
      channels: ['dna', 'er', 'agp', 'mito', 'rna']
    })
  });

  const simulationResults = await response.json();

  // 2. Navigate to results page
  navigate(`/calibration-results/${plateData.plate.plate_id}`, {
    state: {
      plateData,
      measurements: simulationResults.measurements
    }
  });
};
```

---

### 3. Documentation

**README_RESULTS.md** - Complete guide with:
- API documentation for both components
- TypeScript interface definitions
- Usage examples
- Integration guide
- Data transformation examples
- Benefits summary

---

## Data Flow

```
User clicks "Simulate" button
         ↓
CalibrationPlatePage.handleSimulate(plateData)
         ↓
Cell OS Simulation API
  - Takes plate design JSON
  - Runs Cell Painting simulation
  - Returns WellMeasurement[] with 5-channel data
         ↓
Navigate to Results Page
         ↓
PlateResultsViewer renders:
  - Plate map (colored by selected channel)
  - Channel selector (DNA/ER/AGP/Mito/RNA)
  - Sentinel chart (well-by-well analysis)
  - Statistics & outliers
```

---

## Data Formats

### Input: Plate Design
```json
{
  "schema_version": "calibration_plate_v1",
  "plate": {
    "plate_id": "CAL_384_RULES_WORLD_v1",
    "format": "384",
    "rows": ["A", "B", ...],
    "cols": [1, 2, ...]
  },
  "cell_lines": {...},
  "anchors": {...},
  ...
}
```

### Output: Simulation Results
```typescript
interface WellMeasurement {
  wellId: string;
  row: string;
  col: number;
  channels: {
    dna: number;    // DNA intensity
    er: number;     // ER intensity
    agp: number;    // AGP intensity
    mito: number;   // Mitochondria intensity
    rna: number;    // RNA intensity
  };
  metadata?: {
    cellLine?: string;     // e.g., "HepG2", "A549"
    treatment?: string;    // e.g., "DMSO", "Nocodazole"
    dose?: number;         // e.g., 0, 0.3, 1.0 (µM)
    [key: string]: any;
  };
}
```

---

## Integration Steps

### Step 1: Create Results Page

Create `/src/pages/CalibrationResultsPage.tsx`:

```typescript
import React from 'react';
import { useParams, useLocation } from 'react-router-dom';
import PlateResultsViewer, { WellMeasurement } from '../components/shared/PlateResultsViewer';

export default function CalibrationResultsPage() {
  const { plateId } = useParams();
  const location = useLocation();
  const { plateData, measurements } = location.state;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
      <div className="container mx-auto max-w-6xl">
        <PlateResultsViewer
          plateId={plateId}
          format="384"
          measurements={measurements}
          isDarkMode={true}
          title="Calibration Simulation Results"
          showSentinelChart={true}
          onWellClick={(wellId) => {
            console.log('Clicked well:', wellId);
            // Could open detail modal, etc.
          }}
        />
      </div>
    </div>
  );
}
```

### Step 2: Add Route

In `App.tsx`:
```typescript
<Route path="/calibration-results/:plateId" element={<CalibrationResultsPage />} />
```

### Step 3: Connect Backend

Update `handleSimulate` in `CalibrationPlatePage.tsx`:
```typescript
const handleSimulate = async (plateData: any) => {
  try {
    setLoading(true);

    // Call your Cell OS Python backend
    const response = await fetch('http://localhost:8000/api/simulate/cell-painting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plateDesign: plateData })
    });

    if (!response.ok) throw new Error('Simulation failed');

    const results = await response.json();

    // Navigate to results
    navigate(`/calibration-results/${plateData.plate.plate_id}`, {
      state: {
        plateData,
        measurements: results.measurements
      }
    });
  } catch (error) {
    console.error('Simulation error:', error);
    alert('Simulation failed. Check console for details.');
  } finally {
    setLoading(false);
  }
};
```

---

## Backend API Contract

### Endpoint: `POST /api/simulate/cell-painting`

**Request:**
```json
{
  "plateDesign": {
    "schema_version": "calibration_plate_v1",
    "plate": {...},
    "cell_lines": {...},
    "anchors": {...}
  }
}
```

**Response:**
```json
{
  "plate_id": "CAL_384_RULES_WORLD_v1",
  "measurements": [
    {
      "wellId": "A1",
      "row": "A",
      "col": 1,
      "channels": {
        "dna": 125.3,
        "er": 98.7,
        "agp": 145.2,
        "mito": 110.5,
        "rna": 88.9
      },
      "metadata": {
        "cellLine": "HepG2",
        "treatment": "DMSO",
        "dose": 0
      }
    },
    // ... 383 more wells
  ]
}
```

---

## Python Backend Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import numpy as np

app = FastAPI()

class PlateDesign(BaseModel):
    schema_version: str
    plate: Dict
    # ... other fields

class SimulationRequest(BaseModel):
    plateDesign: PlateDesign

class WellMeasurement(BaseModel):
    wellId: str
    row: str
    col: int
    channels: Dict[str, float]
    metadata: Dict

class SimulationResponse(BaseModel):
    plate_id: str
    measurements: List[WellMeasurement]

@app.post("/api/simulate/cell-painting")
async def simulate_cell_painting(request: SimulationRequest) -> SimulationResponse:
    """
    Run Cell Painting simulation on plate design.

    This would call your actual Cell OS simulation:
    - Load plate design
    - Simulate cell morphology responses
    - Extract Cell Painting features
    - Return multi-channel measurements
    """

    try:
        plate_design = request.plateDesign
        plate_id = plate_design.plate["plate_id"]

        # TODO: Replace with actual Cell OS simulation
        # from cell_os.simulation import run_cell_painting
        # results = run_cell_painting(plate_design)

        # For now, generate mock data
        measurements = []
        rows = plate_design.plate["rows"]
        cols = plate_design.plate["cols"]

        for row in rows:
            for col in cols:
                well_id = f"{row}{col}"

                # Mock measurements with some structure
                # (real simulation would use Cell OS biology)
                measurements.append(WellMeasurement(
                    wellId=well_id,
                    row=row,
                    col=col,
                    channels={
                        "dna": np.random.normal(125, 15),
                        "er": np.random.normal(100, 12),
                        "agp": np.random.normal(140, 18),
                        "mito": np.random.normal(110, 14),
                        "rna": np.random.normal(90, 11),
                    },
                    metadata={
                        "cellLine": "HepG2" if rows.index(row) < len(rows)//2 else "A549",
                        "treatment": "DMSO",  # Extract from plate design
                        "dose": 0
                    }
                ))

        return SimulationResponse(
            plate_id=plate_id,
            measurements=measurements
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Testing Without Backend

You can test the UI components immediately with mock data:

```typescript
// In CalibrationPlatePage.tsx
const handleSimulate = (plateData: any) => {
  // Generate mock measurements
  const rows = plateData.plate.rows;
  const cols = plateData.plate.cols;

  const mockMeasurements: WellMeasurement[] = [];
  rows.forEach((row: string, rowIdx: number) => {
    cols.forEach((col: number) => {
      const wellId = `${row}${col}`;

      mockMeasurements.push({
        wellId,
        row,
        col,
        channels: {
          dna: 120 + Math.random() * 30,
          er: 95 + Math.random() * 25,
          agp: 135 + Math.random() * 35,
          mito: 105 + Math.random() * 28,
          rna: 85 + Math.random() * 22,
        },
        metadata: {
          cellLine: rowIdx < rows.length / 2 ? 'HepG2' : 'A549',
          treatment: 'DMSO',
          dose: 0
        }
      });
    });
  });

  // Navigate with mock data
  navigate(`/calibration-results/${plateData.plate.plate_id}`, {
    state: { plateData, measurements: mockMeasurements }
  });
};
```

---

## Features Summary

✅ **Reusable Components** - SentinelChart and PlateResultsViewer work for any plate
✅ **Multi-Channel Support** - DNA, ER, AGP, Mito, RNA with custom colors
✅ **Interactive** - Clickable plate map, channel switching
✅ **Statistical** - Automatic outlier detection, SPC charts
✅ **Responsive** - Works on mobile and desktop
✅ **Type-Safe** - Full TypeScript support
✅ **Documented** - Complete API docs and examples
✅ **Integrated** - Simulate buttons on all 4 calibration plates

---

## Next Steps

1. **Create CalibrationResultsPage** component
2. **Add route** in App.tsx
3. **Connect to Cell OS simulation backend**
4. **Test with real simulation data**
5. **Add export functionality** (CSV, PNG)
6. **Add comparison mode** (compare multiple simulations)
7. **Add feature extraction results** (morphology features, not just raw intensities)
8. **Add quality metrics** (Z-factor, SSMD, CV%)
