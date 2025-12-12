/**
 * Plate Map Preview Component
 *
 * Shows visual preview of 96-well plate layout before running simulation
 */

import React, { useMemo, useState } from 'react';
import templateAData from '../utils/template_A.json';
import templateBData from '../utils/template_B.json';

interface Well {
  wellId: string;
  row: string;
  col: number;
  type: 'sentinel' | 'dmso' | 'experimental';
  cellLine?: string;
  compound?: string;
  dose?: string;
  sentinelType?: 'mild' | 'strong' | 'dmso' | 'reference';
}

interface PlateMapPreviewProps {
  cellLines: string[];
  compounds: string[];
  mode: 'demo' | 'quick' | 'full' | 'custom';
}

const PlateMapPreview: React.FC<PlateMapPreviewProps> = ({ cellLines, compounds, mode }) => {
  const [selectedTemplate, setSelectedTemplate] = useState<'A' | 'B'>('A');

  // Generate well layout based on mode
  const wells = useMemo(() => {
    const wellArray: (Well | null)[][] = Array(8)
      .fill(null)
      .map(() => Array(12).fill(null));

    const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

    // Helper to create well ID
    const createWellId = (row: number, col: number): string => {
      return `${rows[row]}${(col + 1).toString().padStart(2, '0')}`;
    };

    // FULL MODE: Use fixed templates
    if (mode === 'full') {
      const templateData = selectedTemplate === 'A' ? templateAData : templateBData;

      (templateData as any[]).forEach((well) => {
        const rowIdx = rows.indexOf(well.row);
        const colIdx = well.col - 1;

        if (rowIdx >= 0 && colIdx >= 0 && rowIdx < 8 && colIdx < 12) {
          wellArray[rowIdx][colIdx] = {
            wellId: well.wellId,
            row: well.row,
            col: well.col,
            type: well.type as 'sentinel' | 'dmso' | 'experimental',
            cellLine: well.cellLine,
            compound: well.compound,
            dose: well.dose ? `${well.dose} µM` : undefined,
            sentinelType: well.sentinelType,
          };
        }
      });

      return wellArray;
    }

    // DEMO MODE: 7 wells for quick UI testing
    if (mode === 'demo') {
      const cellLine = cellLines[0] || 'A549';

      // Just a few experimental wells in corners for visualization
      wellArray[0][0] = {
        wellId: 'A01',
        row: 'A',
        col: 1,
        type: 'dmso',
        cellLine,
        compound: 'DMSO',
        dose: '0 µM',
      };

      wellArray[0][1] = {
        wellId: 'A02',
        row: 'A',
        col: 2,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '1 µM',
      };

      wellArray[0][2] = {
        wellId: 'A03',
        row: 'A',
        col: 3,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '100 µM',
      };

      wellArray[1][0] = {
        wellId: 'B01',
        row: 'B',
        col: 1,
        type: 'experimental',
        cellLine,
        compound: 'tunicamycin',
        dose: '1 µM',
      };

      wellArray[1][1] = {
        wellId: 'B02',
        row: 'B',
        col: 2,
        type: 'experimental',
        cellLine,
        compound: 'tunicamycin',
        dose: '100 µM',
      };

      wellArray[7][11] = {
        wellId: 'H12',
        row: 'H',
        col: 12,
        type: 'sentinel',
        compound: 'tBHQ',
        dose: '1 µM',
        sentinelType: 'mild',
      };

      wellArray[7][10] = {
        wellId: 'H11',
        row: 'H',
        col: 11,
        type: 'sentinel',
        compound: 'tBHQ',
        dose: '100 µM',
        sentinelType: 'strong',
      };

      return wellArray;
    }

    // QUICK & CUSTOM MODES: Simple layouts (not Phase 0 templates)
    const useCompounds = mode === 'quick'
      ? ['tBHQ', 'tunicamycin', 'CCCP']
      : compounds.length > 0 ? compounds : [];

    const doses = ['0.1', '1', '10', '100'];
    const useCellLines = cellLines.length > 0 ? cellLines : ['A549'];

    let wellCounter = 0;
    const createWellCounter = (counter: number): { row: number; col: number } => {
      const row = counter % 8;
      const col = Math.floor(counter / 8) % 12;
      return { row, col };
    };

    useCellLines.forEach((cellLine) => {
      // DMSO control
      const { row, col } = createWellCounter(wellCounter);
      wellArray[row][col] = {
        wellId: createWellId(row, col),
        row: rows[row],
        col: col + 1,
        type: 'dmso',
        cellLine,
        compound: 'DMSO',
        dose: '0 µM',
      };
      wellCounter++;

      // Experimental wells
      useCompounds.forEach((compound) => {
        doses.forEach((dose) => {
          const { row, col } = createWellCounter(wellCounter);
          if (row < 8 && col < 12) {
            wellArray[row][col] = {
              wellId: createWellId(row, col),
              row: rows[row],
              col: col + 1,
              type: 'experimental',
              cellLine,
              compound,
              dose: `${dose} µM`,
            };
          }
          wellCounter++;
        });
      });
    });

    return wellArray;
  }, [cellLines, compounds, mode, selectedTemplate]);

  // Color scheme: border = cell line, fill = compound, shade = dose
  const getBorderColor = (well: Well | null) => {
    if (!well) return '#334155'; // slate-700

    if (well.type === 'sentinel') return '#000000'; // black
    if (well.type === 'dmso') return '#64748b'; // slate-500

    // Cell line colors for border
    const cellLineColors: Record<string, string> = {
      A549: '#8b5cf6', // violet
      HepG2: '#ec4899', // pink
      U2OS: '#14b8a6', // teal
    };
    return cellLineColors[well.cellLine || ''] || '#6366f1'; // indigo
  };

  const getCompoundColor = (compound: string): string => {
    // Map compounds to distinct colors
    const compoundColors: Record<string, string> = {
      tBHQ: '#ef4444', // red
      H2O2: '#f97316', // orange
      tunicamycin: '#f59e0b', // amber
      thapsigargin: '#eab308', // yellow
      CCCP: '#84cc16', // lime
      oligomycin: '#22c55e', // green
      etoposide: '#14b8a6', // teal
      MG132: '#06b6d4', // cyan
      nocodazole: '#3b82f6', // blue
      paclitaxel: '#8b5cf6', // violet
    };
    return compoundColors[compound] || '#6366f1'; // indigo default
  };

  const getDoseOpacity = (dose: string | undefined): number => {
    if (!dose) return 0.5;

    // Extract numeric value from dose string
    const match = dose.match(/(\d+\.?\d*)/);
    if (!match) return 0.5;

    const value = parseFloat(match[1]);

    // Map dose to opacity: 0.1 → 0.3, 1 → 0.5, 10 → 0.7, 100 → 0.9
    if (value <= 0.1) return 0.3;
    if (value <= 1) return 0.5;
    if (value <= 10) return 0.7;
    return 0.9;
  };

  const getWellStyle = (well: Well | null) => {
    if (!well) {
      return {
        backgroundColor: '#1e293b', // slate-800 (empty)
        borderColor: '#334155',
        borderWidth: '1px',
      };
    }

    if (well.type === 'sentinel') {
      return {
        backgroundColor: '#000000', // black
        borderColor: '#000000',
        borderWidth: '2px',
      };
    }

    if (well.type === 'dmso') {
      return {
        backgroundColor: '#475569', // slate-600
        borderColor: getBorderColor(well),
        borderWidth: '2px',
      };
    }

    // Experimental wells: compound color with dose opacity
    const compoundColor = getCompoundColor(well.compound || '');
    const opacity = getDoseOpacity(well.dose);

    // Convert hex to rgba
    const r = parseInt(compoundColor.slice(1, 3), 16);
    const g = parseInt(compoundColor.slice(3, 5), 16);
    const b = parseInt(compoundColor.slice(5, 7), 16);

    return {
      backgroundColor: `rgba(${r}, ${g}, ${b}, ${opacity})`,
      borderColor: getBorderColor(well),
      borderWidth: '2px',
    };
  };

  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Plate Map Preview</h3>
          <p className="text-sm text-slate-400 mt-1">
            {mode === 'demo' && '7 wells - Quick UI test'}
            {mode === 'quick' && '3 compounds - Quick validation'}
            {mode === 'full' && 'Phase 0 design: 2 cell lines, 48 wells each'}
            {mode === 'custom' && 'Custom compound selection'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Template Selector - ONLY for full mode */}
          {mode === 'full' && (
            <label className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Template:</span>
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value as 'A' | 'B')}
                className="bg-slate-900 border border-slate-700 text-white rounded px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                <option value="A">A (fixed)</option>
                <option value="B">B (fixed)</option>
              </select>
            </label>
          )}
          <div className="text-sm text-slate-400">
            {mode === 'full' && 'Plate 1 of 6'}
          </div>
        </div>
      </div>

      {/* Grid and Legend Layout */}
      <div className="flex gap-6 items-start">
        {/* 96-well grid */}
        <div className="overflow-x-auto overflow-y-visible flex-shrink-0">
          <div className="inline-block py-12">
          {/* Column headers */}
          <div className="flex mb-1">
            <div className="w-8"></div>
            {Array.from({ length: 12 }, (_, i) => (
              <div key={i} className="w-12 mr-1 text-center text-xs text-slate-400">
                {i + 1}
              </div>
            ))}
          </div>

          {/* Rows */}
          {wells.map((row, rowIdx) => (
            <div key={rowIdx} className="flex items-center mb-1">
              {/* Row label */}
              <div className="w-8 text-xs text-slate-400 text-right pr-2">
                {rows[rowIdx]}
              </div>

              {/* Wells */}
              {row.map((well, colIdx) => {
                const wellStyle = getWellStyle(well);
                return (
                  <div
                    key={colIdx}
                    className="w-12 h-10 mr-1 rounded flex items-center justify-center group relative cursor-pointer transition-all hover:ring-2 hover:ring-white/50"
                    style={{
                      backgroundColor: wellStyle.backgroundColor,
                      borderColor: wellStyle.borderColor,
                      borderWidth: wellStyle.borderWidth,
                      borderStyle: 'solid',
                    }}
                    title={
                      well
                        ? `${well.wellId}\n${well.type === 'sentinel' ? 'Sentinel' : well.type === 'dmso' ? 'DMSO Control' : `${well.compound} ${well.dose}`}`
                        : 'Empty'
                    }
                  >
                  {well && (
                    <>
                      {/* Well ID in top-left corner */}
                      <span className="absolute top-0.5 left-0.5 text-[8px] font-mono text-white/50 group-hover:text-white/70">
                        {well.wellId}
                      </span>
                    </>
                  )}

                  {/* Tooltip - smart positioning */}
                  {well && (
                    <div
                      className={`
                        absolute hidden group-hover:block pointer-events-none z-50
                        ${rowIdx < 2 ? 'top-full mt-2' : 'bottom-full mb-2'}
                        ${colIdx < 3 ? 'left-0' : colIdx > 9 ? 'right-0' : 'left-1/2 -translate-x-1/2'}
                      `}
                    >
                      <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                        <div className="font-bold text-white text-sm mb-1">{well.wellId}</div>
                        <div className="text-violet-300 mb-1">{well.cellLine}</div>
                        {well.type === 'sentinel' ? (
                          <>
                            <div className="text-green-400 font-semibold">
                              🎯 Sentinel {well.sentinelType === 'mild' ? '(Mild)' : '(Strong)'}
                            </div>
                            <div className="text-slate-400">{well.compound} {well.dose}</div>
                          </>
                        ) : well.type === 'dmso' ? (
                          <div className="text-slate-400">
                            {well.sentinelType === 'reference' ? 'Reference Control' : 'DMSO Control'}
                          </div>
                        ) : (
                          <>
                            <div className="text-blue-300">{well.compound}</div>
                            <div className="text-orange-300">{well.dose}</div>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            </div>
          ))}
          </div>
        </div>

        {/* Legend - Right Side */}
        <div className="flex-1 space-y-3 text-xs pt-12">
          {/* Cell Lines (Borders) */}
          <div>
            <div className="text-slate-400 font-semibold mb-2">Cell Lines (border):</div>
            <div className="space-y-1">
              {mode === 'full' ? (
                <>
                  <div className="flex items-center gap-2">
                    <div
                      className="w-4 h-4 rounded border-2"
                      style={{
                        borderColor: '#8b5cf6',
                        backgroundColor: '#1e293b'
                      }}
                    ></div>
                    <span className="text-slate-300">A549 (rows A-D)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className="w-4 h-4 rounded border-2"
                      style={{
                        borderColor: '#ec4899',
                        backgroundColor: '#1e293b'
                      }}
                    ></div>
                    <span className="text-slate-300">HepG2 (rows E-H)</span>
                  </div>
                </>
              ) : (
                cellLines.map((cellLine) => {
                  const colors: Record<string, string> = {
                    A549: '#8b5cf6',
                    HepG2: '#ec4899',
                    U2OS: '#14b8a6',
                  };
                  return (
                    <div key={cellLine} className="flex items-center gap-2">
                      <div
                        className="w-4 h-4 rounded border-2"
                        style={{
                          borderColor: colors[cellLine] || '#6366f1',
                          backgroundColor: '#1e293b'
                        }}
                      ></div>
                      <span className="text-slate-300">{cellLine}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Compounds (Fill) - Only show detailed list for full mode */}
          {mode === 'full' && (
            <div>
              <div className="text-slate-400 font-semibold mb-2">Compounds (fill):</div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#ef4444' }}></div>
                  <span className="text-slate-300">tBHQ</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">tert-Butylhydroquinone</div>
                      <div className="text-orange-300">Oxidative Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#f97316' }}></div>
                  <span className="text-slate-300">H₂O₂</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Hydrogen Peroxide</div>
                      <div className="text-orange-300">Oxidative Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#f59e0b' }}></div>
                  <span className="text-slate-300">tunicamycin</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Tunicamycin</div>
                      <div className="text-orange-300">ER Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#eab308' }}></div>
                  <span className="text-slate-300">thapsigargin</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Thapsigargin</div>
                      <div className="text-orange-300">ER Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#84cc16' }}></div>
                  <span className="text-slate-300">CCCP</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">CCCP</div>
                      <div className="text-orange-300">Mitochondrial Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#22c55e' }}></div>
                  <span className="text-slate-300">oligomycin</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Oligomycin</div>
                      <div className="text-orange-300">Mitochondrial Stress</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#14b8a6' }}></div>
                  <span className="text-slate-300">etoposide</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Etoposide</div>
                      <div className="text-orange-300">DNA Damage</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#06b6d4' }}></div>
                  <span className="text-slate-300">MG132</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">MG132</div>
                      <div className="text-orange-300">Proteasome Inhibition</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#3b82f6' }}></div>
                  <span className="text-slate-300">nocodazole</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Nocodazole</div>
                      <div className="text-orange-300">Microtubule Disruption</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#8b5cf6' }}></div>
                  <span className="text-slate-300">paclitaxel</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Paclitaxel</div>
                      <div className="text-orange-300">Microtubule Stabilization</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 group relative cursor-help">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: '#475569' }}></div>
                  <span className="text-slate-300">DMSO</span>
                  <div className="absolute right-full mr-2 top-0 hidden group-hover:block z-50 pointer-events-none">
                    <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                      <div className="font-bold text-white">Dimethyl Sulfoxide</div>
                      <div className="text-orange-300">Vehicle Control</div>
                      <div className="text-slate-400 mt-1">Solvent baseline (0.1-1% DMSO)</div>
                      <div className="text-slate-400 text-[10px] mt-1">Note: Some assays use EtOH or other solvents</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Dose Intensity */}
          <div>
            <div className="text-slate-400 font-semibold mb-2">Dose (opacity):</div>
            <div className="text-xs text-slate-500 mb-2 italic">Example: tBHQ at 4 doses</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.3)' }}></div>
                <span className="text-slate-300">0.1 µM (light)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.5)' }}></div>
                <span className="text-slate-300">1 µM</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.7)' }}></div>
                <span className="text-slate-300">10 µM</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.9)' }}></div>
                <span className="text-slate-300">100 µM (dark)</span>
              </div>
            </div>
          </div>

          {/* Fixed Controls */}
          <div>
            <div className="text-slate-400 font-semibold mb-2">Fixed Controls (16 wells):</div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 group relative cursor-help">
                <div className="w-4 h-4 rounded border-2" style={{ backgroundColor: '#000000', borderColor: '#000000' }}></div>
                <span className="text-slate-300">Sentinel (4 wells)</span>
                <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-50 pointer-events-none">
                  <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                    <div className="font-bold text-white">Sentinel Wells (Fixed QC)</div>
                    <div className="text-green-400 mt-2">2 Mild: C1, G1 (tBHQ 1 µM)</div>
                    <div className="text-orange-400">2 Strong: D1, H1 (tBHQ 100 µM)</div>
                    <div className="text-slate-400 mt-2 text-[10px]">Same positions on every plate and timepoint</div>
                    <div className="text-slate-400 text-[10px]">Used to detect plate-to-plate variability</div>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 group relative cursor-help">
                <div className="w-4 h-4 rounded border-2" style={{ backgroundColor: '#475569', borderColor: '#64748b' }}></div>
                <span className="text-slate-300">DMSO/Reference (12 wells)</span>
                <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-50 pointer-events-none">
                  <div className="bg-slate-900 border-2 border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-2xl">
                    <div className="font-bold text-white">DMSO & Reference Controls</div>
                    <div className="text-slate-400 mt-2 text-[10px]">8 DMSO: A1, B1, E1, F1, A12, B12, E12, F12</div>
                    <div className="text-slate-400 text-[10px]">4 Reference: C12, D12, G12, H12</div>
                    <div className="text-slate-400 mt-2 text-[10px]">Fixed positions for vehicle control baseline</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div> {/* End flex container */}

      {mode === 'full' && (
        <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3 border border-slate-700">
          <strong>Phase 0 Design:</strong> 6 assay plates total (3 plates × 2 timepoints: 12h & 48h).
          Each plate has 2 cell lines (48 wells each). Template A and B are used at both timepoints,
          ensuring timepoint and spatial effects can be separated. Sentinels remain in fixed positions
          across all plates for QC monitoring.
        </div>
      )}
    </div>
  );
};

export default PlateMapPreview;
