import React, { useState, useEffect } from 'react';
import { Download, Play } from 'lucide-react';
import PlateViewer, { WellData } from './shared/PlateViewer';

interface CalibrationPlateProps {
  isDarkMode: boolean;
  designVersion: string;
  onSimulate?: (plateData: any) => void;
}

// V1 embedded design (original)
const PLATE_MAP_V1 = {
  schema_version: "calibration_plate_v1",
  intent: "Learn the measurement rules of the world before exploring biology",
  plate: {
    plate_id: "CAL_384_RULES_WORLD_v1",
    format: "384",
    rows: ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P"],
    cols: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24],
  },
  cell_lines: {
    A: { rows: ["A","B","C","D","E","F","G","H"], name: "HepG2" },
    B: { rows: ["I","J","K","L","M","N","O","P"], name: "A549" }
  },
  anchors: {
    MILD: {
      wells: ["A1","A12","A24","D6","D18","H1","H12","H24","I1","I12","I24","L6","L18","P1","P12","P24"],
      dose: 1
    },
    STRONG: {
      wells: ["B3","B22","E9","E16","G3","G22","H6","H18","J3","J22","M9","M16","O3","O22","P6","P18"],
      dose: 100
    }
  },
  tiles: {
    wells: [
      "B2","B3","C2","C3",
      "B22","B23","C22","C23",
      "G2","G3","H2","H3",
      "G22","G23","H22","H23",
      "J2","J3","K2","K3",
      "J22","J23","K22","K23",
      "O2","O3","P2","P3",
      "O22","O23","P22","P23"
    ]
  }
};

