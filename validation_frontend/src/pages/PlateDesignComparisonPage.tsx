import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';

interface WellData {
  well_id: string;
  row: string;
  col: number;
  cell_line: string;
  compound: string;
  viability: number;
  n_cells: number;
  morph_er: number;
  morph_mito: number;
  morph_nucleus: number;
  morph_actin: number;
  morph_rna: number;
}

interface PlateResult {
  plate_id: string;
  seed: number;
  flat_results: WellData[];
}

const SEEDS = [42, 123, 456, 789, 1011];
const ROWS = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P'];
const COLS = Array.from({length: 24}, (_, i) => i + 1);

const FEATURES = [
  { key: 'n_cells', label: 'Cell Count', format: (v: number) => v.toFixed(0) },
  { key: 'viability', label: 'Viability', format: (v: number) => v.toFixed(2) },
  { key: 'morph_er', label: 'ER Morphology', format: (v: number) => v.toFixed(2) },
  { key: 'morph_mito', label: 'Mito Morphology', format: (v: number) => v.toFixed(2) },
  { key: 'morph_nucleus', label: 'Nucleus Morphology', format: (v: number) => v.toFixed(2) },
  { key: 'morph_actin', label: 'Actin Morphology', format: (v: number) => v.toFixed(2) },
  { key: 'morph_rna', label: 'RNA Morphology', format: (v: number) => v.toFixed(2) },
];

