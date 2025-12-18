/**
 * Design Catalog Tab - Browse experimental design versions
 *
 * Displays the design catalog with:
 * - All design versions with status (current/archived)
 * - Evolution history with evidence
 * - Design principles and guidelines
 * - Ability to view full design details
 */

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import DesignPlatePreview from './DesignPlatePreview';
import DesignInvariantBadge from './DesignInvariantBadge';
import { AVAILABLE_CELL_LINES, AVAILABLE_COMPOUNDS } from '../constants/designMetadata';
import { getAvailableWellCount } from '../utils/wellPositions';
import { parseNumberList, parseIntList, parseStringList } from '../utils/inputParsing';
import { parseDesignParams, designParamsEqual, PHASE0_V2_PARAMS } from '../utils/designComparison';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { API_ENDPOINTS } from '../../../config/api';
import { PRESET_IDS, PRESET_REGISTRY, type PresetId } from '../constants/presets';
import { checkPhase0V2Design } from '../invariants/index';

interface Design {
  design_id: string;
  version: string;
  filename: string;
  created_at: string;
  status: string;
  design_type: string;
  description: string;
  metadata: Record<string, any>;
  features: string[];
  improvements_over_previous?: string[];
  supersedes?: string;
  superseded_by?: string;
  chart_definitions?: any[];
  validation_targets?: Record<string, any>;
  next_iteration_ideas?: string[];
  notes?: string;
  buffer_well_rationale?: {
    summary: string;
    positions: string[];
    purpose: string;
    technical_necessity: string[];
    epistemic_function: string;
    phase_dependency: string;
    information_economics: string;
    design_principle: string;
  };
  cell_line_separation_rationale?: {
    summary: string;
    plate_allocation: Record<string, string>;
    why_separation: string[];
    when_mixing_makes_sense: string;
    phase0_recommendation: string;
    design_principle: string;
  };
}

interface FullDesignData {
  catalog_entry: Design;
  design_data: {
    design_id: string;
    design_type: string;
    description: string;
    metadata: Record<string, any>;
    wells: any[];
  };
}

interface EvolutionEntry {
  from_version: string | null;
  to_version: string;
  date: string;
  reason: string;
  key_changes: string[];
  evidence?: Record<string, any>;
}

interface Catalog {
  catalog_version: string;
  description: string;
  designs: Design[];
  design_evolution_log: EvolutionEntry[];
  design_principles: Record<string, string>;
  glossary: Record<string, string>;
}

// Tooltip Component
const Tooltip: React.FC<{ text: string; children: React.ReactNode }> = ({ text, children }) => {
  const [show, setShow] = useState(false);

  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="cursor-help"
      >
        {children}
      </div>
      {show && (
        <div className="absolute z-50 w-64 p-3 bg-slate-900 border border-slate-600 rounded-lg shadow-xl text-xs text-slate-300 bottom-full left-1/2 transform -translate-x-1/2 mb-2">
          <div className="absolute w-3 h-3 bg-slate-900 border-r border-b border-slate-600 transform rotate-45 -bottom-1.5 left-1/2 -translate-x-1/2"></div>
          {text}
        </div>
      )}
    </div>
  );
};

