# Plate Results Visualization Components

Reusable components for displaying Cell Painting simulation results.

## Components

### 1. SentinelChart
Statistical Process Control (SPC) chart for sequential measurements.

**Features:**
- Line chart with control limits (mean ± 3σ)
- Automatic outlier detection (values outside UCL/LCL)
- Statistics summary (mean, std dev, UCL, LCL, outlier count)
- Support for dark/light mode
- Optional live mode with pulsing animation
- Detailed outlier reporting

**Usage:**
```tsx
import SentinelChart, { SentinelDataPoint } from './shared/SentinelChart';

const data: SentinelDataPoint[] = [
  { index: 1, value: 120.5, isOutlier: false, wellId: 'A1', label: 'Well A1' },
  { index: 2, value: 125.3, isOutlier: false, wellId: 'A2', label: 'Well A2' },
  { index: 3, value: 180.2, isOutlier: true, wellId: 'A3', label: 'Well A3' },
  // ...
];

const mean = 125;
const std = 15;
const ucl = mean + 3 * std; // 170
const lcl = mean - 3 * std; // 80

<SentinelChart
  data={data}
  mean={mean}
  ucl={ucl}
  lcl={lcl}
  std={std}
  title="DNA Channel - Well Analysis"
  subtitle="Control limits: mean ± 3σ"
  yAxisLabel="DNA Intensity (AU)"
  xAxisLabel="Well Index"
  isDarkMode={true}
  showStatistics={true}
  height={400}
  isLiveMode={false}
/>
```

**Props:**
- `data: SentinelDataPoint[]` - Array of measurements with index, value, optional outlier flag, wellId, label
- `mean: number` - Mean value for reference line
- `ucl: number` - Upper control limit (mean + 3σ)
- `lcl: number` - Lower control limit (mean - 3σ)
- `std: number` - Standard deviation
- `title?: string` - Chart title
- `subtitle?: string` - Chart subtitle (default: control limits explanation)
- `yAxisLabel?: string` - Y-axis label (default: "Value")
- `xAxisLabel?: string` - X-axis label (default: "Measurement Number")
- `isDarkMode?: boolean` - Dark mode styling (default: true)
- `showStatistics?: boolean` - Show statistics summary box (default: true)
- `height?: number` - Chart height in pixels (default: 400)
- `isLiveMode?: boolean` - Enable live mode animation (default: false)

---

### 2. PlateResultsViewer
Complete results viewer with plate map and sentinel chart for multi-channel Cell Painting data.

**Features:**
- Interactive plate map colored by measurement intensity
- Channel selector (DNA, ER, AGP, Mito, RNA) with custom colors
- Automatic color gradient based on min/max values
- Integrated sentinel chart for spatial pattern analysis
- Well tooltips with channel values and metadata
- Statistics summary (min, mean, max)
- Support for 96/384/1536-well plates

**Usage:**
```tsx
import PlateResultsViewer, { WellMeasurement, CellPaintingChannel } from './shared/PlateResultsViewer';

const measurements: WellMeasurement[] = [
  {
    wellId: 'A1',
    row: 'A',
    col: 1,
    channels: {
      dna: 125.3,
      er: 98.7,
      agp: 145.2,
      mito: 110.5,
      rna: 88.9
    },
    metadata: {
      cellLine: 'HepG2',
      treatment: 'DMSO',
      dose: 0
    }
  },
  {
    wellId: 'A2',
    row: 'A',
    col: 2,
    channels: {
      dna: 130.1,
      er: 102.3,
      agp: 150.8,
      mito: 115.2,
      rna: 92.1
    },
    metadata: {
      cellLine: 'HepG2',
      treatment: 'Nocodazole',
      dose: 0.3
    }
  },
  // ... more wells
];

// Optional: Custom channels
const customChannels: CellPaintingChannel[] = [
  { id: 'dna', name: 'DNA (Hoechst)', color: '#3b82f6', description: 'Nucleus' },
  { id: 'er', name: 'ER', color: '#10b981', description: 'ER' },
  // ...
];

<PlateResultsViewer
  plateId="CAL_384_RULES_WORLD_v1"
  format="384"
  measurements={measurements}
  channels={customChannels} // Optional, uses defaults if not provided
  isDarkMode={true}
  title="Calibration Plate Results"
  showSentinelChart={true}
  onWellClick={(wellId) => console.log('Clicked:', wellId)}
/>
```