export default function PlateDesignComparisonPage() {
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [selectedFeature, setSelectedFeature] = useState('n_cells');
  const [selectedSeed, setSelectedSeed] = useState<number | 'mean'>(42);
  const [v1Data, setV1Data] = useState<Map<number, PlateResult>>(new Map());
  const [v2Data, setV2Data] = useState<Map<number, PlateResult>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAllResults();
  }, []);

  const loadAllResults = async () => {
    const v1Map = new Map<number, PlateResult>();
    const v2Map = new Map<number, PlateResult>();

    // Load manifest to get file paths
    const manifest = await fetch('/demo_results/calibration_plates/runs_manifest.json').then(r => r.json());

    for (const seed of SEEDS) {
      // Find v1 and v2 results for this seed
      const v1Run = manifest.runs.find((r: any) =>
        r.plate_id === 'CAL_384_RULES_WORLD_v1' && r.seed === seed
      );
      const v2Run = manifest.runs.find((r: any) =>
        r.plate_id === 'CAL_384_RULES_WORLD_v2' && r.seed === seed
      );

      if (v1Run) {
        const data = await fetch(`/${v1Run.file_path}`).then(r => r.json());
        v1Map.set(seed, data);
      }

      if (v2Run) {
        const data = await fetch(`/${v2Run.file_path}`).then(r => r.json());
        v2Map.set(seed, data);
      }
    }

    setV1Data(v1Map);
    setV2Data(v2Map);
    setLoading(false);
  };

  const getFeatureValue = (wellData: WellData, feature: string): number => {
    return (wellData as any)[feature] || 0;
  };

  const computePlateHeatmap = (data: Map<number, PlateResult>, seed: number | 'mean', feature: string): number[][] => {
    const heatmap = Array(16).fill(0).map(() => Array(24).fill(0));

    if (seed === 'mean') {
      // Compute mean across all seeds
      const counts = Array(16).fill(0).map(() => Array(24).fill(0));

      for (const [s, result] of data.entries()) {
        for (const well of result.flat_results) {
          const rowIdx = ROWS.indexOf(well.row);
          const colIdx = well.col - 1;
          heatmap[rowIdx][colIdx] += getFeatureValue(well, feature);
          counts[rowIdx][colIdx]++;
        }
      }

      // Average
      for (let r = 0; r < 16; r++) {
        for (let c = 0; c < 24; c++) {
          if (counts[r][c] > 0) {
            heatmap[r][c] /= counts[r][c];
          }
        }
      }
    } else {
      // Single seed
      const result = data.get(seed);
      if (result) {
        for (const well of result.flat_results) {
          const rowIdx = ROWS.indexOf(well.row);
          const colIdx = well.col - 1;
          heatmap[rowIdx][colIdx] = getFeatureValue(well, feature);
        }
      }
    }

    return heatmap;
  };

  const getColorForValue = (value: number, min: number, max: number): string => {
    const normalized = (value - min) / (max - min);
    const hue = (1 - normalized) * 240; // Blue (240) to Red (0)
    return `hsl(${hue}, 70%, 50%)`;
  };

  const renderHeatmap = (title: string, heatmap: number[][], design: 'v1' | 'v2') => {
    const allValues = heatmap.flat();
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);

    return (
      <div className="flex-1">
        <div className={`text-lg font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          {title}
        </div>
        <div className={`text-sm mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          {design === 'v1' ? 'Blocked: HepG2 (A-H), A549 (I-P)' : 'Interleaved: Alternating rows'}
        </div>
        <div className="inline-block border-2" style={{
          borderColor: isDarkMode ? '#475569' : '#d4d4d8'
        }}>
          {heatmap.map((row, rowIdx) => (
            <div key={rowIdx} className="flex">
              {row.map((value, colIdx) => (
                <div
                  key={colIdx}
                  className="w-6 h-6 border"
                  style={{
                    backgroundColor: getColorForValue(value, min, max),
                    borderColor: isDarkMode ? '#334155' : '#e4e4e7',
                    borderWidth: '0.5px'
                  }}
                  title={`${ROWS[rowIdx]}${colIdx + 1}: ${value.toFixed(2)}`}
                />
              ))}
            </div>
          ))}
        </div>
        <div className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Range: {min.toFixed(2)} - {max.toFixed(2)}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDarkMode ? 'bg-slate-900' : 'bg-white'}`}>
        <div className={`text-xl ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          Loading comparison data...
        </div>
      </div>
    );
  }

  const v1Heatmap = computePlateHeatmap(v1Data, selectedSeed, selectedFeature);
  const v2Heatmap = computePlateHeatmap(v2Data, selectedSeed, selectedFeature);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDarkMode
      ? 'bg-gradient-to-b from-slate-900 to-slate-800'
      : 'bg-gradient-to-b from-zinc-50 to-white'
    }`}>
      {/* Header */}
      <div className={`backdrop-blur-sm border-b sticky top-0 z-50 transition-colors duration-300 ${isDarkMode
        ? 'bg-slate-800/80 border-slate-700'
        : 'bg-white/80 border-zinc-200'
      }`}>
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <button
                onClick={() => navigate('/documentary')}
                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${isDarkMode
                  ? 'text-slate-400 hover:text-white'
                  : 'text-zinc-500 hover:text-zinc-900'
                }`}
              >
                ← Back to Documentary
              </button>
              <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                Plate Design Comparison: v1 vs v2
              </h1>
              <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                Spatial analysis across {SEEDS.length} seeds
              </p>
            </div>

            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`p-2 rounded-lg transition-all ${isDarkMode
                ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
              }`}
            >
              {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="container mx-auto px-6 py-6">
        <div className={`p-6 rounded-lg mb-6 ${isDarkMode ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className={`block text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                Feature to visualize:
              </label>
              <select
                value={selectedFeature}
                onChange={(e) => setSelectedFeature(e.target.value)}
                className={`w-full px-4 py-2 rounded-lg border-2 ${isDarkMode
                  ? 'bg-slate-700 border-slate-600 text-white'
                  : 'bg-white border-zinc-300 text-zinc-900'
                }`}
              >
                {FEATURES.map(f => (
                  <option key={f.key} value={f.key}>{f.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className={`block text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                Seed (or mean across all):
              </label>
              <select
                value={selectedSeed}
                onChange={(e) => setSelectedSeed(e.target.value === 'mean' ? 'mean' : parseInt(e.target.value))}
                className={`w-full px-4 py-2 rounded-lg border-2 ${isDarkMode
                  ? 'bg-slate-700 border-slate-600 text-white'
                  : 'bg-white border-zinc-300 text-zinc-900'
                }`}
              >
                <option value="mean">Mean across all seeds</option>
                {SEEDS.map(s => (
                  <option key={s} value={s}>Seed {s}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Side-by-side heatmaps */}
        <div className="flex gap-6">
          {renderHeatmap('CAL_384_RULES_WORLD_v1', v1Heatmap, 'v1')}
          {renderHeatmap('CAL_384_RULES_WORLD_v2', v2Heatmap, 'v2')}
        </div>

        {/* Key insights */}
        <div className={`mt-6 p-6 rounded-lg ${isDarkMode ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
          <div className={`text-lg font-bold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
            Key Questions
          </div>
          <ul className={`text-sm space-y-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
            <li>• <strong>v1:</strong> Can you see a horizontal band separating HepG2 (top) from A549 (bottom)? That's the confound.</li>
            <li>• <strong>v2:</strong> Does interleaving break the confound? Look for alternating patterns instead of bands.</li>
            <li>• <strong>Consistency:</strong> Switch between seeds - do patterns hold? Or are they seed-specific noise?</li>
            <li>• <strong>Edge effects:</strong> Are edge wells (column 1, 24, rows A, P) different from interior?</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
