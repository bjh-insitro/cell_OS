import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import CalibrationPlateViewer from '../components/CalibrationPlateViewer';

const AVAILABLE_DESIGNS = [
  {
    id: 'microscope',
    name: 'CAL_384_MICROSCOPE_BEADS_DYES_v1',
    description: 'Microscope calibration - dyes, beads, no cells',
    version: 'microscope'
  },
  {
    id: 'v1',
    name: 'CAL_384_RULES_WORLD_v1',
    description: 'Simple calibration - anchors, tiles, vehicle',
    version: 'v1'
  },
  {
    id: 'v2',
    name: 'CAL_384_RULES_WORLD_v2',
    description: 'Advanced - interleaved cells, density gradient, probes',
    version: 'v2'
  },
  {
    id: 'lh',
    name: 'CAL_384_LH_ARTIFACTS_v1',
    description: 'Liquid handler artifacts - channel bias, carryover, mixing',
    version: 'lh'
  },
  {
    id: 'variance',
    name: 'CAL_VARIANCE_PARTITION_v1',
    description: 'Variance components - local vs global, quadrants, replicates',
    version: 'variance'
  },
  {
    id: 'wash',
    name: 'CAL_EL406_WASH_DAMAGE_v1',
    description: 'EL406 wash stress - aspiration shear, residual volume effects',
    version: 'wash'
  },
  {
    id: 'dynamic',
    name: 'CAL_DYNAMIC_RANGE_v1',
    description: 'Dynamic range - dose-response curves, saturation mapping',
    version: 'dynamic'
  }
];