**Props:**
- `plateId: string` - Plate identifier for display
- `format: '96' | '384' | '1536'` - Plate format
- `measurements: WellMeasurement[]` - Array of well measurements
- `channels?: CellPaintingChannel[]` - Channel definitions (optional, uses defaults)
- `isDarkMode?: boolean` - Dark mode styling (default: true)
- `title?: string` - Title for results section
- `showSentinelChart?: boolean` - Show sentinel chart below plate map (default: true)
- `onWellClick?: (wellId: string) => void` - Callback when well is clicked

**Default Channels:**
- DNA (Hoechst) - Blue (#3b82f6) - Nucleus
- ER (Concanavalin A) - Green (#10b981) - Endoplasmic Reticulum
- AGP (WGA) - Amber (#f59e0b) - Golgi & Plasma Membrane
- Mito (MitoTracker) - Red (#ef4444) - Mitochondria
- RNA (SYTO) - Purple (#8b5cf6) - Nucleoli & Cytoplasmic RNA

---

### 3. Complete Example: Simulation Results Page

```tsx
import React, { useState } from 'react';
import PlateResultsViewer, { WellMeasurement } from '../components/shared/PlateResultsViewer';

export default function CalibrationResultsPage() {
  const [simulationData, setSimulationData] = useState<WellMeasurement[] | null>(null);
  const [loading, setLoading] = useState(false);

  const runSimulation = async () => {
    setLoading(true);
    try {
      // Call your simulation API
      const response = await fetch('/api/simulate/CAL_384_RULES_WORLD_v1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plateDesign: '...' })
      });
      const data = await response.json();
      setSimulationData(data.measurements);
    } catch (error) {
      console.error('Simulation failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
      <div className="container mx-auto max-w-6xl">
        {!simulationData ? (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-12 text-center">
            <h2 className="text-2xl font-bold text-white mb-4">
              Ready to Simulate
            </h2>
            <p className="text-slate-400 mb-6">
              Run Cell Painting simulation on this calibration plate
            </p>
            <button
              onClick={runSimulation}
              disabled={loading}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold transition-all disabled:opacity-50"
            >
              {loading ? 'Simulating...' : 'Run Simulation'}
            </button>
          </div>
        ) : (
          <PlateResultsViewer
            plateId="CAL_384_RULES_WORLD_v1"
            format="384"
            measurements={simulationData}
            isDarkMode={true}
            title="Simulation Results"
            showSentinelChart={true}
            onWellClick={(wellId) => {
              console.log('Clicked well:', wellId);
              // Could open detail modal, etc.
            }}
          />
        )}
      </div>
    </div>
  );
}
```

---

## Integration with Existing Plate Designs

To add simulation capability to your calibration plates:

1. **Add "Simulate" button** to plate viewer page
2. **Generate mock data** or call simulation API
3. **Transform data** to `WellMeasurement[]` format
4. **Display with PlateResultsViewer**

Example transformation from simulation output:
```typescript
// Simulation output format
interface SimulationOutput {
  wells: {
    wellId: string;
    channels: { dna: number; er: number; agp: number; mito: number; rna: number; };
  }[];
}

// Transform to WellMeasurement format
function transformSimulationData(simOutput: SimulationOutput, plateDesign: any): WellMeasurement[] {
  return simOutput.wells.map(well => {
    const row = well.wellId[0];
    const col = parseInt(well.wellId.slice(1));

    return {
      wellId: well.wellId,
      row,
      col,
      channels: well.channels,
      metadata: {
        cellLine: getCellLineForWell(well.wellId, plateDesign),
        treatment: getTreatmentForWell(well.wellId, plateDesign),
        dose: getDoseForWell(well.wellId, plateDesign),
      }
    };
  });
}
```

---

## Benefits

✅ **DRY Principle** - Single source of truth for results visualization
✅ **Consistency** - Same look and feel across all plate types
✅ **Flexibility** - Works with 96/384/1536-well plates
✅ **Customizable** - Custom channels, colors, metadata
✅ **Interactive** - Clickable wells, channel switching
✅ **Statistical** - Automatic outlier detection and SPC charts
✅ **Type-Safe** - Full TypeScript support
✅ **Responsive** - Works on mobile and desktop

---

## Next Steps

1. Connect to Cell OS simulation backend
2. Add export functionality (CSV, images)
3. Add comparison mode (compare multiple simulations)
4. Add feature extraction results
5. Add quality metrics (Z-factor, SSMD, etc.)