export default function CalibrationPlateViewer({ isDarkMode, designVersion, onSimulate }: CalibrationPlateProps) {
  const [plateData, setPlateData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load plate design based on version
  useEffect(() => {
    async function loadDesign() {
      setLoading(true);
      setError(null);

      try {
        if (designVersion === 'v1') {
          setPlateData(PLATE_MAP_V1);
        } else if (designVersion === 'v2') {
          const response = await fetch('/plate_designs/CAL_384_RULES_WORLD_v2.json');
          if (!response.ok) throw new Error('Failed to load v2 design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'v3') {
          const response = await fetch('/plate_designs/CAL_384_RULES_WORLD_v3.json');
          if (!response.ok) throw new Error('Failed to load v3 design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'microscope') {
          const response = await fetch('/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json');
          if (!response.ok) throw new Error('Failed to load microscope design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'lh') {
          const response = await fetch('/plate_designs/CAL_384_LH_ARTIFACTS_v1.json');
          if (!response.ok) throw new Error('Failed to load liquid handler design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'variance') {
          const response = await fetch('/plate_designs/CAL_VARIANCE_PARTITION_v1.json');
          if (!response.ok) throw new Error('Failed to load variance partition design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'wash') {
          const response = await fetch('/plate_designs/CAL_EL406_WASH_DAMAGE_v1.json');
          if (!response.ok) throw new Error('Failed to load wash damage design');
          const data = await response.json();
          setPlateData(data);
        } else if (designVersion === 'dynamic') {
          const response = await fetch('/plate_designs/CAL_DYNAMIC_RANGE_v1.json');
          if (!response.ok) throw new Error('Failed to load dynamic range design');
          const data = await response.json();
          setPlateData(data);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    loadDesign();
  }, [designVersion]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-slate-400">Loading plate design...</div>
      </div>
    );
  }

  if (error || !plateData) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-red-400">Error: {error || 'No plate data'}</div>
      </div>
    );
  }

  // Render based on schema version
  if (plateData.schema_version === 'calibration_plate_v1') {
    return <PlateViewerV1 plateData={plateData} isDarkMode={isDarkMode} onSimulate={onSimulate} />;
  } else if (plateData.schema_version === 'calibration_plate_v2') {
    return <PlateViewerV2 plateData={plateData} isDarkMode={isDarkMode} onSimulate={onSimulate} />;
  } else if (plateData.schema_version === 'calibration_plate_v3') {
    return <PlateViewerV2 plateData={plateData} isDarkMode={isDarkMode} onSimulate={onSimulate} />;
  } else if (plateData.schema_version === 'microscope_calibration_plate_v1') {
    return <PlateViewerMicroscope plateData={plateData} isDarkMode={isDarkMode} onSimulate={onSimulate} />;
  } else if (plateData.schema_version === 'liquid_handler_calibration_plate_v1') {
    return <PlateViewerLiquidHandler plateData={plateData} isDarkMode={isDarkMode} onSimulate={onSimulate} />;
  }

  return (
    <div className="text-red-400">Unknown schema version: {plateData.schema_version}</div>
  );
}

// V1 Viewer (original implementation)
function PlateViewerV1({ plateData, isDarkMode, onSimulate }: { plateData: any; isDarkMode: boolean; onSimulate?: (plateData: any) => void }) {
  const rows = plateData.plate.rows;
  const cols = plateData.plate.cols;

  // Check plate type
  const isVariancePartition = plateData.plate.plate_id === 'CAL_VARIANCE_PARTITION_v1';
  const isWashDamage = plateData.plate.plate_id === 'CAL_EL406_WASH_DAMAGE_v1';
  const isDynamicRange = plateData.plate.plate_id === 'CAL_DYNAMIC_RANGE_v1';

  const downloadPlateJSON = () => {
    const dataStr = JSON.stringify(plateData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `${plateData.plate.plate_id}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const getWellType = (wellId: string) => {
    if (isDynamicRange) {
      // Determine anchor and dose by column
      const col = parseInt(wellId.slice(1));

      for (const anchor of plateData.anchors || []) {
        const dose = anchor.dose_uM_by_column?.[col.toString()];
        if (dose !== undefined) {
          if (dose === 0) return 'vehicle';
          // Return anchor type with dose level for coloring
          return `${anchor.anchor_id.toLowerCase()}_dose_${dose}`;
        }
      }

      return 'vehicle';
    } else if (isWashDamage) {
      // Check no-cells background wells first
      if (plateData.design?.no_cells_background?.wells?.includes(wellId)) {
        return 'no_cells';
      }

      // Determine wash program by column
      const col = parseInt(wellId.slice(1));
      for (const block of plateData.design?.program_blocks_by_columns || []) {
        if (block.cols.includes(col)) {
          return block.wash_program_id.toLowerCase();
        }
      }

      return 'wash_standard'; // Default
    } else if (isVariancePartition) {
      // Variance partition plate structure
      // Check replicate tiles first
      for (const tile of plateData.design?.replicate_tiles || []) {
        if (tile.wells.includes(wellId)) {
          if (tile.assignment.treatment === 'VEHICLE_TILE') return 'vehicle_tile';
          if (tile.assignment.treatment === 'ANCHOR_TILE') return 'anchor_tile';
        }
      }

      // Check distributed replicates
      for (const set of plateData.design?.distributed_replicates?.sets || []) {
        if (set.wells.includes(wellId)) {
          if (set.assignment.treatment === 'VEHICLE_SCATTER') return 'vehicle_scatter';
          if (set.assignment.treatment === 'ANCHOR_SCATTER') return 'anchor_scatter';
        }
      }

      return 'vehicle';
    } else {
      // Original v1 plate structure
      if (plateData.anchors.MILD.wells.includes(wellId)) return 'anchor_mild';
      if (plateData.anchors.STRONG.wells.includes(wellId)) return 'anchor_strong';
      if (plateData.tiles.wells.includes(wellId)) return 'tile';
      return 'vehicle';
    }
  };

  const getCellLine = (wellId: string) => {
    const row = wellId[0];

    if (isDynamicRange) {
      // Dynamic range uses interleaved cell lines
      return plateData.cell_lines.row_to_cell_line[row];
    } else if (isWashDamage) {
      // Wash damage uses single cell line
      return plateData.cell_lines.row_to_cell_line[row];
    } else if (isVariancePartition) {
      // Variance partition uses row_to_cell_line mapping
      return plateData.cell_lines.row_to_cell_line[row];
    } else {
      // Original v1 uses A/B groups
      return plateData.cell_lines.A.rows.includes(row) ? 'A' : 'B';
    }
  };

  const getWellColor = (type: string) => {
    if (isDynamicRange) {
      // Dynamic range: color by compound and dose gradient
      if (type === 'vehicle') return 'bg-slate-700/70';

      // Extract dose from type string
      const match = type.match(/_dose_([\d.]+)$/);
      const dose = match ? parseFloat(match[1]) : 0;

      // Oxidative stress (tBHQ) - Yellow to Orange gradient
      if (type.startsWith('ox_stress')) {
        if (dose <= 0.3) return 'bg-yellow-300/80';
        if (dose <= 1) return 'bg-yellow-400/85';
        if (dose <= 3) return 'bg-yellow-500/90';
        if (dose <= 10) return 'bg-orange-400/90';
        if (dose <= 30) return 'bg-orange-500/90';
        if (dose <= 60) return 'bg-orange-600/95';
        return 'bg-orange-700/95';
      }

      // Microtubule destabilization (Nocodazole) - Purple gradient
      if (type.startsWith('mt_destab')) {
        if (dose <= 0.01) return 'bg-purple-300/80';
        if (dose <= 0.03) return 'bg-purple-400/85';
        if (dose <= 0.1) return 'bg-purple-500/90';
        if (dose <= 0.3) return 'bg-purple-600/90';
        if (dose <= 1) return 'bg-purple-700/90';
        if (dose <= 3) return 'bg-purple-800/95';
        return 'bg-purple-900/95';
      }

      // ER stress (Thapsigargin) - Red gradient
      if (type.startsWith('er_stress')) {
        if (dose <= 0.001) return 'bg-red-300/80';
        if (dose <= 0.003) return 'bg-red-400/85';
        if (dose <= 0.01) return 'bg-red-500/90';
        if (dose <= 0.03) return 'bg-red-600/90';
        if (dose <= 0.1) return 'bg-red-700/90';
        if (dose <= 0.3) return 'bg-red-800/95';
        return 'bg-red-900/95';
      }

      return 'bg-slate-700/70';
    } else if (isWashDamage) {
      // Wash damage colors (by wash program)
      if (type === 'no_cells') return 'bg-slate-950/90';
      if (type === 'wash_gentle') return 'bg-green-500/90';
      if (type === 'wash_standard') return 'bg-blue-500/90';
      if (type === 'wash_harsh_low_height') return 'bg-orange-600/90';
      if (type === 'wash_harsh_more_cycles') return 'bg-red-600/90';
      return 'bg-slate-700/70';
    } else if (isVariancePartition) {
      // Variance partition colors
      if (type === 'anchor_tile') return 'bg-purple-600/90';
      if (type === 'anchor_scatter') return 'bg-violet-500/90';
      if (type === 'vehicle_tile') return 'bg-blue-500/90';
      if (type === 'vehicle_scatter') return 'bg-cyan-500/90';
      return 'bg-slate-700/70';
    } else {
      // Original v1 colors
      if (type === 'anchor_strong') return 'bg-red-500/90';
      if (type === 'anchor_mild') return 'bg-orange-500/90';
      if (type === 'tile') return 'bg-blue-500/90';
      return 'bg-slate-700/70';
    }
  };

  const getBorderColor = (cellLine: string) => {
    if (isDynamicRange) {
      // Interleaved cell lines
      return cellLine === 'HepG2' ? '#ec4899' : '#a855f7';
    } else if (isWashDamage) {
      // Single cell line (A549) - use purple
      return '#a855f7';
    } else if (isVariancePartition) {
      return cellLine === 'HepG2' ? '#ec4899' : '#a855f7';
    } else {
      return cellLine === 'A' ? '#ec4899' : '#a855f7';
    }
  };

  const wellData: WellData[] = [];
  rows.forEach((row: string) => {
    cols.forEach((col: number) => {
      const wellId = `${row}${col}`;
      const wellType = getWellType(wellId);
      const cellLine = getCellLine(wellId);

      // Get dose info for dynamic range plates
      let doseInfo = '';
      if (isDynamicRange) {
        const col = parseInt(wellId.slice(1));
        for (const anchor of plateData.anchors || []) {
          const dose = anchor.dose_uM_by_column?.[col.toString()];
          if (dose !== undefined) {
            doseInfo = dose === 0 ? 'Vehicle' : `${anchor.reagent} ${dose}µM`;
            break;
          }
        }
      }

      wellData.push({
        id: wellId,
        color: getWellColor(wellType),
        borderColor: getBorderColor(cellLine),
        borderWidth: 2,
        tooltip: {
          title: wellId,
          lines: isDynamicRange
            ? [
                doseInfo,
                cellLine,
              ]
            : isWashDamage
              ? [
                  wellType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                  cellLine,
                ]
              : isVariancePartition
                ? [
                    wellType.replace(/_/g, ' '),
                    cellLine,
                  ]
                : [
                    wellType.replace('_', ' '),
                    cellLine === 'A' ? 'HepG2' : 'A549',
                  ],
        },
      });
    });
  });

  return (
    <div className="space-y-4">
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">
              {plateData.plate.plate_id}
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              {plateData.intent}
            </p>
            <p className="text-sm text-slate-400">
              384-well plate (16 rows × 24 columns)
            </p>
          </div>
          <div className="flex gap-2">
            {onSimulate && (
              <button
                onClick={() => onSimulate(plateData)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all text-sm font-medium"
              >
                <Play className="h-4 w-4" />
                Simulate
              </button>
            )}
            <button
              onClick={downloadPlateJSON}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all text-sm font-medium"
            >
              <Download className="h-4 w-4" />
              Download JSON
            </button>
          </div>
        </div>

        <PlateViewer
          format="384"
          wells={wellData}
          isDarkMode={isDarkMode}
          size="medium"
          showLabels={false}
          showAxisLabels={true}
        />

        {/* Legend */}
        {isDynamicRange ? (
          // Dynamic Range Legend
          <div className="mt-6 space-y-4">
            <div>
              <div className="text-sm font-semibold text-white mb-3">Dose-Response Curves (fill, by column):</div>
              <div className="space-y-3 text-sm">
                {/* tBHQ */}
                <div>
                  <div className="text-xs font-semibold text-yellow-400 mb-2">tBHQ (Oxidative Stress) - Cols 1-8:</div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-slate-700/70"></div>
                    <div className="w-3 h-3 bg-yellow-300/80"></div>
                    <div className="w-3 h-3 bg-yellow-400/85"></div>
                    <div className="w-3 h-3 bg-yellow-500/90"></div>
                    <div className="w-3 h-3 bg-orange-400/90"></div>
                    <div className="w-3 h-3 bg-orange-500/90"></div>
                    <div className="w-3 h-3 bg-orange-600/95"></div>
                    <div className="w-3 h-3 bg-orange-700/95"></div>
                    <span className="text-slate-300 text-xs ml-2">0 → 0.3 → 1 → 3 → 10 → 30 → 60 → 100 µM</span>
                  </div>
                </div>

                {/* Nocodazole */}
                <div>
                  <div className="text-xs font-semibold text-purple-400 mb-2">Nocodazole (MT Destabilization) - Cols 9-16:</div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-slate-700/70"></div>
                    <div className="w-3 h-3 bg-purple-300/80"></div>
                    <div className="w-3 h-3 bg-purple-400/85"></div>
                    <div className="w-3 h-3 bg-purple-500/90"></div>
                    <div className="w-3 h-3 bg-purple-600/90"></div>
                    <div className="w-3 h-3 bg-purple-700/90"></div>
                    <div className="w-3 h-3 bg-purple-800/95"></div>
                    <div className="w-3 h-3 bg-purple-900/95"></div>
                    <span className="text-slate-300 text-xs ml-2">0 → 0.01 → 0.03 → 0.1 → 0.3 → 1 → 3 → 10 µM</span>
                  </div>
                </div>

                {/* Thapsigargin */}
                <div>
                  <div className="text-xs font-semibold text-red-400 mb-2">Thapsigargin (ER Stress) - Cols 17-24:</div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-slate-700/70"></div>
                    <div className="w-3 h-3 bg-red-300/80"></div>
                    <div className="w-3 h-3 bg-red-400/85"></div>
                    <div className="w-3 h-3 bg-red-500/90"></div>
                    <div className="w-3 h-3 bg-red-600/90"></div>
                    <div className="w-3 h-3 bg-red-700/90"></div>
                    <div className="w-3 h-3 bg-red-800/95"></div>
                    <div className="w-3 h-3 bg-red-900/95"></div>
                    <span className="text-slate-300 text-xs ml-2">0 → 0.001 → 0.003 → 0.01 → 0.03 → 0.1 → 0.3 → 1 µM</span>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Purpose:</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>• <strong>Find saturation points:</strong> Where does Cell Painting saturate for each compound?</div>
                <div>• <strong>Map LDH range:</strong> Where is LDH responsive vs insensitive?</div>
                <div>• <strong>Optimal calibration window:</strong> Morphology responsive while LDH flat</div>
                <div>• <strong>Cell line differences:</strong> Do HepG2 and A549 have different dose-response slopes?</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Cell lines (border, interleaved rows):</div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                  <span className="text-slate-300">A549 (even rows: B, D, F, H, J, L, N, P)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-pink-500 rounded"></div>
                  <span className="text-slate-300">HepG2 (odd rows: A, C, E, G, I, K, M, O)</span>
                </div>
              </div>
            </div>
          </div>
        ) : isWashDamage ? (
          // Wash Damage Legend
          <div className="mt-6 space-y-4">
            <div>
              <div className="text-sm font-semibold text-white mb-3">Wash Programs (fill, by column):</div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-green-500/90"></div>
                  <span className="text-slate-300">Gentle (cols 1-6) - High height, low speed</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-blue-500/90"></div>
                  <span className="text-slate-300">Standard (cols 7-12) - Reference protocol</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-orange-600/90"></div>
                  <span className="text-slate-300">Harsh Low Height (cols 13-18) - 0.6mm, shear risk</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-red-600/90"></div>
                  <span className="text-slate-300">Harsh More Cycles (cols 19-24) - 5 cycles, high speed</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-slate-950/90"></div>
                  <span className="text-slate-300">No Cells (background control)</span>
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Purpose:</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>• <strong>Isolate wash artifacts:</strong> Does morphology shift by wash program?</div>
                <div>• <strong>Physical damage:</strong> Does LDH rise under harsh programs?</div>
                <div>• <strong>Residual stain:</strong> Do no-cells wells show wash-dependent background?</div>
                <div>• <strong>Segmentation failures:</strong> Does harsh washing cause detection issues?</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Cell line (border):</div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                  <span className="text-slate-300">A549 (all wells)</span>
                </div>
              </div>
            </div>
          </div>
        ) : isVariancePartition ? (
          // Variance Partition Legend
          <div className="mt-6 space-y-4">
            <div>
              <div className="text-sm font-semibold text-white mb-3">Replicate Types (fill):</div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-slate-700/70"></div>
                  <span className="text-slate-300">Vehicle (default)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-blue-500/90"></div>
                  <span className="text-slate-300">Vehicle Tile (local replicates)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-cyan-500/90"></div>
                  <span className="text-slate-300">Vehicle Scatter (global replicates)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-purple-600/90"></div>
                  <span className="text-slate-300">Anchor Tile (Nocodazole 0.3µM, local)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-violet-500/90"></div>
                  <span className="text-slate-300">Anchor Scatter (Nocodazole 0.3µM, global)</span>
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Purpose:</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>• <strong>Tiles (2x2):</strong> Measure local variance (technical noise floor)</div>
                <div>• <strong>Scatter:</strong> Measure global variance (spatial + technical)</div>
                <div>• <strong>4 Quadrants:</strong> Estimate quadrant-specific effects</div>
                <div>• <strong>Compare:</strong> σ²_local vs σ²_spatial vs σ²_quadrant vs σ²_biological</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Cell lines (border, interleaved rows):</div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                  <span className="text-slate-300">A549 (rows B, D, F, H, J, L, N, P)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-pink-500 rounded"></div>
                  <span className="text-slate-300">HepG2 (rows A, C, E, G, I, K, M, O)</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          // Original V1 Legend
          <div className="mt-6 space-y-4">
            <div>
              <div className="text-sm font-semibold text-white mb-3">Compounds (fill):</div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-slate-700/70"></div>
                  <span className="text-slate-300">Vehicle (DMSO)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-orange-500/90"></div>
                  <span className="text-slate-300">Anchor Mild (1µM)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-red-500/90"></div>
                  <span className="text-slate-300">Anchor Strong (100µM)</span>
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">QC Features:</div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-blue-500/90"></div>
                  <span className="text-slate-300">Tiles (2x2 vehicle replicates for spatial QC)</span>
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-white mb-3">Cell lines (border):</div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                  <span className="text-slate-300">A549</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-pink-500 rounded"></div>
                  <span className="text-slate-300">HepG2</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// V2 Viewer (more complex with probes, gradients, etc.)
function PlateViewerV2({ plateData, isDarkMode, onSimulate }: { plateData: any; isDarkMode: boolean; onSimulate?: (plateData: any) => void }) {
  const rows = plateData.plate.rows;
  const cols = plateData.plate.cols;

  const downloadPlateJSON = () => {
    const dataStr = JSON.stringify(plateData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `${plateData.plate.plate_id}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  // Helper to get well assignments for v2
  const getWellAssignment = (wellId: string) => {
    const row = wellId[0];
    const col = parseInt(wellId.slice(1));

    // Background controls (no cells)
    if (plateData.non_biological_provocations.background_controls.wells_no_cells.includes(wellId)) {
      return { type: 'no_cells', detail: 'No cells' };
    }

    // Tiles
    for (const tile of plateData.contrastive_tiles.tiles) {
      if (tile.wells.includes(wellId)) {
        return { type: 'tile', detail: tile.tile_id };
      }
    }

    // Anchors
    if (plateData.biological_anchors.wells.ANCHOR_MORPH?.includes(wellId)) {
      return { type: 'anchor_morph', detail: 'Nocodazole 0.3µM' };
    }
    if (plateData.biological_anchors.wells.ANCHOR_DEATH?.includes(wellId)) {
      return { type: 'anchor_death', detail: 'Thapsigargin 0.05µM' };
    }

    // Probes
    const probes = plateData.non_biological_provocations;
    if (probes.stain_scale_probes.wells.STAIN_LOW?.includes(wellId)) {
      return { type: 'stain_low', detail: 'Stain 0.9x' };
    }
    if (probes.stain_scale_probes.wells.STAIN_HIGH?.includes(wellId)) {
      return { type: 'stain_high', detail: 'Stain 1.1x' };
    }
    if (probes.fixation_timing_probes.wells.EARLY_FIX?.includes(wellId)) {
      return { type: 'fix_early', detail: 'Early fix -15min' };
    }
    if (probes.fixation_timing_probes.wells.LATE_FIX?.includes(wellId)) {
      return { type: 'fix_late', detail: 'Late fix +15min' };
    }
    if (probes.imaging_focus_probes.wells.FOCUS_MINUS?.includes(wellId)) {
      return { type: 'focus_minus', detail: 'Focus -2µm' };
    }
    if (probes.imaging_focus_probes.wells.FOCUS_PLUS?.includes(wellId)) {
      return { type: 'focus_plus', detail: 'Focus +2µm' };
    }

    // Density gradient
    const densityGradient = probes.cell_density_gradient.rule;
    let density = 'NOMINAL';
    if (densityGradient.LOW_cols.includes(col)) density = 'LOW';
    else if (densityGradient.HIGH_cols.includes(col)) density = 'HIGH';

    return { type: 'vehicle', detail: `Vehicle (${density} density)` };
  };

  const getWellColor = (assignment: any) => {
    switch (assignment.type) {
      case 'no_cells': return 'bg-slate-900/90';
      case 'anchor_morph': return 'bg-purple-600/90';
      case 'anchor_death': return 'bg-red-600/90';
      case 'tile': return 'bg-blue-500/90';
      case 'stain_low': return 'bg-yellow-600/90';
      case 'stain_high': return 'bg-orange-600/90';
      case 'fix_early': return 'bg-cyan-600/90';
      case 'fix_late': return 'bg-teal-600/90';
      case 'focus_minus': return 'bg-pink-600/90';
      case 'focus_plus': return 'bg-rose-600/90';
      default: return 'bg-slate-700/70';
    }
  };

  const getCellLineBorderColor = (wellId: string) => {
    const row = wellId[0];
    const cellLine = plateData.cell_lines.row_to_cell_line[row];
    return cellLine === 'HepG2' ? '#ec4899' : '#a855f7';
  };

  const wellData: WellData[] = [];
  rows.forEach((row: string) => {
    cols.forEach((col: number) => {
      const wellId = `${row}${col}`;
      const assignment = getWellAssignment(wellId);
      const cellLine = plateData.cell_lines.row_to_cell_line[row];

      wellData.push({
        id: wellId,
        color: getWellColor(assignment),
        borderColor: getCellLineBorderColor(wellId),
        borderWidth: 2,
        tooltip: {
          title: wellId,
          lines: [
            assignment.detail,
            cellLine,
          ],
        },
      });
    });
  });

  return (
    <div className="space-y-4">
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">
              {plateData.plate.plate_id}
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              {plateData.intent}
            </p>
            <p className="text-sm text-slate-400">
              384-well plate (16 rows × 24 columns) - Interleaved cell lines
            </p>
          </div>
          <div className="flex gap-2">
            {onSimulate && (
              <button
                onClick={() => onSimulate(plateData)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all text-sm font-medium"
              >
                <Play className="h-4 w-4" />
                Simulate
              </button>
            )}
            <button
              onClick={downloadPlateJSON}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all text-sm font-medium"
            >
              <Download className="h-4 w-4" />
              Download JSON
            </button>
          </div>
        </div>

        <PlateViewer
          format="384"
          wells={wellData}
          isDarkMode={isDarkMode}
          size="medium"
          showLabels={false}
          showAxisLabels={true}
        />

        {/* V2 Legend - More Complex */}
        <div className="mt-6 space-y-4">
          <div>
            <div className="text-sm font-semibold text-white mb-3">Biological Anchors:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-purple-600/90"></div>
                <span className="text-slate-300">Nocodazole (morph anchor)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-red-600/90"></div>
                <span className="text-slate-300">Thapsigargin (death anchor)</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">Non-Biological Probes:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-yellow-600/90"></div>
                <span className="text-slate-300">Stain 0.9x</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-orange-600/90"></div>
                <span className="text-slate-300">Stain 1.1x</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-cyan-600/90"></div>
                <span className="text-slate-300">Early fix (-15min)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-teal-600/90"></div>
                <span className="text-slate-300">Late fix (+15min)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-pink-600/90"></div>
                <span className="text-slate-300">Focus -2µm</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-rose-600/90"></div>
                <span className="text-slate-300">Focus +2µm</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">QC Features:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-blue-500/90"></div>
                <span className="text-slate-300">Contrastive tiles</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-900/90"></div>
                <span className="text-slate-300">No-cell controls</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-700/70"></div>
                <span className="text-slate-300">Vehicle (density gradient)</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">Cell lines (border, interleaved rows):</div>
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                <span className="text-slate-300">A549 (alt rows)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-pink-500 rounded"></div>
                <span className="text-slate-300">HepG2 (alt rows)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Microscope Calibration Viewer (dyes, beads, no cells)
function PlateViewerMicroscope({ plateData, isDarkMode, onSimulate }: { plateData: any; isDarkMode: boolean; onSimulate?: (plateData: any) => void }) {
  const rows = plateData.plate.rows;
  const cols = plateData.plate.cols;

  const downloadPlateJSON = () => {
    const dataStr = JSON.stringify(plateData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `${plateData.plate.plate_id}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  // Helper to get material assignment for microscope plate
  const getWellMaterial = (wellId: string) => {
    const assignments = plateData.explicit_assignments;

    // Dark wells
    if (assignments.dark_wells.wells.includes(wellId)) {
      return { type: 'dark', detail: 'Dark (camera baseline)' };
    }

    // Blank wells
    if (assignments.blank_wells.wells.includes(wellId)) {
      return { type: 'blank', detail: 'Blank (dust/artifacts)' };
    }

    // Flatfield high
    if (assignments.flatfield_high.wells.includes(wellId)) {
      return { type: 'flatfield_high', detail: 'Flatfield dye (high)' };
    }

    // Sparse beads
    if (assignments.multicolor_beads_sparse.wells.includes(wellId)) {
      return { type: 'beads_sparse', detail: 'Multicolor beads (sparse)' };
    }

    // Dense beads
    if (assignments.multicolor_beads_dense.wells.includes(wellId)) {
      return { type: 'beads_dense', detail: 'Multicolor beads (dense)' };
    }

    // Focus beads
    if (assignments.focus_beads_map.wells.includes(wellId)) {
      return { type: 'focus_beads', detail: 'Focus beads' };
    }

    // Tiles
    for (const tile of plateData.repeatability_tiles.tiles) {
      if (tile.wells.includes(wellId)) {
        return { type: 'tile_' + tile.material.toLowerCase(), detail: tile.tile_id };
      }
    }

    // Default: Flatfield low
    return { type: 'flatfield_low', detail: 'Flatfield dye (low)' };
  };

  const getWellColor = (material: any) => {
    switch (material.type) {
      case 'dark': return 'bg-slate-950/90';
      case 'blank': return 'bg-slate-900/70';
      case 'flatfield_low': return 'bg-cyan-500/80';
      case 'flatfield_high': return 'bg-cyan-700/90';
      case 'tile_flatfield_dye_low': return 'bg-cyan-500/90';
      case 'beads_sparse': return 'bg-yellow-500/90';
      case 'beads_dense': return 'bg-orange-500/90';
      case 'tile_multicolor_beads_sparse': return 'bg-yellow-600/90';
      case 'tile_multicolor_beads_dense': return 'bg-orange-600/90';
      case 'focus_beads': return 'bg-green-500/90';
      default: return 'bg-slate-700/70';
    }
  };

  const wellData: WellData[] = [];
  rows.forEach((row: string) => {
    cols.forEach((col: number) => {
      const wellId = `${row}${col}`;
      const material = getWellMaterial(wellId);

      wellData.push({
        id: wellId,
        color: getWellColor(material),
        borderColor: '#64748b', // Gray border for all (no cell lines)
        borderWidth: 1,
        tooltip: {
          title: wellId,
          lines: [material.detail],
        },
      });
    });
  });

  return (
    <div className="space-y-4">
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">
              {plateData.plate.plate_id}
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              {plateData.intent}
            </p>
            <p className="text-sm text-slate-400">
              384-well plate (16 rows × 24 columns) - No cells, microscope calibration only
            </p>
          </div>
          <div className="flex gap-2">
            {onSimulate && (
              <button
                onClick={() => onSimulate(plateData)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all text-sm font-medium"
              >
                <Play className="h-4 w-4" />
                Simulate
              </button>
            )}
            <button
              onClick={downloadPlateJSON}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all text-sm font-medium"
            >
              <Download className="h-4 w-4" />
              Download JSON
            </button>
          </div>
        </div>

        <PlateViewer
          format="384"
          wells={wellData}
          isDarkMode={isDarkMode}
          size="medium"
          showLabels={false}
          showAxisLabels={true}
        />

        {/* Legend */}
        <div className="mt-6 space-y-4">
          <div>
            <div className="text-sm font-semibold text-white mb-3">Flat-Field Materials:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-cyan-500/80"></div>
                <span className="text-slate-300">Flatfield dye (low intensity)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-cyan-700/90"></div>
                <span className="text-slate-300">Flatfield dye (high intensity)</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">Bead Materials:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-yellow-500/90"></div>
                <span className="text-slate-300">Multicolor beads (sparse)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-orange-500/90"></div>
                <span className="text-slate-300">Multicolor beads (dense)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-green-500/90"></div>
                <span className="text-slate-300">Focus beads</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">Controls:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-950/90"></div>
                <span className="text-slate-300">Dark (camera baseline)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-900/70"></div>
                <span className="text-slate-300">Blank (dust/artifacts)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Purpose callout */}
        <div className="mt-6 p-4 rounded-lg bg-indigo-900/20 border border-indigo-700/50">
          <div className="text-sm font-semibold text-indigo-300 mb-2">
            Purpose: Run BEFORE biological plates
          </div>
          <div className="text-xs text-indigo-200 space-y-1">
            <div>• Learn illumination non-uniformity and vignetting (flat-field)</div>
            <div>• Measure chromatic registration across field (sparse beads)</div>
            <div>• Map focus performance and field curvature (focus beads)</div>
            <div>• Estimate camera baseline and noise (dark wells)</div>
            <div>• Detect plate artifacts and dust (blank wells)</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Liquid Handler Calibration Viewer (channel bias, carryover, mixing)
function PlateViewerLiquidHandler({ plateData, isDarkMode, onSimulate }: { plateData: any; isDarkMode: boolean; onSimulate?: (plateData: any) => void }) {
  const rows = plateData.plate.rows;
  const cols = plateData.plate.cols;

  const downloadPlateJSON = () => {
    const dataStr = JSON.stringify(plateData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `${plateData.plate.plate_id}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  // Helper to get well assignment for liquid handler plate
  const getWellAssignment = (wellId: string) => {
    const row = wellId[0];
    const col = parseInt(wellId.slice(1));

    // R5: Mix program tiles (highest precedence)
    for (const tile of plateData.regions.R5_mix_program_tiles.tiles) {
      if (tile.wells.includes(wellId)) {
        const isMixMinimal = tile.assignment.mix_program_id === 'MIX_MINIMAL';
        return {
          type: isMixMinimal ? 'mix_minimal' : 'mix_aggressive',
          detail: `${tile.assignment.reagent} ${tile.assignment.dose_uM}µM (${tile.assignment.mix_program_id})`,
          dose: tile.assignment.dose_uM
        };
      }
    }

    // R4: Carryover checkerboard (cols 1-2)
    if (col === 1 || col === 2) {
      // Calculate dispense order index for alternation
      // In column-wise dispense: col 1 pass 1 (rows A-H), col 1 pass 2 (rows I-P), col 2 pass 1, col 2 pass 2
      const passNum = ['A','B','C','D','E','F','G','H'].includes(row) ? 1 : 2;
      const rowIndexInPass = passNum === 1
        ? ['A','B','C','D','E','F','G','H'].indexOf(row)
        : ['I','J','K','L','M','N','O','P'].indexOf(row);
      const dispenseIndex = (col - 1) * 16 + (passNum - 1) * 8 + rowIndexInPass;

      const isEven = dispenseIndex % 2 === 0;
      if (isEven) {
        return { type: 'carryover_high', detail: 'Nocodazole 3µM (carryover test)', dose: 3.0 };
      } else {
        return { type: 'carryover_blank', detail: 'DMSO blank (carryover test)', dose: 0 };
      }
    }

    // R2: Order drift ladder early (cols 7-12)
    const earlyLadderMapping: { [key: number]: number } = {
      7: 0.003, 8: 0.006, 9: 0.012, 10: 0.024, 11: 0.049, 12: 0.098
    };
    if (col >= 7 && col <= 12) {
      const dose = earlyLadderMapping[col];
      return { type: 'ladder_early', detail: `Nocodazole ${dose}µM (early ladder)`, dose };
    }

    // R3: Order drift ladder late (cols 19-24)
    const lateLadderMapping: { [key: number]: number } = {
      19: 0.195, 20: 0.391, 21: 0.781, 22: 1.56, 23: 3.12, 24: 6.25
    };
    if (col >= 19 && col <= 24) {
      const dose = lateLadderMapping[col];
      return { type: 'ladder_late', detail: `Nocodazole ${dose}µM (late ladder)`, dose };
    }

    // R1: Default vehicle baseline
    return { type: 'vehicle', detail: 'DMSO vehicle (baseline)', dose: 0 };
  };

  const getWellColor = (assignment: any) => {
    switch (assignment.type) {
      case 'vehicle': return 'bg-slate-700/70';
      case 'carryover_high': return 'bg-red-600/90';
      case 'carryover_blank': return 'bg-slate-950/90';
      case 'mix_minimal': return 'bg-purple-600/90';
      case 'mix_aggressive': return 'bg-pink-600/90';
      case 'ladder_early':
      case 'ladder_late':
        // Gradient based on dose (log scale for better visual distribution)
        const dose = assignment.dose;
        if (dose <= 0.003) return 'bg-blue-300/80';
        if (dose <= 0.006) return 'bg-blue-400/80';
        if (dose <= 0.012) return 'bg-blue-500/80';
        if (dose <= 0.024) return 'bg-blue-600/85';
        if (dose <= 0.049) return 'bg-blue-600/90';
        if (dose <= 0.098) return 'bg-blue-700/90';
        if (dose <= 0.195) return 'bg-indigo-600/90';
        if (dose <= 0.391) return 'bg-indigo-700/90';
        if (dose <= 0.781) return 'bg-indigo-800/90';
        if (dose <= 1.56) return 'bg-violet-700/90';
        if (dose <= 3.12) return 'bg-violet-800/90';
        return 'bg-violet-900/90';
      default: return 'bg-slate-700/70';
    }
  };

  const getCellLineBorderColor = (wellId: string) => {
    const row = wellId[0];
    const cellLine = plateData.cell_lines.row_to_cell_line[row];
    return cellLine === 'HepG2' ? '#ec4899' : '#a855f7';
  };

  const wellData: WellData[] = [];
  rows.forEach((row: string) => {
    cols.forEach((col: number) => {
      const wellId = `${row}${col}`;
      const assignment = getWellAssignment(wellId);
      const cellLine = plateData.cell_lines.row_to_cell_line[row];

      wellData.push({
        id: wellId,
        color: getWellColor(assignment),
        borderColor: getCellLineBorderColor(wellId),
        borderWidth: 2,
        tooltip: {
          title: wellId,
          lines: [
            assignment.detail,
            cellLine,
          ],
        },
      });
    });
  });

  return (
    <div className="space-y-4">
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">
              {plateData.plate.plate_id}
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              {plateData.intent}
            </p>
            <p className="text-sm text-slate-400">
              384-well plate (16 rows × 24 columns) - Interleaved cell lines
            </p>
          </div>
          <div className="flex gap-2">
            {onSimulate && (
              <button
                onClick={() => onSimulate(plateData)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all text-sm font-medium"
              >
                <Play className="h-4 w-4" />
                Simulate
              </button>
            )}
            <button
              onClick={downloadPlateJSON}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all text-sm font-medium"
            >
              <Download className="h-4 w-4" />
              Download JSON
            </button>
          </div>
        </div>

        <PlateViewer
          format="384"
          wells={wellData}
          isDarkMode={isDarkMode}
          size="medium"
          showLabels={false}
          showAxisLabels={true}
        />

        {/* Legend */}
        <div className="mt-6 space-y-4">
          <div>
            <div className="text-sm font-semibold text-white mb-3">Regions & Treatments:</div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-700/70"></div>
                <span className="text-slate-300">Vehicle baseline (most wells)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-blue-500/80"></div>
                <span className="text-slate-300">Ladder early (cols 7-12, low doses)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-indigo-700/90"></div>
                <span className="text-slate-300">Ladder late (cols 19-24, high doses)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-red-600/90"></div>
                <span className="text-slate-300">Carryover high (cols 1-2, alternating)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-slate-950/90"></div>
                <span className="text-slate-300">Carryover blank (cols 1-2, alternating)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-purple-600/90"></div>
                <span className="text-slate-300">Mix minimal (2x2 tiles)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-pink-600/90"></div>
                <span className="text-slate-300">Mix aggressive (2x2 tiles)</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-white mb-3">Cell lines (border, interleaved rows):</div>
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-purple-500 rounded"></div>
                <span className="text-slate-300">A549 (even rows: B, D, F, H, J, L, N, P)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-pink-500 rounded"></div>
                <span className="text-slate-300">HepG2 (odd rows: A, C, E, G, I, K, M, O)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Analysis Questions callout */}
        <div className="mt-6 p-4 rounded-lg bg-amber-900/20 border border-amber-700/50">
          <div className="text-sm font-semibold text-amber-300 mb-2">
            Analysis Questions This Plate Should Answer:
          </div>
          <div className="text-xs text-amber-200 space-y-1">
            <div>• <strong>Channel bias:</strong> Do baseline wells cluster by channel_id?</div>
            <div>• <strong>Order drift:</strong> Do dose-response curves differ between early (cols 7-12) vs late (cols 19-24) regions?</div>
            <div>• <strong>Carryover:</strong> Do blanks following high wells show contamination?</div>
            <div>• <strong>Mixing sensitivity:</strong> Does aggressive mixing reduce variance vs minimal mixing?</div>
            <div>• <strong>Cell line interactions:</strong> Are any artifacts cell-line-specific?</div>
          </div>
        </div>

        {/* Expected Failure Signatures */}
        <div className="mt-4 p-4 rounded-lg bg-red-900/20 border border-red-700/50">
          <div className="text-sm font-semibold text-red-300 mb-2">
            Expected Failure Signatures:
          </div>
          <div className="text-xs text-red-200 space-y-1">
            <div>• <strong>Channel bias:</strong> Striping aligned to dispense channel under vehicle</div>
            <div>• <strong>Order drift:</strong> Systematic shift in curves between early vs late, or monotonic trend with dispense order</div>
            <div>• <strong>Carryover:</strong> Blanks after highs resemble low/intermediate doses</div>
            <div>• <strong>Mixing artifact:</strong> MIX_MINIMAL shows higher variance or inconsistent effect size</div>
          </div>
        </div>
      </div>
    </div>
  );
}