export default function CalibrationPlatePage() {
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [selectedDesign, setSelectedDesign] = useState('v1');

  const currentDesign = AVAILABLE_DESIGNS.find(d => d.id === selectedDesign) || AVAILABLE_DESIGNS[0];

  const handleSimulate = (plateData: any) => {
    console.log('Starting simulation for plate:', plateData.plate.plate_id);

    // Generate realistic mock data
    const rows = plateData.plate.rows;
    const cols = plateData.plate.cols;
    const measurements: any[] = [];

    // Helper functions for realistic patterns
    const getEdgeFactor = (row: string, col: number): number => {
      // Edge wells have lower signal (evaporation, temperature)
      const rowIdx = rows.indexOf(row);
      const isEdgeRow = rowIdx === 0 || rowIdx === rows.length - 1;
      const isEdgeCol = col === 1 || col === cols[cols.length - 1];
      return (isEdgeRow || isEdgeCol) ? 0.85 : 1.0;
    };

    const getColumnGradient = (col: number): number => {
      // Subtle left-to-right gradient (pipetting order effect)
      return 0.95 + (col / cols.length) * 0.10;
    };

    const getTreatmentEffect = (wellId: string, channel: string): number => {
      // V1 plate: check anchors
      if (plateData.schema_version === 'calibration_plate_v1') {
        if (plateData.anchors?.MILD?.wells?.includes(wellId)) {
          // Mild anchor (1µM) - moderate effect
          if (channel === 'mito') return 0.7; // Reduced mito
          if (channel === 'dna') return 1.2; // Increased DNA condensation
          return 1.0;
        }
        if (plateData.anchors?.STRONG?.wells?.includes(wellId)) {
          // Strong anchor (100µM) - strong effect
          if (channel === 'mito') return 0.4; // Much reduced mito
          if (channel === 'dna') return 1.5; // Strong DNA condensation
          if (channel === 'agp') return 0.8; // Golgi disruption
          return 1.0;
        }
      }

      // V2 plate: check biological anchors
      if (plateData.schema_version === 'calibration_plate_v2') {
        if (plateData.biological_anchors?.wells?.ANCHOR_MORPH?.includes(wellId)) {
          // Nocodazole - microtubule depolymerizer
          if (channel === 'mito') return 0.5; // Mito disrupted
          if (channel === 'dna') return 1.3; // Condensed
          if (channel === 'agp') return 0.7; // Golgi affected
          return 1.0;
        }
        if (plateData.biological_anchors?.wells?.ANCHOR_DEATH?.includes(wellId)) {
          // Thapsigargin - ER stress, cell death
          if (channel === 'er') return 0.3; // ER collapse
          if (channel === 'mito') return 0.4; // Mito dysfunction
          if (channel === 'dna') return 0.6; // Fragmentation
          return 0.7;
        }
      }

      // Wash damage plate: wash program effects
      if (plateData.plate?.plate_id === 'CAL_EL406_WASH_DAMAGE_v1') {
        const col = parseInt(wellId.slice(1));

        // No-cells wells have very low signal
        if (plateData.design?.no_cells_background?.wells?.includes(wellId)) {
          return 0.1; // Almost no signal
        }

        // Determine wash program by column
        let washEffect = 1.0;
        if (col >= 1 && col <= 6) {
          // WASH_GENTLE - minimal damage, but residual stain (higher background)
          if (channel === 'dna') return 1.05; // Slightly higher (residual stain)
          if (channel === 'er') return 1.03;
          washEffect = 1.02;
        } else if (col >= 7 && col <= 12) {
          // WASH_STANDARD - reference
          washEffect = 1.0;
        } else if (col >= 13 && col <= 18) {
          // WASH_HARSH_LOW_HEIGHT - physical damage from low aspiration
          if (channel === 'dna') return 0.85; // Cell loss/damage
          if (channel === 'mito') return 0.75; // Mitochondrial damage
          if (channel === 'er') return 0.80; // ER stress from shear
          washEffect = 0.85;
        } else if (col >= 19 && col <= 24) {
          // WASH_HARSH_MORE_CYCLES - repeated stress
          if (channel === 'dna') return 0.70; // More cell loss
          if (channel === 'mito') return 0.60; // Severe mito damage
          if (channel === 'er') return 0.70; // Severe ER stress
          if (channel === 'agp') return 0.75; // Membrane damage
          washEffect = 0.70;
        }

        return washEffect;
      }

      // Variance partition plate: anchor effects
      if (plateData.plate?.plate_id === 'CAL_VARIANCE_PARTITION_v1') {
        // Check anchor tiles
        for (const tile of plateData.design?.replicate_tiles || []) {
          if (tile.wells.includes(wellId) && tile.assignment.treatment === 'ANCHOR_TILE') {
            // Nocodazole effect
            if (channel === 'mito') return 0.6;
            if (channel === 'dna') return 1.3;
            if (channel === 'agp') return 0.8;
            return 1.0;
          }
        }

        // Check anchor scatter
        for (const set of plateData.design?.distributed_replicates?.sets || []) {
          if (set.wells.includes(wellId) && set.assignment.treatment === 'ANCHOR_SCATTER') {
            // Nocodazole effect
            if (channel === 'mito') return 0.6;
            if (channel === 'dna') return 1.3;
            if (channel === 'agp') return 0.8;
            return 1.0;
          }
        }
      }

      // Dynamic range plate: dose-response curves
      if (plateData.plate?.plate_id === 'CAL_DYNAMIC_RANGE_v1') {
        const col = parseInt(wellId.slice(1));

        // Determine compound and dose by column
        for (const anchor of plateData.anchors || []) {
          const dose = anchor.dose_uM_by_column?.[col.toString()];
          if (dose !== undefined && dose > 0) {
            // tBHQ (Oxidative Stress) - cols 1-8
            if (anchor.anchor_id === 'OX_STRESS') {
              // Sigmoidal dose-response with EC50 ~ 10 µM
              const ec50 = 10.0;
              const hillSlope = 1.5;
              const fractionalEffect = Math.pow(dose / ec50, hillSlope) / (1 + Math.pow(dose / ec50, hillSlope));

              // Channel-specific effects
              if (channel === 'mito') {
                // Mito dysfunction: 1.0 → 0.3 at saturation
                return 1.0 - (fractionalEffect * 0.7);
              }
              if (channel === 'er') {
                // ER stress response: 1.0 → 0.5 at saturation
                return 1.0 - (fractionalEffect * 0.5);
              }
              if (channel === 'dna') {
                // Nuclear condensation: 1.0 → 1.4 at saturation
                return 1.0 + (fractionalEffect * 0.4);
              }
              if (channel === 'agp') {
                // Golgi fragmentation: 1.0 → 0.7 at saturation
                return 1.0 - (fractionalEffect * 0.3);
              }
              if (channel === 'rna') {
                // RNA stress response: 1.0 → 1.2 at saturation
                return 1.0 + (fractionalEffect * 0.2);
              }
            }

            // Nocodazole (MT Destabilization) - cols 9-16
            if (anchor.anchor_id === 'MT_DESTAB') {
              // Sigmoidal dose-response with EC50 ~ 0.3 µM
              const ec50 = 0.3;
              const hillSlope = 2.0;
              const fractionalEffect = Math.pow(dose / ec50, hillSlope) / (1 + Math.pow(dose / ec50, hillSlope));

              // Channel-specific effects
              if (channel === 'mito') {
                // Mito redistribution/fragmentation: 1.0 → 0.4 at saturation
                return 1.0 - (fractionalEffect * 0.6);
              }
              if (channel === 'dna') {
                // Mitotic arrest/condensation: 1.0 → 1.5 at saturation
                return 1.0 + (fractionalEffect * 0.5);
              }
              if (channel === 'agp') {
                // Golgi collapse: 1.0 → 0.5 at saturation
                return 1.0 - (fractionalEffect * 0.5);
              }
              if (channel === 'er') {
                // ER rearrangement: 1.0 → 0.8 at saturation
                return 1.0 - (fractionalEffect * 0.2);
              }
              if (channel === 'rna') {
                // Minor effect: 1.0 → 0.9 at saturation
                return 1.0 - (fractionalEffect * 0.1);
              }
            }

            // Thapsigargin (ER Stress) - cols 17-24
            if (anchor.anchor_id === 'ER_STRESS') {
              // Sigmoidal dose-response with EC50 ~ 0.03 µM (very potent)
              const ec50 = 0.03;
              const hillSlope = 2.5;
              const fractionalEffect = Math.pow(dose / ec50, hillSlope) / (1 + Math.pow(dose / ec50, hillSlope));

              // Channel-specific effects (severe ER stress and apoptosis)
              if (channel === 'er') {
                // ER collapse: 1.0 → 0.2 at saturation
                return 1.0 - (fractionalEffect * 0.8);
              }
              if (channel === 'mito') {
                // Mitochondrial dysfunction/apoptosis: 1.0 → 0.3 at saturation
                return 1.0 - (fractionalEffect * 0.7);
              }
              if (channel === 'dna') {
                // DNA fragmentation/condensation: 1.0 → 0.5 at high doses
                return 1.0 - (fractionalEffect * 0.5);
              }
              if (channel === 'agp') {
                // Golgi/membrane disruption: 1.0 → 0.6 at saturation
                return 1.0 - (fractionalEffect * 0.4);
              }
              if (channel === 'rna') {
                // RNA degradation: 1.0 → 0.7 at saturation
                return 1.0 - (fractionalEffect * 0.3);
              }
            }
          }
        }

        // Vehicle wells (dose = 0)
        return 1.0;
      }

      // LH plate: ladder effects
      if (plateData.schema_version === 'liquid_handler_calibration_plate_v1') {
        const col = parseInt(wellId.slice(1));
        // Early ladder (cols 7-12)
        if (col >= 7 && col <= 12) {
          const dose = [0.003, 0.006, 0.012, 0.024, 0.049, 0.098][col - 7];
          const effect = 1.0 - dose * 0.5; // Dose-dependent reduction
          if (channel === 'mito') return effect * 0.8;
          if (channel === 'dna') return 1.0 + (1.0 - effect) * 0.3;
          return effect;
        }
        // Late ladder (cols 19-24)
        if (col >= 19 && col <= 24) {
          const dose = [0.195, 0.391, 0.781, 1.56, 3.12, 6.25][col - 19];
          const effect = 1.0 - Math.min(dose * 0.15, 0.8);
          if (channel === 'mito') return effect * 0.6;
          if (channel === 'dna') return 1.0 + (1.0 - effect) * 0.5;
          return effect;
        }
      }

      return 1.0; // Vehicle/default
    };

    const getCellLine = (wellId: string): string => {
      const row = wellId[0];
      if (plateData.plate?.plate_id === 'CAL_EL406_WASH_DAMAGE_v1') {
        // Wash damage uses single cell line (A549)
        return plateData.cell_lines?.row_to_cell_line?.[row] || 'A549';
      } else if (plateData.plate?.plate_id === 'CAL_VARIANCE_PARTITION_v1') {
        // Variance partition uses row_to_cell_line
        return plateData.cell_lines?.row_to_cell_line?.[row] || 'Unknown';
      } else if (plateData.plate?.plate_id === 'CAL_DYNAMIC_RANGE_v1') {
        // Dynamic range uses interleaved rows via row_to_cell_line
        return plateData.cell_lines?.row_to_cell_line?.[row] || 'Unknown';
      } else if (plateData.schema_version === 'calibration_plate_v1') {
        return plateData.cell_lines?.A?.rows?.includes(row) ? 'HepG2' : 'A549';
      } else if (plateData.schema_version === 'calibration_plate_v2' ||
                 plateData.schema_version === 'liquid_handler_calibration_plate_v1') {
        return plateData.cell_lines?.row_to_cell_line?.[row] || 'Unknown';
      }
      return 'N/A';
    };

    const getTreatmentName = (wellId: string): string => {
      if (plateData.plate?.plate_id === 'CAL_EL406_WASH_DAMAGE_v1') {
        // Check no-cells wells
        if (plateData.design?.no_cells_background?.wells?.includes(wellId)) {
          return 'No Cells (Background)';
        }

        // Determine wash program by column
        const col = parseInt(wellId.slice(1));
        if (col >= 1 && col <= 6) return 'Gentle Wash';
        if (col >= 7 && col <= 12) return 'Standard Wash';
        if (col >= 13 && col <= 18) return 'Harsh Wash (Low Height)';
        if (col >= 19 && col <= 24) return 'Harsh Wash (More Cycles)';

        return 'Vehicle';
      }
      if (plateData.plate?.plate_id === 'CAL_VARIANCE_PARTITION_v1') {
        // Check replicate tiles
        for (const tile of plateData.design?.replicate_tiles || []) {
          if (tile.wells.includes(wellId)) {
            if (tile.assignment.treatment === 'VEHICLE_TILE') return 'Vehicle Tile';
            if (tile.assignment.treatment === 'ANCHOR_TILE') return 'Anchor Tile (Nocodazole)';
          }
        }

        // Check distributed replicates
        for (const set of plateData.design?.distributed_replicates?.sets || []) {
          if (set.wells.includes(wellId)) {
            if (set.assignment.treatment === 'VEHICLE_SCATTER') return 'Vehicle Scatter';
            if (set.assignment.treatment === 'ANCHOR_SCATTER') return 'Anchor Scatter (Nocodazole)';
          }
        }

        return 'Vehicle';
      }
      if (plateData.plate?.plate_id === 'CAL_DYNAMIC_RANGE_v1') {
        const col = parseInt(wellId.slice(1));

        // Find anchor and dose for this column
        for (const anchor of plateData.anchors || []) {
          const dose = anchor.dose_uM_by_column?.[col.toString()];
          if (dose !== undefined) {
            if (dose === 0) return 'Vehicle';
            return `${anchor.reagent} ${dose}µM`;
          }
        }

        return 'Vehicle';
      }
      if (plateData.schema_version === 'calibration_plate_v1') {
        if (plateData.anchors?.MILD?.wells?.includes(wellId)) return 'Anchor Mild';
        if (plateData.anchors?.STRONG?.wells?.includes(wellId)) return 'Anchor Strong';
        if (plateData.tiles?.wells?.includes(wellId)) return 'Tile (QC)';
        return 'Vehicle';
      }
      if (plateData.schema_version === 'calibration_plate_v2') {
        if (plateData.biological_anchors?.wells?.ANCHOR_MORPH?.includes(wellId)) return 'Nocodazole';
        if (plateData.biological_anchors?.wells?.ANCHOR_DEATH?.includes(wellId)) return 'Thapsigargin';
        return 'Vehicle';
      }
      if (plateData.schema_version === 'liquid_handler_calibration_plate_v1') {
        const col = parseInt(wellId.slice(1));
        if (col >= 7 && col <= 12) return 'Ladder (early)';
        if (col >= 19 && col <= 24) return 'Ladder (late)';
        if (col === 1 || col === 2) return 'Carryover test';
        return 'Vehicle';
      }
      return 'Unknown';
    };

    // Generate measurements for each well
    rows.forEach((row: string) => {
      cols.forEach((col: number) => {
        const wellId = `${row}${col}`;
        const edgeFactor = getEdgeFactor(row, col);
        const gradientFactor = getColumnGradient(col);

        // Base values with some cell-line-specific differences
        const cellLine = getCellLine(wellId);
        const cellLineBoost = cellLine === 'HepG2' ? 1.1 : 0.95;

        // Base channel values (arbitrary units)
        const baseValues = {
          dna: 125 * cellLineBoost,
          er: 100 * cellLineBoost,
          agp: 140 * cellLineBoost,
          mito: 110 * cellLineBoost,
          rna: 90 * cellLineBoost,
        };

        // Apply spatial and treatment effects
        const channels: any = {};
        Object.entries(baseValues).forEach(([channel, baseValue]) => {
          const treatmentFactor = getTreatmentEffect(wellId, channel);
          const noise = 0.90 + Math.random() * 0.20; // ±10% noise

          // Inject outliers (2% of wells)
          const isOutlier = Math.random() < 0.02;
          const outlierFactor = isOutlier ? (Math.random() < 0.5 ? 0.3 : 1.7) : 1.0;

          channels[channel] = baseValue * edgeFactor * gradientFactor * treatmentFactor * noise * outlierFactor;
        });

        measurements.push({
          wellId,
          row,
          col,
          channels,
          metadata: {
            cellLine,
            treatment: getTreatmentName(wellId),
            dose: 0, // Could extract from plate design if needed
          }
        });
      });
    });

    console.log(`Generated ${measurements.length} mock measurements`);

    // Navigate to results page
    navigate(`/calibration-results/${plateData.plate.plate_id}`, {
      state: {
        plateData,
        measurements
      }
    });
  };

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
              <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'
                }`}>
                Calibration Plate Designs
              </h1>
              <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                }`}>
                Learn the measurement rules before exploring biology
              </p>
            </div>

            <div className="flex items-center gap-4">
              {/* Design Selector */}
              <div className="min-w-[300px]">
                <select
                  value={selectedDesign}
                  onChange={(e) => setSelectedDesign(e.target.value)}
                  className={`w-full px-4 py-2 rounded-lg border-2 transition-all ${isDarkMode
                    ? 'bg-slate-700 border-slate-600 text-white hover:border-indigo-500'
                    : 'bg-white border-zinc-300 text-zinc-900 hover:border-indigo-500'
                    }`}
                >
                  {AVAILABLE_DESIGNS.map(design => (
                    <option key={design.id} value={design.id}>
                      {design.name} - {design.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dark Mode Toggle */}
              <button
                onClick={() => setIsDarkMode(!isDarkMode)}
                className={`p-2 rounded-lg transition-all ${isDarkMode
                  ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                  : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                  }`}
                title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-6 max-w-6xl">
        <CalibrationPlateViewer
          isDarkMode={isDarkMode}
          designVersion={selectedDesign}
          onSimulate={handleSimulate}
        />
      </div>
    </div>
  );
}