// Design Generator Form Component
const DesignGeneratorForm: React.FC = () => {
  // Form state
  const [designId, setDesignId] = useState('');
  const [description, setDescription] = useState('');

  // Cell lines & compounds
  const [selectedCellLines, setSelectedCellLines] = useState<string[]>([]);
  const [selectedCompounds, setSelectedCompounds] = useState<string[]>([]);

  // Dose configuration
  const [doseMultipliers, setDoseMultipliers] = useState('');
  const [replicatesPerDose, setReplicatesPerDose] = useState(2);

  // Batch structure
  const [days, setDays] = useState('');
  const [operators, setOperators] = useState('');
  const [timepoints, setTimepoints] = useState('');

  // Sentinels
  const [sentinelDMSO, setSentinelDMSO] = useState(0);
  const [sentinelTBHQ, setSentinelTBHQ] = useState(0);
  const [sentinelThapsigargin, setSentinelThapsigargin] = useState(0);
  const [sentinelOligomycin, setSentinelOligomycin] = useState(0);
  const [sentinelMG132, setSentinelMG132] = useState(0);

  // Plate layout
  const [plateFormat, setPlateFormat] = useState<96 | 384>(96);
  const [checkerboard, setCheckerboard] = useState(false);
  const [excludeCorners, setExcludeCorners] = useState(false);
  const [excludeMidRowWells, setExcludeMidRowWells] = useState(false);
  const [excludeEdges, setExcludeEdges] = useState(false);

  // Preset tracking - explicit rather than fuzzy matching
  // Initialize to null - preset ID is only set when explicitly applying a preset
  const [activePresetId, setActivePresetId] = useState<PresetId | null>(null);

  // Ref to prevent drift detection from clearing preset during application
  const isApplyingPresetRef = useRef(false);

  // Load actual phase0_v2 design for exact preview
  const [phase0V2Design, setPhase0V2Design] = useState<any>(null);

  // UI state
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const availableCellLines = AVAILABLE_CELL_LINES;
  const availableCompounds = AVAILABLE_COMPOUNDS;

  // Apply a preset - sets both form state and preset ID atomically
  const applyPreset = useCallback((presetId: PresetId) => {
    const preset = PRESET_REGISTRY[presetId];
    if (!preset) {
      console.error(`Unknown preset: ${presetId}`);
      return;
    }

    // Set flag to prevent drift detection from clearing preset during application
    isApplyingPresetRef.current = true;

    // Apply all form state atomically
    setSelectedCellLines(preset.selectedCellLines);
    setSelectedCompounds(preset.selectedCompounds);
    setDoseMultipliers(preset.doseMultipliers);
    setReplicatesPerDose(preset.replicatesPerDose);
    setDays(preset.days);
    setOperators(preset.operators);
    setTimepoints(preset.timepoints);
    setSentinelDMSO(preset.sentinelDMSO);
    setSentinelTBHQ(preset.sentinelTBHQ);
    setSentinelThapsigargin(preset.sentinelThapsigargin);
    setSentinelOligomycin(preset.sentinelOligomycin);
    setSentinelMG132(preset.sentinelMG132);
    setPlateFormat(preset.plateFormat);
    setCheckerboard(preset.checkerboard);
    setExcludeCorners(preset.excludeCorners);
    setExcludeMidRowWells(preset.excludeMidRowWells);
    setExcludeEdges(preset.excludeEdges);

    // Set preset ID
    setActivePresetId(presetId);

    // Clear flag after next tick to allow drift detection to resume
    setTimeout(() => {
      isApplyingPresetRef.current = false;
    }, 0);
  }, []);

  // Helper to clear preset when user modifies anything
  // Idempotent - only updates if not already null (prevents unnecessary renders)
  const clearPreset = useCallback(() => {
    setActivePresetId(prev => (prev === null ? prev : null));
  }, []);

  // Initialize with phase0_v2 preset on mount
  useEffect(() => {
    applyPreset(PRESET_IDS.PHASE0_V2);

    // Also fetch the actual phase0_v2 design for exact preview
    const ac = new AbortController();
    fetch(API_ENDPOINTS.catalogDesign(PRESET_IDS.PHASE0_V2), { signal: ac.signal })
      .then(res => res.json())
      .then(data => {
        setPhase0V2Design(data.design_data);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          console.error('Failed to load phase0_v2 design:', err);
        }
      });
    return () => ac.abort();
  }, [applyPreset]);

  const toggleCellLine = (cellLine: string) => {
    clearPreset();
    setSelectedCellLines(prev =>
      prev.includes(cellLine)
        ? prev.filter(c => c !== cellLine)
        : [...prev, cellLine]
    );
  };

  const toggleCompound = (compound: string) => {
    clearPreset();
    setSelectedCompounds(prev =>
      prev.includes(compound)
        ? prev.filter(c => c !== compound)
        : [...prev, compound]
    );
  };

  const selectAllCompounds = () => {
    clearPreset();
    setSelectedCompounds(availableCompounds);
  };

  const clearCompounds = () => {
    clearPreset();
    setSelectedCompounds([]);
  };

  // Debounce text inputs to avoid recomputation on every keystroke
  // Wrap with preset clearing
  const debouncedDoseMultipliers = useDebouncedValue(doseMultipliers, 300);
  const debouncedDays = useDebouncedValue(days, 300);
  const debouncedOperators = useDebouncedValue(operators, 300);
  const debouncedTimepoints = useDebouncedValue(timepoints, 300);

  // Clear preset when debounced text values change (user finished typing)
  // Only runs when not currently applying a preset (prevents self-clearing race)
  useEffect(() => {
    // Don't clear if no preset is active
    if (activePresetId === null) return;

    // Don't clear if we're currently applying a preset (prevents race condition)
    if (isApplyingPresetRef.current) return;

    // Check if current params still match the active preset
    const currentParams = parseDesignParams({
      selectedCellLines,
      selectedCompounds,
      doseMultipliers: debouncedDoseMultipliers,
      replicatesPerDose,
      days: debouncedDays,
      operators: debouncedOperators,
      timepoints: debouncedTimepoints,
      sentinelDMSO,
      sentinelTBHQ,
      sentinelThapsigargin,
      sentinelOligomycin,
      sentinelMG132,
      plateFormat,
      checkerboard,
      excludeCorners,
      excludeMidRowWells,
      excludeEdges,
    });

    // If params have drifted from v2 defaults, clear the preset
    if (!designParamsEqual(currentParams, PHASE0_V2_PARAMS)) {
      setActivePresetId(null);
    }
  }, [
    activePresetId,
    selectedCellLines,
    selectedCompounds,
    debouncedDoseMultipliers,
    replicatesPerDose,
    debouncedDays,
    debouncedOperators,
    debouncedTimepoints,
    sentinelDMSO,
    sentinelTBHQ,
    sentinelThapsigargin,
    sentinelOligomycin,
    sentinelMG132,
    plateFormat,
    checkerboard,
    excludeCorners,
    excludeMidRowWells,
    excludeEdges,
  ]);

  // V2 detection: explicit preset ID, not fuzzy matching
  const matchesV2Defaults = activePresetId === PRESET_IDS.PHASE0_V2;

  // Calculate well statistics in real-time
  const calculateWellStats = () => {
    // If showing actual phase0_v2 design, use its real stats from metadata
    if (matchesV2Defaults && phase0V2Design && phase0V2Design.metadata) {
      const meta = phase0V2Design.metadata;
      const totalWells = meta.wells_per_plate * meta.n_plates; // 88 × 24 = 2,112
      const sentinelsPerPlate = 28; // DMSO(8) + tBHQ(5) + thasp(5) + oligo(5) + MG132(5)
      const totalSentinels = sentinelsPerPlate * meta.n_plates; // 28 × 24 = 672
      const totalExperimental = totalWells - totalSentinels; // 2,112 - 672 = 1,440

      return {
        experimentalWells: totalExperimental,
        sentinelWells: totalSentinels,
        totalWells: totalWells,
        nPlates: meta.n_plates,
        wellsPerPlate: meta.wells_per_plate,
        availableWells: 96,
        fits: true, // v2 design already exists and works
      };
    }

    try {
      const parsedDoses = parseNumberList(debouncedDoseMultipliers);
      const nCompounds = selectedCompounds.length;
      const nDoses = parsedDoses.length;
      const parsedDays = parseIntList(debouncedDays);
      const parsedOperators = parseStringList(debouncedOperators);
      const parsedTimepoints = parseNumberList(debouncedTimepoints);

      // Experimental wells per cell line per INDIVIDUAL PLATE
      const experimentalWellsPerCell = nCompounds * nDoses * replicatesPerDose;

      // Sentinel wells per cell line per INDIVIDUAL PLATE
      const sentinelWellsPerCell = sentinelDMSO + sentinelTBHQ + sentinelThapsigargin + sentinelOligomycin + sentinelMG132;

      // Total wells on ONE INDIVIDUAL PLATE (one day, one operator, one timepoint)
      const wellsPerIndividualPlate = experimentalWellsPerCell + sentinelWellsPerCell;

      // Available wells based on exclusions (single source of truth)
      const availableWells = getAvailableWellCount(plateFormat, {
        excludeCorners,
        excludeMidRowWells,
        excludeEdges,
      });

      if (checkerboard) {
        // Both cell lines on same plate
        const wellsPerPlate = wellsPerIndividualPlate * selectedCellLines.length;
        const nPlates = parsedDays.length * parsedOperators.length * parsedTimepoints.length;
        const totalWells = wellsPerPlate * nPlates;

        return {
          experimentalWells: experimentalWellsPerCell * selectedCellLines.length * nPlates,
          sentinelWells: sentinelWellsPerCell * selectedCellLines.length * nPlates,
          totalWells,
          nPlates,
          wellsPerPlate,
          availableWells,
          fits: wellsPerPlate <= availableWells,
        };
      } else {
        // Separate plates per cell line - each (day × operator × timepoint × cell_line) gets ONE plate
        const nPlates = parsedDays.length * parsedOperators.length * parsedTimepoints.length * selectedCellLines.length;
        const totalWells = wellsPerIndividualPlate * nPlates;

        return {
          experimentalWells: experimentalWellsPerCell * nPlates,
          sentinelWells: sentinelWellsPerCell * nPlates,
          totalWells,
          nPlates,
          wellsPerPlate: wellsPerIndividualPlate,
          availableWells,
          fits: wellsPerIndividualPlate <= availableWells,
        };
      }
    } catch (err) {
      return null;
    }
  };

  const wellStats = useMemo(() => calculateWellStats(), [
    matchesV2Defaults,
    phase0V2Design,
    debouncedDoseMultipliers,
    replicatesPerDose,
    debouncedDays,
    debouncedOperators,
    debouncedTimepoints,
    selectedCompounds.length,
    selectedCellLines.length,
    sentinelDMSO,
    sentinelTBHQ,
    sentinelThapsigargin,
    sentinelOligomycin,
    sentinelMG132,
    plateFormat,
    checkerboard,
    excludeCorners,
    excludeMidRowWells,
    excludeEdges,
  ]);

  // Generate preview wells based on current form state - ALL PLATES
  // This matches the EXACT algorithm from scripts/design_catalog.py DesignGenerator.create_design()
  const generatePreviewWells = () => {
    if (!wellStats || selectedCompounds.length === 0) return {};

    // CRITICAL: Don't generate misleading previews for designs that don't fit
    // User must fix the design parameters first
    if (!wellStats.fits && !matchesV2Defaults) {
      return {};
    }

    if (matchesV2Defaults && phase0V2Design && phase0V2Design.wells) {
      // Return EXACT phase0_v2 design from file (with spatial sentinel stratification)
      const plateWellsMap: Record<string, any[]> = {};
      for (const well of phase0V2Design.wells) {
        if (!plateWellsMap[well.plate_id]) {
          plateWellsMap[well.plate_id] = [];
        }
        plateWellsMap[well.plate_id].push(well);
      }
      return plateWellsMap;
    }

    // Otherwise generate algorithmically with sentinel interspersion

    const parsedDoses = parseNumberList(debouncedDoseMultipliers);
    const parsedDays = parseIntList(debouncedDays);
    const parsedOperators = parseStringList(debouncedOperators);
    const parsedTimepoints = parseNumberList(debouncedTimepoints);
    const compounds = selectedCompounds;

    // Compound IC50 values (matches Python compound_ic50 dict)
    const compoundIC50: Record<string, number> = {
      'tBHQ': 30.0, 'H2O2': 100.0, 'tunicamycin': 1.0, 'thapsigargin': 0.5,
      'CCCP': 5.0, 'oligomycin': 1.0, 'etoposide': 10.0, 'MG132': 1.0,
      'nocodazole': 0.5, 'paclitaxel': 0.01
    };

    // Calculate plate geometry
    const nRows = plateFormat === 96 ? 8 : 16;
    const nCols = plateFormat === 96 ? 12 : 24;
    const rowLabels = Array.from({ length: nRows }, (_, i) => String.fromCharCode(65 + i));

    // Generate excluded wells
    const excludedWells = new Set<string>();
    if (excludeCorners) {
      excludedWells.add(`${rowLabels[0]}${String(1).padStart(2, '0')}`);  // Top-left
      excludedWells.add(`${rowLabels[0]}${String(nCols).padStart(2, '0')}`);  // Top-right
      excludedWells.add(`${rowLabels[nRows-1]}${String(1).padStart(2, '0')}`);  // Bottom-left
      excludedWells.add(`${rowLabels[nRows-1]}${String(nCols).padStart(2, '0')}`);  // Bottom-right
    }
    if (excludeMidRowWells && plateFormat === 96) {
      // Exclude A6, A7, H6, H7 for 96-well plates (phase0_v2 pattern)
      excludedWells.add(`${rowLabels[0]}${String(6).padStart(2, '0')}`);  // A6
      excludedWells.add(`${rowLabels[0]}${String(7).padStart(2, '0')}`);  // A7
      excludedWells.add(`${rowLabels[nRows-1]}${String(6).padStart(2, '0')}`);  // H6
      excludedWells.add(`${rowLabels[nRows-1]}${String(7).padStart(2, '0')}`);  // H7
    }
    if (excludeEdges) {
      // All wells in first/last row
      for (const row of [rowLabels[0], rowLabels[nRows-1]]) {
        for (let col = 1; col <= nCols; col++) {
          excludedWells.add(`${row}${String(col).padStart(2, '0')}`);
        }
      }
      // All wells in first/last column
      for (const col of [1, nCols]) {
        for (const row of rowLabels) {
          excludedWells.add(`${row}${String(col).padStart(2, '0')}`);
        }
      }
    }

    // Generate all well positions
    const allWells: string[] = [];
    for (const row of rowLabels) {
      for (let col = 1; col <= nCols; col++) {
        allWells.push(`${row}${String(col).padStart(2, '0')}`);
      }
    }

    // Filter out excluded wells
    const availableWells = allWells.filter(w => !excludedWells.has(w));

    // Sentinel configuration (matches phase0_v2)
    const sentinelConfig = {
      'DMSO': { dose_uM: 0.0, n_per_cell: sentinelDMSO },
      'tBHQ': { dose_uM: 30.0, n_per_cell: sentinelTBHQ },
      'thapsigargin': { dose_uM: 0.5, n_per_cell: sentinelThapsigargin },
      'oligomycin': { dose_uM: 1.0, n_per_cell: sentinelOligomycin },
      'MG132': { dose_uM: 1.0, n_per_cell: sentinelMG132 },
    };

    const plateWellsMap: Record<string, any[]> = {};

    // Generate wells - matches Python loop structure exactly
    for (const day of parsedDays) {
      for (const operator of parsedOperators) {
        for (const timepoint of parsedTimepoints) {
          if (checkerboard) {
            // Checkerboard: single plate with interleaved cell lines and interspersed sentinels
            const plateId = `Day${day}_${operator}_T${timepoint}h`;
            plateWellsMap[plateId] = [];

            // Generate experimental wells
            const experimentalWells = [];
            for (const compound of compounds) {
              const ic50 = compoundIC50[compound] || 1.0;
              for (const doseMult of parsedDoses) {
                const doseUM = doseMult * ic50;
                for (let rep = 0; rep < replicatesPerDose; rep++) {
                  for (const cellLine of selectedCellLines) {
                    experimentalWells.push({
                      cell_line: cellLine,
                      compound: compound,
                      dose_uM: doseUM,
                      is_sentinel: false,
                    });
                  }
                }
              }
            }

            // Generate sentinel wells
            const sentinelWells = [];
            for (const [sentinelCompound, config] of Object.entries(sentinelConfig)) {
              for (let i = 0; i < config.n_per_cell; i++) {
                for (const cellLine of selectedCellLines) {
                  sentinelWells.push({
                    cell_line: cellLine,
                    compound: sentinelCompound,
                    dose_uM: config.dose_uM,
                    is_sentinel: true,
                    sentinel_type: sentinelCompound.toLowerCase(),
                  });
                }
              }
            }

            // Intersperse sentinels among experimental wells
            // Use a more robust algorithm that handles all ratios correctly
            const allWells = [];
            const totalWells = experimentalWells.length + sentinelWells.length;

            if (sentinelWells.length === 0) {
              // No sentinels, just add all experimental
              allWells.push(...experimentalWells);
            } else if (experimentalWells.length === 0) {
              // No experimental, just add all sentinels
              allWells.push(...sentinelWells);
            } else {
              // Interleave based on density - add experimental or sentinel based on which is "due"
              let expIdx = 0;
              let sentIdx = 0;

              for (let i = 0; i < totalWells; i++) {
                // Calculate what proportion we've added so far
                const expProportion = expIdx / experimentalWells.length;
                const sentProportion = sentIdx / sentinelWells.length;

                // Add whichever type is "behind" its target proportion
                if (expIdx < experimentalWells.length &&
                    (sentIdx >= sentinelWells.length || expProportion <= sentProportion)) {
                  allWells.push(experimentalWells[expIdx++]);
                } else if (sentIdx < sentinelWells.length) {
                  allWells.push(sentinelWells[sentIdx++]);
                }
              }
            }

            // Assign well positions
            for (let i = 0; i < Math.min(allWells.length, availableWells.length); i++) {
              plateWellsMap[plateId].push({
                ...allWells[i],
                plate_id: plateId,
                well_pos: availableWells[i],
              });
            }
          } else {
            // Separate plate per cell line with interspersed sentinels
            for (const cellLine of selectedCellLines) {
              const plateId = `${cellLine}_Day${day}_${operator}_T${timepoint}h`;
              plateWellsMap[plateId] = [];

              // Generate experimental wells
              const experimentalWells = [];
              for (const compound of compounds) {
                const ic50 = compoundIC50[compound] || 1.0;
                for (const doseMult of parsedDoses) {
                  const doseUM = doseMult * ic50;
                  for (let rep = 0; rep < replicatesPerDose; rep++) {
                    experimentalWells.push({
                      cell_line: cellLine,
                      compound: compound,
                      dose_uM: doseUM,
                      is_sentinel: false,
                    });
                  }
                }
              }

              // Generate sentinel wells
              const sentinelWells = [];
              for (const [sentinelCompound, config] of Object.entries(sentinelConfig)) {
                for (let i = 0; i < config.n_per_cell; i++) {
                  sentinelWells.push({
                    cell_line: cellLine,
                    compound: sentinelCompound,
                    dose_uM: config.dose_uM,
                    is_sentinel: true,
                    sentinel_type: sentinelCompound.toLowerCase(),
                  });
                }
              }

              // Intersperse sentinels among experimental wells
              // Use a more robust algorithm that handles all ratios correctly
              const allWells = [];
              const totalWells = experimentalWells.length + sentinelWells.length;

              if (sentinelWells.length === 0) {
                // No sentinels, just add all experimental
                allWells.push(...experimentalWells);
              } else if (experimentalWells.length === 0) {
                // No experimental, just add all sentinels
                allWells.push(...sentinelWells);
              } else {
                // Interleave based on density - add experimental or sentinel based on which is "due"
                let expIdx = 0;
                let sentIdx = 0;

                for (let i = 0; i < totalWells; i++) {
                  // Calculate what proportion we've added so far
                  const expProportion = expIdx / experimentalWells.length;
                  const sentProportion = sentIdx / sentinelWells.length;

                  // Add whichever type is "behind" its target proportion
                  if (expIdx < experimentalWells.length &&
                      (sentIdx >= sentinelWells.length || expProportion <= sentProportion)) {
                    allWells.push(experimentalWells[expIdx++]);
                  } else if (sentIdx < sentinelWells.length) {
                    allWells.push(sentinelWells[sentIdx++]);
                  }
                }
              }

              // Assign well positions
              for (let i = 0; i < Math.min(allWells.length, availableWells.length); i++) {
                plateWellsMap[plateId].push({
                  ...allWells[i],
                  plate_id: plateId,
                  well_pos: availableWells[i],
                });
              }
            }
          }
        }
      }
    }

    // Dev-mode invariant: check for duplicate plate IDs
    if (import.meta.env.DEV) {
      const plateIds = Object.keys(plateWellsMap);
      const dupes = plateIds.filter((id, i) => plateIds.indexOf(id) !== i);
      if (dupes.length > 0) {
        console.warn('Duplicate plate IDs detected:', dupes);
      }
    }

    return plateWellsMap;
  };

  const previewWells = useMemo(() => generatePreviewWells(), [
    wellStats,
    matchesV2Defaults,
    phase0V2Design,
    selectedCompounds,
    debouncedDoseMultipliers,
    replicatesPerDose,
    debouncedDays,
    debouncedOperators,
    debouncedTimepoints,
    selectedCellLines,
    sentinelDMSO,
    sentinelTBHQ,
    sentinelThapsigargin,
    sentinelOligomycin,
    sentinelMG132,
    plateFormat,
    checkerboard,
    excludeCorners,
    excludeMidRowWells,
    excludeEdges,
  ]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      // Parse comma-separated values with proper filtering
      const parsedDoses = parseNumberList(doseMultipliers);
      const parsedDays = parseIntList(days);
      const parsedOperators = parseStringList(operators);
      const parsedTimepoints = parseNumberList(timepoints);

      // Validate inputs
      if (parsedDoses.length === 0) {
        throw new Error('At least one valid dose is required');
      }
      if (parsedDays.length === 0) {
        throw new Error('At least one valid day is required');
      }
      if (parsedOperators.length === 0) {
        throw new Error('At least one valid operator is required');
      }
      if (parsedTimepoints.length === 0) {
        throw new Error('At least one valid timepoint is required');
      }
      if (selectedCellLines.length === 0) {
        throw new Error('At least one cell line must be selected');
      }

      const payload = {
        design_id: designId,
        description: description,
        cell_lines: selectedCellLines,
        compounds: selectedCompounds.length > 0 ? selectedCompounds : undefined,
        dose_multipliers: parsedDoses,
        replicates_per_dose: replicatesPerDose,
        days: parsedDays,
        operators: parsedOperators,
        timepoints_h: parsedTimepoints,
        sentinel_config: {
          DMSO: { dose_uM: 0.0, n_per_cell: sentinelDMSO },
          tBHQ: { dose_uM: 30.0, n_per_cell: sentinelTBHQ },
          thapsigargin: { dose_uM: 0.5, n_per_cell: sentinelThapsigargin },
          oligomycin: { dose_uM: 1.0, n_per_cell: sentinelOligomycin },
          MG132: { dose_uM: 1.0, n_per_cell: sentinelMG132 },
        },
        plate_format: plateFormat,
        checkerboard: checkerboard,
        exclude_corners: excludeCorners,
        exclude_mid_row_wells: excludeMidRowWells,
        exclude_edges: excludeEdges,
      };

      const response = await fetch(API_ENDPOINTS.generateDesign, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate design');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setGenerating(false);
    }
  };

  const exportForLLMReview = () => {
    console.log('exportForLLMReview called');

    // Parse current form values
    const parsedDoses = parseNumberList(doseMultipliers);
    const parsedDays = parseIntList(days);
    const parsedOperators = parseStringList(operators);
    const parsedTimepoints = parseNumberList(timepoints);

    // Build the export package
    const exportData = {
      _meta: {
        export_type: 'design_for_llm_review',
        version: '1.0.0',
        purpose: 'Complete design snapshot for LLM feedback (ChatGPT, Claude, etc.)',
        timestamp: new Date().toISOString(),
      },

      // 1. DESIGN SPACE: What's available
      design_space: {
        cell_lines: {
          available: availableCellLines.map(cl => ({
            value: cl,
            selected: selectedCellLines.includes(cl),
          })),
          constraints: ['Cell lines are SEPARATE: no mixing within plate'],
        },
        compounds: {
          available: AVAILABLE_COMPOUNDS.map(c => ({
            value: c,
            selected: selectedCompounds.includes(c),
          })),
          constraints: ['96-well format fits 5 compounds × 6 doses × 2 replicates = 60 experimental + 28 sentinels = 88 wells'],
        },
        doses: {
          current: parsedDoses,
          interpretation: 'dose_uM = multiplier × ic50',
        },
        replicates: {
          current: replicatesPerDose,
          impact: 'More replicates = more wells needed per condition',
        },
        timepoints_h: {
          current: parsedTimepoints,
          impact: 'Each timepoint multiplies plate count',
        },
        days: {
          current: parsedDays,
          role: 'Batch factor (orthogonal)',
        },
        operators: {
          current: parsedOperators,
          role: 'Batch factor (orthogonal)',
        },
        plate_format: {
          current: plateFormat,
          available: [96, 384],
        },
        exclusions: {
          corners: excludeCorners,
          midRow: excludeMidRowWells,
          edges: excludeEdges,
        },
      },

      // 2. CURRENT PARAMETERS: What you chose
      current_parameters: {
        design_id: designId || 'unnamed_design',
        description: description || 'No description',
        cell_lines: selectedCellLines,
        compounds: selectedCompounds.length > 0 ? selectedCompounds : 'all',
        doses: parsedDoses,
        replicates: replicatesPerDose,
        timepoints_h: parsedTimepoints,
        days: parsedDays,
        operators: parsedOperators,
        plate_format: plateFormat,
        exclusions: {
          corners: excludeCorners,
          midRow: excludeMidRowWells,
          edges: excludeEdges,
        },
      },

      // 3. STATISTICS: Calculated metrics
      statistics: wellStats ? {
        total_wells: wellStats.totalWells,
        sentinel_wells: wellStats.sentinelWells,
        experimental_wells: wellStats.experimentalWells,
        plates: wellStats.nPlates,
        wells_per_plate: wellStats.wellsPerPlate,
        available_wells_per_plate: wellStats.availableWells,
        fits: wellStats.fits,
      } : null,

      // 4. DESIGN DATA: Preview wells (if available)
      design_preview: (matchesV2Defaults && phase0V2Design) ? {
        source: 'phase0_founder_v2_regenerated.json',
        wells: phase0V2Design.wells,
        metadata: phase0V2Design.metadata,
      } : {
        source: 'generated_preview',
        wells: Object.values(previewWells).flat(),
        note: 'This is a preview generated from the form. For full design, click Generate Design button.',
      },

      // 5. VALIDATION: Run invariants if we have a design
      validation: (matchesV2Defaults && phase0V2Design) ? (() => {
        try {
          const certificate = checkPhase0V2Design(phase0V2Design.wells, phase0V2Design.metadata);
          return {
            violations: certificate.violations,
            stats: certificate.stats,
            scaffoldMetadata: certificate.scaffoldMetadata,
          };
        } catch (error) {
          console.error('Validation failed:', error);
          return {
            error: 'Validation failed: ' + (error instanceof Error ? error.message : String(error)),
          };
        }
      })() : {
        note: 'Validation only available for generated designs. Click Generate Design to get full validation.',
      },

      // 6. CONTEXT: Goals and constraints
      context: {
        design_goals: [
          'Maximum identifiability (position = identity)',
          'Batch orthogonality (day × operator × timepoint)',
          'Spatial scatter (eliminate gradient confounding)',
          'Position stability (same position = same condition within cell line)',
        ],
        constraints: [
          'Fixed sentinel scaffold (28 sentinels, same positions on all plates)',
          'Exact fill requirement (88 wells per plate, no partials)',
          'Cell line separation (no mixing on same plate)',
          'Identical conditions per timepoint (multiset consistency)',
        ],
        invariants_enforced: [
          'sentinel_scaffold_exact_match',
          'plate_capacity',
          'condition_multiset_identical',
          'experimental_position_stability',
          'spatial_dispersion (bbox area ≥ 40)',
          'sentinel_placement_quality',
          'batch_balance',
        ],
      },

      // 7. PROMPT TEMPLATE: How to use this file
      how_to_use: {
        instructions: [
          '1. Copy this entire JSON file',
          '2. Go to ChatGPT/Claude',
          '3. Paste the JSON',
          '4. Ask: "Review this experimental design. Does it satisfy the stated goals? What would you improve?"',
        ],
        example_questions: [
          'Does this design satisfy the identifiability and spatial scatter goals?',
          'Are there red flags in the statistics or validation?',
          'What would you change to improve the design?',
          'How would adding a 72h timepoint affect plate count?',
          'Should I use per-plate or per-cell-line position shuffling?',
        ],
      },
    };

    console.log('Export data prepared:', exportData);

    // Trigger download
    try {
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `design_for_llm_review_${new Date().toISOString().split('T')[0]}.json`;
      console.log('Download filename:', a.download);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      console.log('Download triggered successfully');
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-900/30 to-emerald-900/30 border border-green-700/30 rounded-lg p-6">
        <h3 className="text-2xl font-bold text-white mb-2">✨ Create New Design</h3>
        <p className="text-slate-300">
          Interactive design generator with full control over all parameters
        </p>
        {matchesV2Defaults && phase0V2Design ? (
          <div className="mt-3 text-xs text-violet-400/80 bg-violet-900/20 rounded p-2">
            <strong>✓ Showing EXACT phase0_v2 design:</strong> Preview displays the actual phase0_founder_v2_controls_stratified layout with custom compound splitting (5 compounds per plate) and spatial sentinel stratification.
          </div>
        ) : (
          <div className="mt-3 text-xs text-green-400/80 bg-green-900/20 rounded p-2">
            <strong>Generator mode:</strong> Form defaults match phase0_v2 parameters but will generate algorithmically. For v2's custom 5-compound splitting, switch to 384-well or reduce compounds.
          </div>
        )}
      </div>

      {/* Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Basic Info */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h4 className="text-lg font-semibold text-white mb-4">Basic Information</h4>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Design ID
                </label>
                <input
                  type="text"
                  value={designId}
                  onChange={(e) => setDesignId(e.target.value)}
                  placeholder="e.g., phase0_custom_neurons_v1"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of this experimental design"
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
            </div>
          </div>

          {/* Cell Lines */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <h4 className="text-lg font-semibold text-white">Cell Lines</h4>
              <Tooltip text="Choose which cell lines to test. A549 (lung cancer) and HepG2 (hepatoma) are standard. iPSC_NGN2 are neurons (post-mitotic, OXPHOS-dependent). iPSC_Microglia are immune cells (oxidative stress resistant).">
                <span className="text-slate-400 text-sm">ⓘ</span>
              </Tooltip>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {availableCellLines.map(cellLine => {
                const tooltips: Record<string, string> = {
                  'A549': 'Lung cancer. NRF2-primed (oxidative resistant), fast cycling (microtubule sensitive)',
                  'HepG2': 'Hepatoma. High ER load, OXPHOS-dependent, H2O2 resistant',
                  'iPSC_NGN2': 'Neurons. Post-mitotic, extreme OXPHOS dependence, transport-critical',
                  'iPSC_Microglia': 'Immune cells. High ROS resistance, phagocytic, pro-inflammatory'
                };
                return (
                  <Tooltip key={cellLine} text={tooltips[cellLine]}>
                    <button
                      onClick={() => toggleCellLine(cellLine)}
                      className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                        selectedCellLines.includes(cellLine)
                          ? 'bg-green-600 text-white border-2 border-green-400'
                          : 'bg-slate-900 text-slate-400 border border-slate-700 hover:border-slate-500'
                      }`}
                    >
                      {cellLine}
                    </button>
                  </Tooltip>
                );
              })}
            </div>
          </div>

          {/* Compounds */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h4 className="text-lg font-semibold text-white">Compounds</h4>
                <Tooltip text="Select compounds to test. Leave empty to include all 10 Phase 0 compounds. Each compound targets a specific stress mechanism with known IC50 values.">
                  <span className="text-slate-400 text-sm">ⓘ</span>
                </Tooltip>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={selectAllCompounds}
                  className="text-xs px-3 py-1 bg-green-700 text-white rounded hover:bg-green-600"
                >
                  Select All
                </button>
                <button
                  onClick={clearCompounds}
                  className="text-xs px-3 py-1 bg-slate-700 text-white rounded hover:bg-slate-600"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {availableCompounds.map(compound => {
                const compoundTooltips: Record<string, string> = {
                  'tBHQ': 'Oxidative stress. NRF2 activator, electrophile (IC50: 30 µM)',
                  'H2O2': 'Oxidative stress. Direct ROS, hydrogen peroxide (IC50: 100 µM)',
                  'tunicamycin': 'ER stress. N-glycosylation inhibitor (IC50: 1 µM)',
                  'thapsigargin': 'ER stress. SERCA pump inhibitor, Ca²⁺ disruption (IC50: 0.5 µM)',
                  'CCCP': 'Mitochondrial stress. Protonophore uncoupler (IC50: 5 µM)',
                  'oligomycin': 'Mitochondrial stress. ATP synthase inhibitor (IC50: 1 µM)',
                  'etoposide': 'DNA damage. Topoisomerase II inhibitor (IC50: 10 µM)',
                  'MG132': 'Proteasome inhibitor. Protein degradation blockade (IC50: 1 µM)',
                  'nocodazole': 'Microtubule poison. Depolymerizer (IC50: 0.5 µM)',
                  'paclitaxel': 'Microtubule poison. Stabilizer (IC50: 0.01 µM)'
                };
                return (
                  <Tooltip key={compound} text={compoundTooltips[compound]}>
                    <button
                      onClick={() => toggleCompound(compound)}
                      className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                        selectedCompounds.includes(compound)
                          ? 'bg-green-600 text-white'
                          : 'bg-slate-900 text-slate-400 border border-slate-700 hover:border-slate-500'
                      }`}
                    >
                      {compound}
                    </button>
                  </Tooltip>
                );
              })}
            </div>
            <p className="text-xs text-slate-400 mt-3">
              {selectedCompounds.length === 10 ? 'All 10 compounds selected' : `${selectedCompounds.length} of 10 compounds selected`}
            </p>
          </div>

          {/* Dose Configuration */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <h4 className="text-lg font-semibold text-white">Dose Configuration</h4>
              <Tooltip text="Configure dose-response curve sampling. Doses are specified as multipliers of each compound's IC50 value for biologically meaningful comparisons.">
                <span className="text-slate-400 text-sm">ⓘ</span>
              </Tooltip>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Dose Multipliers (relative to IC50)
                  </label>
                  <Tooltip text="Doses as fractions of IC50. For tBHQ (IC50=30µM): [0, 0.1, 1.0, 10.0] → [0, 3, 30, 300]µM. Use 0 for vehicle control. More doses = better curve fit but fewer compounds fit.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="text"
                  value={doseMultipliers}
                  onChange={(e) => setDoseMultipliers(e.target.value)}
                  placeholder="0, 0.1, 1.0, 10.0"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm"
                />
                <p className="text-xs text-slate-400 mt-1">
                  Comma-separated. Example: 0 = vehicle, 1.0 = IC50, 10.0 = 10×IC50
                </p>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Replicates Per Dose
                  </label>
                  <Tooltip text="Technical replicates at each dose. More reps = tighter error bars and better EC50 estimates, but fewer compounds/doses fit per plate. 3 replicates is standard for dose-response.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={replicatesPerDose}
                  onChange={(e) => {
                    clearPreset();
                    setReplicatesPerDose(parseInt(e.target.value));
                  }}
                  min={1}
                  max={10}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Batch Structure */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <h4 className="text-lg font-semibold text-white">Batch Structure</h4>
              <Tooltip text="Define biological replicates (days), technical variability (operators), and kinetic sampling (timepoints). Each combination creates a separate plate.">
                <span className="text-slate-400 text-sm">ⓘ</span>
              </Tooltip>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Days
                  </label>
                  <Tooltip text="Experimental days (biological replicates). Each day is an independent run. [1, 2] doubles plate count but captures day-to-day variability.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="text"
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                  placeholder="1, 2"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Operators
                  </label>
                  <Tooltip text="Lab personnel performing the experiment. Multiple operators capture operator-to-operator variability. Single operator is fine for initial pilots.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="text"
                  value={operators}
                  onChange={(e) => setOperators(e.target.value)}
                  placeholder="Operator_A, Operator_B"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Timepoints (hours)
                  </label>
                  <Tooltip text="Time after compound addition. [12.0, 48.0] captures early stress response (12h) vs late/death (48h). Single timepoint reduces plates. Each timepoint creates a new plate.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="text"
                  value={timepoints}
                  onChange={(e) => setTimepoints(e.target.value)}
                  placeholder="12.0, 48.0"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm"
                />
              </div>
            </div>
          </div>

          {/* Sentinels */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <h4 className="text-lg font-semibold text-white">Sentinel Wells (QC)</h4>
              <Tooltip text="Quality control wells repeated across all plates at fixed doses. Used for Statistical Process Control (SPC) to detect plate drift, batch effects, and assay degradation over time.">
                <span className="text-slate-400 text-sm">ⓘ</span>
              </Tooltip>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    DMSO (vehicle control)
                  </label>
                  <Tooltip text="Negative control (no compound). Essential baseline for all calculations. 4-8 replicates recommended for tight control limits.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={sentinelDMSO}
                  onChange={(e) => {
                    clearPreset();
                    setSentinelDMSO(parseInt(e.target.value));
                  }}
                  min={0}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    tBHQ (30 µM)
                  </label>
                  <Tooltip text="Oxidative stress positive control. Fixed IC50 dose monitors NRF2 pathway response consistency across plates.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={sentinelTBHQ}
                  onChange={(e) => {
                    clearPreset();
                    setSentinelTBHQ(parseInt(e.target.value));
                  }}
                  min={0}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Thapsigargin (0.5 µM)
                  </label>
                  <Tooltip text="ER stress positive control. Fixed IC50 dose monitors SERCA pump inhibition and UPR pathway consistency.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={sentinelThapsigargin}
                  onChange={(e) => {
                    clearPreset();
                    setSentinelThapsigargin(parseInt(e.target.value));
                  }}
                  min={0}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Oligomycin (1 µM)
                  </label>
                  <Tooltip text="Mitochondrial stress positive control. Fixed IC50 dose monitors ATP synthase inhibition and OXPHOS disruption.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={sentinelOligomycin}
                  onChange={(e) => {
                    clearPreset();
                    setSentinelOligomycin(parseInt(e.target.value));
                  }}
                  min={0}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    MG132 (1 µM)
                  </label>
                  <Tooltip text="Proteasome inhibitor positive control. Fixed IC50 dose monitors protein degradation blockade and proteostasis stress.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <input
                  type="number"
                  value={sentinelMG132}
                  onChange={(e) => {
                    clearPreset();
                    setSentinelMG132(parseInt(e.target.value));
                  }}
                  min={0}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <p className="text-xs text-slate-400">
                Counts are per cell line. Sentinels enable Statistical Process Control (SPC) monitoring.
              </p>
            </div>
          </div>

          {/* Plate Layout */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <h4 className="text-lg font-semibold text-white">Plate Layout</h4>
              <Tooltip text="Physical plate format and well exclusion strategies. Higher throughput (384-well) vs easier handling (96-well). Edge/corner exclusion reduces artifacts but costs wells.">
                <span className="text-slate-400 text-sm">ⓘ</span>
              </Tooltip>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Plate Format
                  </label>
                  <Tooltip text="96-well: 8×12 layout, easier handling, standard. 384-well: 16×24 layout, 4× density, higher throughput but requires precision liquid handling.">
                    <span className="text-slate-400 text-xs">ⓘ</span>
                  </Tooltip>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => {
                      clearPreset();
                      setPlateFormat(96);
                    }}
                    className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                      plateFormat === 96
                        ? 'bg-green-600 text-white border-2 border-green-400'
                        : 'bg-slate-900 text-slate-400 border border-slate-700 hover:border-slate-500'
                    }`}
                  >
                    96-well
                  </button>
                  <button
                    onClick={() => {
                      clearPreset();
                      setPlateFormat(384);
                    }}
                    className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                      plateFormat === 384
                        ? 'bg-green-600 text-white border-2 border-green-400'
                        : 'bg-slate-900 text-slate-400 border border-slate-700 hover:border-slate-500'
                    }`}
                  >
                    384-well
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checkerboard}
                    onChange={(e) => {
                      clearPreset();
                      setCheckerboard(e.target.checked);
                    }}
                    className="w-5 h-5 bg-slate-900 border-slate-700 rounded focus:ring-2 focus:ring-green-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-medium text-slate-300">Checkerboard Layout</div>
                      <Tooltip text="Mix cell lines on same plate in alternating pattern. Pro: eliminates plate-to-plate confounding. Con: halves wells per cell line. Good for direct comparisons.">
                        <span className="text-slate-400 text-xs">ⓘ</span>
                      </Tooltip>
                    </div>
                    <div className="text-xs text-slate-400">Mix cell lines on same plate</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={excludeCorners}
                    onChange={(e) => {
                      clearPreset();
                      setExcludeCorners(e.target.checked);
                    }}
                    className="w-5 h-5 bg-slate-900 border-slate-700 rounded focus:ring-2 focus:ring-green-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-medium text-slate-300">Exclude Corners</div>
                      <Tooltip text="Skip 4 corner wells (A1, A12, H1, H12). Common QC practice - corners prone to temperature gradients and handling artifacts. Minimal cost (4/96 wells).">
                        <span className="text-slate-400 text-xs">ⓘ</span>
                      </Tooltip>
                    </div>
                    <div className="text-xs text-slate-400">Skip corner wells (QC practice)</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={excludeMidRowWells}
                    onChange={(e) => {
                      clearPreset();
                      setExcludeMidRowWells(e.target.checked);
                    }}
                    className="w-5 h-5 bg-slate-900 border-slate-700 rounded focus:ring-2 focus:ring-green-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-medium text-slate-300">Exclude Mid-Row Wells</div>
                      <Tooltip text="Skip 4 mid-row wells (A6, A7, H6, H7 for 96-well). Used in phase0_v2 design. These positions can show edge-adjacent artifacts. Cost: 4/96 wells.">
                        <span className="text-slate-400 text-xs">ⓘ</span>
                      </Tooltip>
                    </div>
                    <div className="text-xs text-slate-400">Skip mid-row edge wells (phase0_v2 practice)</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={excludeEdges}
                    onChange={(e) => {
                      clearPreset();
                      setExcludeEdges(e.target.checked);
                    }}
                    className="w-5 h-5 bg-slate-900 border-slate-700 rounded focus:ring-2 focus:ring-green-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-medium text-slate-300">Exclude Edges</div>
                      <Tooltip text="Skip all edge wells (entire first/last row and column). Eliminates evaporation and temperature artifacts. Cost: 40% fewer wells (96→48). Use for high-stakes experiments.">
                        <span className="text-slate-400 text-xs">ⓘ</span>
                      </Tooltip>
                    </div>
                    <div className="text-xs text-slate-400">Skip all edge wells (~40% reduction)</div>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Well Calculator & Preview */}
      {wellStats && (
        <div className="bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-700/30 rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-xl font-bold text-white">🧮 Design Calculator</h3>
            {wellStats.fits ? (
              <span className="text-xs px-2 py-1 rounded-full bg-green-900/30 text-green-400 border border-green-700">
                ✓ Fits
              </span>
            ) : (
              <span className="text-xs px-2 py-1 rounded-full bg-red-900/30 text-red-400 border border-red-700">
                ✗ Too many wells!
              </span>
            )}
          </div>

          {/* Statistics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <div className="text-xs text-slate-400 mb-1">Total Wells</div>
              <div className="text-2xl font-bold text-white">{wellStats.totalWells}</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <div className="text-xs text-slate-400 mb-1">Plates</div>
              <div className="text-2xl font-bold text-cyan-400">{wellStats.nPlates}</div>
            </div>
            <div className={`bg-slate-800/50 border rounded-lg p-4 ${
              wellStats.fits ? 'border-slate-700' : 'border-red-700 bg-red-900/10'
            }`}>
              <div className="text-xs text-slate-400 mb-1">Wells/Plate</div>
              <div className={`text-2xl font-bold ${
                wellStats.fits ? 'text-violet-400' : 'text-red-400'
              }`}>{wellStats.wellsPerPlate}</div>
              <div className={`text-xs mt-1 ${
                wellStats.fits ? 'text-slate-500' : 'text-red-400 font-semibold'
              }`}>
                {wellStats.fits ? `of ${wellStats.availableWells} available` : `exceeds ${wellStats.availableWells} available!`}
              </div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <div className="text-xs text-slate-400 mb-1">Available Wells</div>
              <div className="text-2xl font-bold text-white">{wellStats.availableWells}</div>
              <div className="text-xs text-slate-500 mt-1">
                {plateFormat}-well {excludeEdges ? '(edges excluded)' : excludeCorners && excludeMidRowWells ? '(8 wells excluded)' : excludeCorners ? '(4 corners excluded)' : '(full plate)'}
              </div>
            </div>
          </div>

          {/* Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-green-400 mb-2">Experimental Wells</h4>
              <div className="text-xl font-bold text-white mb-2">{wellStats.experimentalWells}</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>• {selectedCellLines.length} cell line{selectedCellLines.length > 1 ? 's' : ''}</div>
                <div>• {selectedCompounds.length} compound{selectedCompounds.length > 1 ? 's' : ''}</div>
                <div>• {doseMultipliers.split(',').length} dose{doseMultipliers.split(',').length > 1 ? 's' : ''} × {replicatesPerDose} rep{replicatesPerDose > 1 ? 's' : ''}</div>
              </div>
            </div>
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-blue-400 mb-2">Sentinel Wells (QC)</h4>
              <div className="text-xl font-bold text-white mb-2">{wellStats.sentinelWells}</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>• {sentinelDMSO} DMSO per cell line</div>
                <div>• {sentinelTBHQ} tBHQ per cell line</div>
                <div>• {sentinelThapsigargin} thapsigargin per cell line</div>
                <div>• {sentinelOligomycin} oligomycin per cell line</div>
                <div>• {sentinelMG132} MG132 per cell line</div>
              </div>
            </div>
          </div>

          {/* Warning if doesn't fit */}
          {!wellStats.fits && !matchesV2Defaults && (
            <div className="mt-4 bg-red-900/20 border border-red-700 rounded-lg p-4">
              <div className="text-sm text-red-300">
                <strong>⚠️ Design doesn't fit!</strong> Need {wellStats.wellsPerPlate} wells but only {wellStats.availableWells} available per plate.
              </div>
              <div className="text-xs text-red-400 mt-2 space-y-2">
                {/* Auto-fix buttons */}
                <div className="flex gap-2 pt-2">
                  {plateFormat === 96 && wellStats.wellsPerPlate <= 380 && (
                    <button
                      onClick={() => {
                        clearPreset();
                        setPlateFormat(384);
                      }}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition-colors"
                    >
                      ⚡ Auto-fix: Switch to 384-well
                    </button>
                  )}
                  {replicatesPerDose > 1 && (
                    <button
                      onClick={() => {
                        clearPreset();
                        setReplicatesPerDose(replicatesPerDose - 1);
                      }}
                      className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-semibold hover:bg-amber-700 transition-colors"
                    >
                      ⚡ Auto-fix: Reduce replicates to {replicatesPerDose - 1}
                    </button>
                  )}
                </div>
                <div className="pt-2 border-t border-red-700/30">
                  <div><strong>Manual options:</strong></div>
                  <div>• Switch to 384-well format (has 380 available with corners excluded)</div>
                  <div>• Reduce: (1) Number of compounds, (2) Number of doses, (3) Replicates per dose, (4) Sentinels</div>
                  <div className="mt-2 text-amber-300">💡 <strong>Tip:</strong> Each compound uses {doseMultipliers.split(',').length} doses × {replicatesPerDose} reps = {doseMultipliers.split(',').length * replicatesPerDose} wells. Need to remove {Math.ceil((wellStats.wellsPerPlate - wellStats.availableWells) / (doseMultipliers.split(',').length * replicatesPerDose))} compounds to fit.</div>
                </div>
              </div>
            </div>
          )}

          {/* Info about well exclusions when visible */}
          {wellStats.fits && (excludeCorners || excludeMidRowWells) && (
            <div className="mt-4 bg-blue-900/20 border border-blue-700/30 rounded-lg p-4">
              <div className="text-sm text-blue-300">
                <strong>ℹ️ Well exclusions active:</strong>
              </div>
              <div className="text-xs text-blue-400 mt-2 space-y-1">
                {excludeCorners && <div>• 4 corner wells excluded: A1, A12, H1, H12</div>}
                {excludeMidRowWells && <div>• 4 mid-row wells excluded: A6, A7, H6, H7</div>}
                <div className="mt-2 text-slate-400">Total: {96 - wellStats.availableWells} excluded, {wellStats.availableWells} available</div>
              </div>
            </div>
          )}

          {matchesV2Defaults && phase0V2Design && (
            <div className="mt-4 bg-violet-900/20 border border-violet-700 rounded-lg p-4">
              <div className="text-sm text-violet-300">
                <strong>ℹ️ About phase0_v2 compound splitting:</strong>
              </div>
              <div className="text-xs text-violet-400 mt-2 space-y-1">
                <div>• phase0_v2 uses <strong>5 compounds per plate</strong> (not all 10), creating 2 sub-plates per condition</div>
                <div>• Each plate: 5 compounds × 6 doses × 2 reps + 28 sentinels = <strong>88 wells</strong> (fits on 96-well plate)</div>
                <div>• This custom splitting logic is <strong>not available in the generator form</strong></div>
                <div>• To create a similar design, use 5 compounds instead of 10, or switch to 384-well format</div>
              </div>
            </div>
          )}

          {/* Plate Preview */}
          {Object.keys(previewWells).length > 0 && (
            <div className="mt-6 pt-6 border-t border-cyan-700/30">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-cyan-400 flex items-center gap-2">
                  <span>🗺️</span>
                  <span>Live Plate Preview</span>
                  <span className="text-xs text-slate-500">({Object.keys(previewWells).length} {Object.keys(previewWells).length === 1 ? 'plate' : 'plates'})</span>
                </h4>
                <div className="flex items-center gap-2">
                  {!wellStats.fits && (
                    <div className="text-xs text-red-400 bg-red-900/20 border border-red-700/30 rounded px-2 py-1">
                      ⚠️ Preview truncated - design exceeds plate capacity
                    </div>
                  )}
                  {matchesV2Defaults && phase0V2Design && (
                    <div className="text-xs text-violet-400 bg-violet-900/20 border border-violet-700/30 rounded px-2 py-1 flex items-center gap-1">
                      <span>✓</span>
                      <span>EXACT phase0_v2 layout</span>
                    </div>
                  )}
                  <button
                    onClick={() => exportForLLMReview()}
                    className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded flex items-center gap-1.5 transition-colors"
                    title="Download design snapshot for LLM review (ChatGPT, Claude, etc.)"
                  >
                    <span>🤖</span>
                    <span>Download for AI Review</span>
                  </button>
                </div>
              </div>
              <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                {/* Horizontal scroll container for plates */}
                <div className="overflow-x-auto pb-4">
                  <div className="flex gap-6 min-w-max">
                    {Object.entries(previewWells)
                      .sort(([a], [b]) => {
                        // Extract numeric part for proper numeric sorting (Plate_1, Plate_2, ..., Plate_10)
                        const numA = parseInt(a.match(/\d+/)?.[0] || '0');
                        const numB = parseInt(b.match(/\d+/)?.[0] || '0');
                        if (numA !== numB) return numA - numB;
                        // If same number, fall back to string comparison
                        return a.localeCompare(b);
                      })
                      .map(([plateId, plateWells]) => (
                        <div key={plateId} className="flex-shrink-0">
                          <DesignPlatePreview
                            plateId={plateId}
                            wells={plateWells}
                          />
                        </div>
                      ))}
                  </div>
                </div>
                <div className="mt-6 grid grid-cols-2 gap-4 text-xs">
                  {/* Legend */}
                  <div>
                    <div className="font-semibold text-slate-300 mb-2">Compounds (fill color):</div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#ef4444] flex-shrink-0"></div>
                        <span className="text-slate-300">tBHQ</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#22c55e] flex-shrink-0"></div>
                        <span className="text-slate-300">oligomycin</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#f97316] flex-shrink-0"></div>
                        <span className="text-slate-300">H₂O₂</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#14b8a6] flex-shrink-0"></div>
                        <span className="text-slate-300">etoposide</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#f59e0b] flex-shrink-0"></div>
                        <span className="text-slate-300">tunicamycin</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#06b6d4] flex-shrink-0"></div>
                        <span className="text-slate-300">MG132</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#eab308] flex-shrink-0"></div>
                        <span className="text-slate-300">thapsigargin</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#3b82f6] flex-shrink-0"></div>
                        <span className="text-slate-300">nocodazole</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#84cc16] flex-shrink-0"></div>
                        <span className="text-slate-300">CCCP</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#8b5cf6] flex-shrink-0"></div>
                        <span className="text-slate-300">paclitaxel</span>
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-300 mb-2">Well types:</div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded bg-white flex-shrink-0"></div>
                        <span className="text-slate-400">Sentinel (vehicle)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded flex-shrink-0" style={{background: 'linear-gradient(135deg, #ffffff 50%, #ef4444 50%)'}}></div>
                        <span className="text-slate-400">Sentinel (compound)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded bg-slate-600 flex-shrink-0"></div>
                        <span className="text-slate-400">DMSO vehicle</span>
                      </div>
                    </div>
                    <div className="font-semibold text-slate-300 mb-2 mt-3">Cell lines (border):</div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded border-2 border-[#8b5cf6] bg-slate-700 flex-shrink-0"></div>
                        <span className="text-slate-400">A549</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded border-2 border-[#ec4899] bg-slate-700 flex-shrink-0"></div>
                        <span className="text-slate-400">HepG2</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <div className="text-xs text-slate-400 text-center">
                    Showing all {Object.keys(previewWells).length} plates. {checkerboard ? 'Checkerboard: both cell lines on same plate.' : 'Separate plates per cell line.'} Scroll horizontally to see all plates.
                  </div>
                  {matchesV2Defaults && phase0V2Design ? (
                    <>
                      <div className="text-xs text-violet-400/80 bg-violet-900/10 rounded p-2 mt-2 flex items-center gap-2">
                        <span>✓</span>
                        <span><strong>EXACT phase0_v2 preview:</strong> This is the actual phase0_founder_v2_controls_stratified design loaded from file, showing the custom 8-well exclusion (A1, A6, A7, A12, H1, H6, H7, H12) and spatial sentinel stratification.</span>
                      </div>
                      <div className="mt-2">
                        <DesignInvariantBadge
                          wells={phase0V2Design.wells}
                          metadata={phase0V2Design.metadata}
                        />
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-green-400/70 bg-green-900/10 rounded p-2 mt-2 flex items-center gap-2">
                      <span>✓</span>
                      <span><strong>Accurate preview:</strong> This layout matches the exact algorithm used by the backend generator, including corner/edge exclusion if enabled.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Generate Button */}
      <div className="flex justify-end gap-4">
        <button
          onClick={handleGenerate}
          disabled={generating || !designId || !description || (wellStats ? !wellStats.fits : false)}
          className="px-8 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {generating ? 'Generating...' : '✨ Generate Design'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <div className="text-red-300">
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-6">
          <h4 className="text-lg font-semibold text-green-400 mb-4">✓ Design Generated Successfully!</h4>
          <div className="space-y-3 text-sm text-slate-300">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-slate-400">Design ID:</span>
                <span className="ml-2 font-mono text-white">{result.design_id}</span>
              </div>
              <div>
                <span className="text-slate-400">Total Wells:</span>
                <span className="ml-2 font-bold text-green-400">{result.metadata?.total_wells}</span>
              </div>
              <div>
                <span className="text-slate-400">Plates:</span>
                <span className="ml-2 font-bold text-white">{result.metadata?.n_plates}</span>
              </div>
              <div>
                <span className="text-slate-400">Format:</span>
                <span className="ml-2 text-white">{result.metadata?.plate_format}-well</span>
              </div>
            </div>
            <div className="pt-3 border-t border-green-700/30">
              <p className="text-slate-300">
                Design saved to: <code className="text-green-400">data/designs/{result.design_id}.json</code>
              </p>
              <p className="text-slate-400 text-xs mt-2">
                Run simulation: <code className="bg-slate-800 px-2 py-1 rounded text-green-400">
                  python3 standalone_cell_thalamus.py --design-json data/designs/{result.design_id}.json --seed 0
                </code>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const DesignCatalogTab: React.FC = () => {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDesign, setExpandedDesign] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'designs' | 'evolution' | 'comparison' | 'principles' | 'create'>('designs');
  const [fullDesignData, setFullDesignData] = useState<Record<string, FullDesignData>>({});
  const [loadingDesigns, setLoadingDesigns] = useState<Set<string>>(new Set());

  const exportDesignForLLMReview = (designId: string) => {
    console.log('exportDesignForLLMReview called for:', designId);

    const fullDesign = fullDesignData[designId];
    if (!fullDesign) {
      console.error('Design data not loaded');
      return;
    }

    const designData = fullDesign.design_data;
    const catalogEntry = fullDesign.catalog_entry;

    // Build the export package
    const exportData = {
      _meta: {
        export_type: 'design_for_llm_review',
        version: '1.0.0',
        purpose: 'Complete design snapshot for LLM feedback (ChatGPT, Claude, etc.)',
        timestamp: new Date().toISOString(),
        design_id: designId,
      },

      design_space: {
        cell_lines: {
          available: AVAILABLE_CELL_LINES.map(cl => ({
            value: cl,
            selected: catalogEntry.metadata.cell_lines?.includes(cl) || false,
          })),
          constraints: ['Cell lines are SEPARATE: no mixing within plate'],
        },
        compounds: {
          available: AVAILABLE_COMPOUNDS.map(c => ({
            value: c,
            selected: true, // From catalog, assume all listed compounds are used
          })),
          constraints: ['96-well format fits 5 compounds × 6 doses × 2 replicates = 60 experimental + 28 sentinels = 88 wells'],
        },
      },

      current_parameters: {
        design_id: designData.design_id,
        description: designData.description,
        cell_lines: catalogEntry.metadata.cell_lines || [],
        compounds: catalogEntry.metadata.n_compounds || 0,
        timepoints_h: catalogEntry.metadata.timepoints_h || [],
        days: catalogEntry.metadata.days || [],
        operators: catalogEntry.metadata.operators || [],
        plate_format: 96,
      },

      statistics: {
        total_wells: catalogEntry.metadata.n_wells,
        sentinel_wells: catalogEntry.metadata.n_wells - (catalogEntry.metadata.n_wells || 0),
        experimental_wells: catalogEntry.metadata.n_wells || 0,
        plates: catalogEntry.metadata.n_plates,
        wells_per_plate: catalogEntry.metadata.wells_per_plate,
      },

      design_preview: {
        source: catalogEntry.filename,
        wells: designData.wells,
        metadata: designData.metadata,
      },

      validation: (() => {
        try {
          const certificate = checkPhase0V2Design(designData.wells, designData.metadata);
          return {
            violations: certificate.violations,
            stats: certificate.stats,
            scaffoldMetadata: certificate.scaffoldMetadata,
          };
        } catch (error) {
          console.error('Validation failed:', error);
          return {
            error: 'Validation failed: ' + (error instanceof Error ? error.message : String(error)),
          };
        }
      })(),

      context: {
        design_goals: [
          'Maximum identifiability (position = identity)',
          'Batch orthogonality (day × operator × timepoint)',
          'Spatial scatter (eliminate gradient confounding)',
          'Position stability (same position = same condition within cell line)',
        ],
        constraints: [
          'Fixed sentinel scaffold (28 sentinels, same positions on all plates)',
          'Exact fill requirement (88 wells per plate, no partials)',
          'Cell line separation (no mixing on same plate)',
          'Identical conditions per timepoint (multiset consistency)',
        ],
        invariants_enforced: [
          'sentinel_scaffold_exact_match',
          'plate_capacity',
          'condition_multiset_identical',
          'experimental_position_stability',
          'spatial_dispersion (bbox area ≥ 40)',
          'sentinel_placement_quality',
          'batch_balance',
        ],
      },

      how_to_use: {
        instructions: [
          '1. Copy this entire JSON file',
          '2. Go to ChatGPT/Claude',
          '3. Paste the JSON',
          '4. Ask: "Review this experimental design. Does it satisfy the stated goals? What would you improve?"',
        ],
        example_questions: [
          'Does this design satisfy the identifiability and spatial scatter goals?',
          'Are there red flags in the statistics or validation?',
          'What would you change to improve the design?',
          'How would adding a 72h timepoint affect plate count?',
        ],
      },
    };

    console.log('Export data prepared:', exportData);

    // Trigger download
    try {
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `design_for_llm_review_${designId}_${new Date().toISOString().split('T')[0]}.json`;
      console.log('Download filename:', a.download);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      console.log('Download triggered successfully');
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  useEffect(() => {
    fetchCatalog();
  }, []);

  const fetchCatalog = async () => {
    const ac = new AbortController();
    try {
      setLoading(true);
      const response = await fetch(API_ENDPOINTS.catalog, { signal: ac.signal });
      if (!response.ok) throw new Error('Failed to fetch catalog');
      const data = await response.json();
      setCatalog(data);
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchFullDesign = async (designId: string) => {
    if (fullDesignData[designId] || loadingDesigns.has(designId)) return;

    setLoadingDesigns((prev) => new Set(prev).add(designId));

    const ac = new AbortController();
    try {
      const response = await fetch(API_ENDPOINTS.catalogDesign(designId), { signal: ac.signal });
      if (!response.ok) throw new Error('Failed to fetch design data');
      const data = await response.json();
      setFullDesignData((prev) => ({ ...prev, [designId]: data }));
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        console.error(`Error fetching design ${designId}:`, err);
      }
    } finally {
      setLoadingDesigns((prev) => {
        const newSet = new Set(prev);
        newSet.delete(designId);
        return newSet;
      });
    }
  };

  const handleToggleExpand = (designId: string) => {
    if (expandedDesign === designId) {
      setExpandedDesign(null);
    } else {
      setExpandedDesign(designId);
      fetchFullDesign(designId);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading design catalog...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
        <p className="text-red-400">Error loading catalog: {error}</p>
      </div>
    );
  }

  if (!catalog) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-900/30 to-blue-900/30 border border-violet-700/30 rounded-lg p-6">
        <h2 className="text-2xl font-bold text-white mb-2">📐 Design Catalog</h2>
        <p className="text-slate-300">{catalog.description}</p>
        <p className="text-slate-400 text-sm mt-1">Version {catalog.catalog_version}</p>
      </div>

      {/* View Selector */}
      <div className="flex gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-700 w-fit">
        <button
          onClick={() => setActiveView('create')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'create'
              ? 'bg-green-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          ✨ Create New
        </button>
        <button
          onClick={() => setActiveView('designs')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'designs'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📋 Designs
        </button>
        <button
          onClick={() => setActiveView('evolution')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'evolution'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          🔄 Evolution
        </button>
        <button
          onClick={() => setActiveView('comparison')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'comparison'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📊 Comparison
        </button>
        <button
          onClick={() => setActiveView('principles')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'principles'
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
          }`}
        >
          📖 Principles
        </button>
      </div>

      {/* Create New Design View */}
      {activeView === 'create' && (
        <DesignGeneratorForm />
      )}

      {/* Designs View */}
      {activeView === 'designs' && (
        <div className="space-y-4">
          {catalog.designs.map((design) => (
            <div
              key={design.design_id}
              className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden"
            >
              {/* Design Header */}
              <div
                className="p-4 cursor-pointer hover:bg-slate-700/30 transition-colors"
                onClick={() => handleToggleExpand(design.design_id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">
                        {design.status === 'current' ? '✓' : '○'}
                      </span>
                      <div>
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                          {design.design_id}
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              design.status === 'current'
                                ? 'bg-green-900/30 text-green-400 border border-green-700'
                                : 'bg-slate-700/30 text-slate-400 border border-slate-600'
                            }`}
                          >
                            {design.status}
                          </span>
                          <span className="text-xs px-2 py-1 rounded-full bg-violet-900/30 text-violet-400 border border-violet-700">
                            {design.version}
                          </span>
                          {fullDesignData[design.design_id] && (
                            <DesignInvariantBadge
                              wells={fullDesignData[design.design_id].design_data.wells}
                              metadata={fullDesignData[design.design_id].design_data.metadata}
                              compact={true}
                            />
                          )}
                        </h3>
                        <p className="text-slate-400 text-sm mt-1">{design.description}</p>
                      </div>
                    </div>

                    {/* Metadata Summary */}
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                      {design.metadata.n_plates && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded flex items-center gap-1">
                          <span className="text-violet-400">🧫</span>
                          {design.metadata.n_plates} plates
                        </span>
                      )}
                      {design.metadata.wells_per_plate && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.wells_per_plate} wells/plate
                        </span>
                      )}
                      {design.metadata.n_wells && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded font-semibold text-white">
                          {design.metadata.n_wells} total wells
                        </span>
                      )}
                      {design.metadata.timepoints_h && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded flex items-center gap-1">
                          <span className="text-blue-400">⏱</span>
                          {design.metadata.timepoints_h.join('h, ')}h
                        </span>
                      )}
                      {design.metadata.n_compounds && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.n_compounds} compounds
                        </span>
                      )}
                      {design.metadata.n_cell_lines && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.n_cell_lines} cell lines
                        </span>
                      )}
                      {design.metadata.cell_lines && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.cell_lines.join(', ')}
                        </span>
                      )}
                      {design.metadata.operators && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.operators.length} operators
                        </span>
                      )}
                      {design.metadata.days && (
                        <span className="bg-slate-700/30 px-2 py-1 rounded">
                          {design.metadata.days.length} days
                        </span>
                      )}
                      <span className="bg-slate-700/30 px-2 py-1 rounded">
                        {design.created_at}
                      </span>
                    </div>
                  </div>

                  <button className="text-slate-400 hover:text-white transition-colors">
                    {expandedDesign === design.design_id ? '▼' : '▶'}
                  </button>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedDesign === design.design_id && (
                <div className="border-t border-slate-700 p-4 space-y-4">
                  {/* Loading indicator */}
                  {loadingDesigns.has(design.design_id) && (
                    <div className="text-center py-4 text-slate-400">
                      Loading design details...
                    </div>
                  )}

                  {/* Invariant Validation Certificate */}
                  {fullDesignData[design.design_id] && (
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-violet-400 flex items-center gap-2">
                          <span>🔒</span>
                          <span>Design Validation</span>
                        </h4>
                        <button
                          onClick={() => exportDesignForLLMReview(design.design_id)}
                          className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded flex items-center gap-1.5 transition-colors"
                          title="Download design snapshot for LLM review (ChatGPT, Claude, etc.)"
                        >
                          <span>🤖</span>
                          <span>Download for AI Review</span>
                        </button>
                      </div>
                      <DesignInvariantBadge
                        wells={fullDesignData[design.design_id].design_data.wells}
                        metadata={fullDesignData[design.design_id].design_data.metadata}
                      />
                    </div>
                  )}

                  {/* Plate Map Preview */}
                  {fullDesignData[design.design_id] && (
                    <div>
                      <h4 className="text-sm font-semibold text-cyan-400 mb-3 flex items-center gap-2">
                        <span>🗺️</span>
                        <span>Plate Layout Preview</span>
                        <span className="text-xs text-slate-500 font-normal">
                          ({fullDesignData[design.design_id].design_data.wells.length} wells)
                        </span>
                      </h4>
                      <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                        {/* Horizontal scroll container */}
                        <div className="overflow-x-auto pb-2">
                          <div className="flex gap-4 min-w-max">
                            {/* Group wells by plate_id */}
                            {Object.entries(
                              fullDesignData[design.design_id].design_data.wells.reduce(
                                (acc: Record<string, any[]>, well: any) => {
                                  if (!acc[well.plate_id]) acc[well.plate_id] = [];
                                  acc[well.plate_id].push(well);
                                  return acc;
                                },
                                {}
                              )
                            )
                              .sort(([a], [b]) => {
                                // Extract numeric part for proper numeric sorting
                                const numA = parseInt(a.match(/\d+/)?.[0] || '0');
                                const numB = parseInt(b.match(/\d+/)?.[0] || '0');
                                return numA - numB;
                              })
                              .map(([plateId, plateWells]) => (
                                <DesignPlatePreview
                                  key={plateId}
                                  plateId={plateId}
                                  wells={plateWells}
                                />
                              ))}
                          </div>
                        </div>
                        {/* Legend */}
                        <div className="mt-4 pt-3 border-t border-slate-700">
                          <div className="text-xs font-semibold text-slate-300 mb-2">Compounds (fill):</div>
                          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#ef4444] flex-shrink-0"></div>
                              <span className="text-slate-300">tBHQ</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#22c55e] flex-shrink-0"></div>
                              <span className="text-slate-300">oligomycin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#f97316] flex-shrink-0"></div>
                              <span className="text-slate-300">H₂O₂</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#14b8a6] flex-shrink-0"></div>
                              <span className="text-slate-300">etoposide</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#f59e0b] flex-shrink-0"></div>
                              <span className="text-slate-300">tunicamycin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#06b6d4] flex-shrink-0"></div>
                              <span className="text-slate-300">MG132</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#eab308] flex-shrink-0"></div>
                              <span className="text-slate-300">thapsigargin</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#3b82f6] flex-shrink-0"></div>
                              <span className="text-slate-300">nocodazole</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#84cc16] flex-shrink-0"></div>
                              <span className="text-slate-300">CCCP</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full bg-[#8b5cf6] flex-shrink-0"></div>
                              <span className="text-slate-300">paclitaxel</span>
                            </div>
                          </div>
                          <div className="mt-3 pt-3 border-t border-slate-700/50">
                            <div className="flex items-center gap-4 text-xs mb-2 flex-wrap">
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded bg-white flex-shrink-0"></div>
                                <span className="text-slate-400">Sentinel (vehicle)</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded flex-shrink-0" style={{background: 'linear-gradient(135deg, #ffffff 50%, #ef4444 50%)'}}></div>
                                <span className="text-slate-400">Sentinel (compound)</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded bg-slate-600 flex-shrink-0"></div>
                                <span className="text-slate-400">DMSO</span>
                              </div>
                            </div>
                            <div className="text-xs font-semibold text-slate-300 mb-1.5">Cell lines (border):</div>
                            <div className="flex items-center gap-4 text-xs">
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded border-2 border-[#8b5cf6] bg-slate-700 flex-shrink-0"></div>
                                <span className="text-slate-400">A549</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded border-2 border-[#ec4899] bg-slate-700 flex-shrink-0"></div>
                                <span className="text-slate-400">HepG2</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Features */}
                  {design.features && design.features.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-violet-400 mb-2">Features</h4>
                      <ul className="space-y-1">
                        {design.features.map((feature, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-violet-400">•</span>
                            {feature}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Improvements */}
                  {design.improvements_over_previous && design.improvements_over_previous.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-green-400 mb-2">
                        Improvements Over Previous
                      </h4>
                      <ul className="space-y-1">
                        {design.improvements_over_previous.map((improvement, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-green-400">✓</span>
                            {improvement}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Chart Definitions */}
                  {design.chart_definitions && design.chart_definitions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-blue-400 mb-2">Chart Definitions</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {design.chart_definitions.map((chart: any, idx: number) => (
                          <div key={idx} className="bg-slate-900/50 border border-slate-600 rounded p-3">
                            <div className="font-mono text-sm text-blue-300">{chart.chart_id}</div>
                            <div className="text-xs text-slate-400 mt-1">
                              Use: {chart.intended_use}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">
                              Capabilities: {chart.capabilities.join(', ')}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Notes */}
                  {design.notes && (
                    <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                      <h4 className="text-sm font-semibold text-amber-400 mb-1">Notes</h4>
                      <p className="text-sm text-slate-300">{design.notes}</p>
                    </div>
                  )}

                  {/* Buffer Well Rationale */}
                  {design.buffer_well_rationale && (
                    <div className="bg-indigo-900/10 border border-indigo-700/30 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-indigo-400 mb-3 flex items-center gap-2">
                        <span>🎯</span>
                        <span>Buffer Well Strategy</span>
                      </h4>

                      <div className="space-y-3">
                        {/* Summary */}
                        <div>
                          <p className="text-sm text-slate-300 italic">
                            {design.buffer_well_rationale.summary}
                          </p>
                        </div>

                        {/* Positions */}
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-400">Reserved positions:</span>
                          <div className="flex gap-1">
                            {design.buffer_well_rationale.positions.map((pos) => (
                              <span key={pos} className="bg-slate-800 px-2 py-1 rounded font-mono text-indigo-400 border border-slate-700">
                                {pos}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Technical Necessity */}
                        <div>
                          <h5 className="text-xs font-semibold text-indigo-300 mb-2">Technical Necessity</h5>
                          <ul className="space-y-1.5">
                            {design.buffer_well_rationale.technical_necessity.map((point, idx) => (
                              <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                                <span className="text-indigo-400 mt-0.5">•</span>
                                <span>{point}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Epistemic Function */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-indigo-300 mb-1">Epistemic Function</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.epistemic_function}</p>
                        </div>

                        {/* Information Economics */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-green-300 mb-1">Information Economics</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.information_economics}</p>
                        </div>

                        {/* Phase Dependency */}
                        <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-amber-300 mb-1">Phase Dependency</h5>
                          <p className="text-xs text-slate-300">{design.buffer_well_rationale.phase_dependency}</p>
                        </div>

                        {/* Design Principle */}
                        <div className="bg-violet-900/10 border border-violet-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-violet-300 mb-1">Design Principle</h5>
                          <p className="text-xs text-slate-300 italic font-semibold">{design.buffer_well_rationale.design_principle}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Cell Line Separation Rationale */}
                  {design.cell_line_separation_rationale && (
                    <div className="bg-emerald-900/10 border border-emerald-700/30 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
                        <span>🧬</span>
                        <span>Cell Line Separation Strategy</span>
                      </h4>

                      <div className="space-y-3">
                        {/* Summary */}
                        <div>
                          <p className="text-sm text-slate-300 italic">
                            {design.cell_line_separation_rationale.summary}
                          </p>
                        </div>

                        {/* Plate Allocation */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded p-3">
                          <h5 className="text-xs font-semibold text-emerald-300 mb-2">Plate Allocation</h5>
                          <div className="space-y-1">
                            {Object.entries(design.cell_line_separation_rationale.plate_allocation).map(
                              ([cellLine, plates]) => (
                                <div key={cellLine} className="text-xs font-mono">
                                  <span className="text-emerald-400">{cellLine}:</span>{' '}
                                  <span className="text-white">{plates}</span>
                                </div>
                              )
                            )}
                          </div>
                        </div>

                        {/* Why Separation */}
                        <div>
                          <h5 className="text-xs font-semibold text-emerald-300 mb-2">
                            Why Separation (Not Mixing)
                          </h5>
                          <ul className="space-y-1.5">
                            {design.cell_line_separation_rationale.why_separation.map((point, idx) => (
                              <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                                <span className="text-emerald-400 mt-0.5">•</span>
                                <span>{point}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* When Mixing Makes Sense */}
                        <div className="bg-blue-900/10 border border-blue-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-blue-300 mb-1">
                            When Mixing Makes Sense
                          </h5>
                          <p className="text-xs text-slate-300">
                            {design.cell_line_separation_rationale.when_mixing_makes_sense}
                          </p>
                        </div>

                        {/* Phase 0 Recommendation */}
                        <div className="bg-amber-900/10 border border-amber-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-amber-300 mb-1">
                            Phase 0 Recommendation
                          </h5>
                          <p className="text-xs text-slate-300">
                            {design.cell_line_separation_rationale.phase0_recommendation}
                          </p>
                        </div>

                        {/* Design Principle */}
                        <div className="bg-violet-900/10 border border-violet-700/30 rounded p-3">
                          <h5 className="text-xs font-semibold text-violet-300 mb-1">Design Principle</h5>
                          <p className="text-xs text-slate-300 italic font-semibold">
                            {design.cell_line_separation_rationale.design_principle}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Next Iteration Ideas */}
                  {design.next_iteration_ideas && design.next_iteration_ideas.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-cyan-400 mb-2">
                        Next Iteration Ideas
                      </h4>
                      <ul className="space-y-1">
                        {design.next_iteration_ideas.map((idea, idx) => (
                          <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-cyan-400">→</span>
                            {idea}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Evolution View */}
      {activeView === 'evolution' && (
        <div className="space-y-4">
          {catalog.design_evolution_log.map((entry, idx) => (
            <div key={idx} className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="text-2xl">{idx + 1}</div>
                <div className="flex items-center gap-2 text-lg font-semibold text-white">
                  <span className="text-slate-400">{entry.from_version || 'initial'}</span>
                  <span className="text-violet-400">→</span>
                  <span>{entry.to_version}</span>
                  <span className="text-sm text-slate-400 font-normal">({entry.date})</span>
                </div>
              </div>

              <div className="space-y-3">
                {/* Reason */}
                <div>
                  <h4 className="text-sm font-semibold text-amber-400 mb-1">Reason</h4>
                  <p className="text-sm text-slate-300">{entry.reason}</p>
                </div>

                {/* Evidence */}
                {entry.evidence && Object.keys(entry.evidence).length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-red-400 mb-2">Evidence</h4>
                    <div className="bg-slate-900/50 border border-slate-600 rounded p-3 space-y-1">
                      {Object.entries(entry.evidence).map(([key, value]) => (
                        <div key={key} className="text-sm font-mono">
                          <span className="text-slate-400">{key}:</span>{' '}
                          <span className="text-white">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Changes */}
                <div>
                  <h4 className="text-sm font-semibold text-green-400 mb-2">Key Changes</h4>
                  <ul className="space-y-1">
                    {entry.key_changes.map((change, changeIdx) => (
                      <li
                        key={changeIdx}
                        className="text-sm text-slate-300 flex items-start gap-2"
                      >
                        <span className="text-green-400">•</span>
                        {change}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Comparison View */}
      {activeView === 'comparison' && (
        <div className="space-y-6">
          {/* Comparison Header */}
          <div className="bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-700/30 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-white mb-2">📊 Design Comparison</h2>
            <p className="text-slate-300">Head-to-head statistical power analysis across all design versions</p>
          </div>

          {/* Overview Table */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Overview</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">Total Wells</th>
                    <th className="text-right py-3 px-4 text-slate-300">Plates</th>
                    <th className="text-right py-3 px-4 text-slate-300">Wells/Plate</th>
                    <th className="text-right py-3 px-4 text-slate-300">Sentinels</th>
                    <th className="text-right py-3 px-4 text-slate-300">Experimental</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4">2,304</td>
                    <td className="text-right py-3 px-4">24</td>
                    <td className="text-right py-3 px-4">96</td>
                    <td className="text-right py-3 px-4">384</td>
                    <td className="text-right py-3 px-4">1,920</td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4">2,112</td>
                    <td className="text-right py-3 px-4">24</td>
                    <td className="text-right py-3 px-4">88</td>
                    <td className="text-right py-3 px-4">688</td>
                    <td className="text-right py-3 px-4">1,424</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">12 (50% ↓)</td>
                    <td className="text-right py-3 px-4">96</td>
                    <td className="text-right py-3 px-4">416</td>
                    <td className="text-right py-3 px-4">736</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-Cell-Line Replication */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Per-Cell-Line Replication</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">A549 Wells</th>
                    <th className="text-right py-3 px-4 text-slate-300">HepG2 Wells</th>
                    <th className="text-left py-3 px-4 text-slate-300">Strategy</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="text-right py-3 px-4">1,152</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Mixed on same plates</td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4">1,056</td>
                    <td className="text-right py-3 px-4">1,056</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Separated (Plates 1-12 vs 13-24)</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">576 (1.8× ↓)</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">576 (1.8× ↓)</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">Checkerboard (both on same plate)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Statistical Power */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Statistical Power Analysis</h3>
            <p className="text-sm text-slate-400 mb-4">
              EC50 confidence interval width from dose-response curve fitting (bootstrap, 50 iterations). Lower = better precision.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600">
                    <th className="text-left py-3 px-4 text-slate-300">Design</th>
                    <th className="text-right py-3 px-4 text-slate-300">Mean EC50 CI Width (µM)</th>
                    <th className="text-right py-3 px-4 text-slate-300">vs v2 Ratio</th>
                    <th className="text-left py-3 px-4 text-slate-300">Interpretation</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v1</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">1.39</td>
                    <td className="text-right py-3 px-4 text-green-400">0.53×</td>
                    <td className="py-3 px-4">
                      <span className="bg-green-900/30 text-green-400 px-2 py-1 rounded text-xs border border-green-700">
                        HIGH POWER ✓
                      </span>
                    </td>
                  </tr>
                  <tr className="border-b border-slate-700/50">
                    <td className="py-3 px-4 font-mono text-violet-400">v2</td>
                    <td className="text-right py-3 px-4 text-green-400 font-semibold">2.64</td>
                    <td className="text-right py-3 px-4">1.00×</td>
                    <td className="py-3 px-4">
                      <span className="bg-green-900/30 text-green-400 px-2 py-1 rounded text-xs border border-green-700">
                        HIGH POWER ✓
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 font-mono text-violet-400">v3</td>
                    <td className="text-right py-3 px-4 text-amber-400 font-semibold">10.08</td>
                    <td className="text-right py-3 px-4 text-red-400 font-semibold">3.82× ↑</td>
                    <td className="py-3 px-4">
                      <span className="bg-amber-900/30 text-amber-400 px-2 py-1 rounded text-xs border border-amber-700">
                        MODERATE POWER
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Key Trade-offs */}
          <div className="bg-gradient-to-r from-red-900/20 to-amber-900/20 border border-red-700/30 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">⚠️ Key Trade-offs: v3 vs v2</h3>

            <div className="grid md:grid-cols-2 gap-6 mb-4">
              <div className="bg-slate-900/50 border border-green-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-green-400 mb-3 flex items-center gap-2">
                  <span>✓</span>
                  <span>Throughput Gains (v3)</span>
                </h4>
                <ul className="space-y-2 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>50% fewer plates (12 vs 24)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>Checkerboard eliminates spatial confounding</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>Paired cell-line comparisons under identical conditions</span>
                  </li>
                </ul>
              </div>

              <div className="bg-slate-900/50 border border-red-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                  <span>✗</span>
                  <span>Statistical Power Loss (v3)</span>
                </h4>
                <ul className="space-y-2 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>1.8× fewer replicates per cell line</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>3.82× wider EC50 confidence intervals</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">•</span>
                    <span>~75% loss in statistical power for dose-response</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="bg-red-900/10 border border-red-700/30 rounded p-4">
              <h4 className="text-sm font-semibold text-red-300 mb-2">✗ VERDICT: SEVERE Power Loss</h4>
              <p className="text-sm text-slate-300 mb-3">
                v3's throughput gain (50% fewer plates) comes at a steep cost: EC50 estimates are 3.82× less precise.
                This makes dose-response characterization significantly less reliable.
              </p>
              <p className="text-sm text-slate-400 italic">
                Recommendation: Use v3 for cost-constrained screening or when rough dose-response is sufficient.
                Use v2 for establishing founder datasets or when precise EC50 estimates are critical.
              </p>
            </div>
          </div>

          {/* When to Use Each Design */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">When to Use Each Design</h3>
            <div className="space-y-4">
              <div className="bg-slate-900/50 border border-violet-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-violet-400 mb-2">Use v2 (Separated, High Power)</h4>
                <ul className="space-y-1 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Establishing founder/reference datasets</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Need precise EC50 estimates for dose selection</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Statistical power is critical for downstream decisions</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400">→</span>
                    <span>Cost/throughput is not the limiting factor</span>
                  </li>
                </ul>
              </div>

              <div className="bg-slate-900/50 border border-cyan-700/30 rounded p-4">
                <h4 className="text-sm font-semibold text-cyan-400 mb-2">Use v3 (Mixed Checkerboard, Lower Power)</h4>
                <ul className="space-y-1 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Cost/plate supply is limiting</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Rough dose-response screening is sufficient</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Already have good EC50 estimates from v2</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400">→</span>
                    <span>Prioritizing paired cell-line comparisons</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Principles View */}
      {activeView === 'principles' && (
        <div className="space-y-6">
          {/* Design Principles */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Design Principles</h3>
            <div className="space-y-4">
              {Object.entries(catalog.design_principles).map(([key, value]) => (
                <div key={key}>
                  <h4 className="text-sm font-semibold text-violet-400 mb-1 capitalize">
                    {key.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-sm text-slate-300">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Glossary */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Glossary</h3>
            <div className="space-y-3">
              {Object.entries(catalog.glossary).map(([term, definition]) => (
                <div key={term}>
                  <h4 className="text-sm font-semibold text-blue-400 mb-1 capitalize">
                    {term.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-sm text-slate-300">{definition}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DesignCatalogTab;
