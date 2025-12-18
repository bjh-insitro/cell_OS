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
  mode: 'demo' | 'benchmark' | 'full';
}

const PlateMapPreview: React.FC<PlateMapPreviewProps> = ({ cellLines, compounds, mode }) => {
  // Generate well layout for a specific template
  const getWellsForTemplate = (template: 'A' | 'B') => {
    const wellArray: (Well | null)[][] = Array(8)
      .fill(null)
      .map(() => Array(12).fill(null));

    const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

    // Helper to create well ID
    const createWellId = (row: number, col: number): string => {
      return `${rows[row]}${(col + 1).toString().padStart(2, '0')}`;
    };

    // BENCHMARK & FULL MODE: Use fixed templates
    if (mode === 'benchmark' || mode === 'full') {
      const templateData = template === 'A' ? templateAData : templateBData;

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

    // DEMO MODE: 8 wells - tBHQ dose-response
    if (mode === 'demo') {
      const cellLine = cellLines[0] || 'A549';

      // DMSO vehicle control (A01)
      wellArray[0][0] = {
        wellId: 'A01',
        row: 'A',
        col: 1,
        type: 'dmso',
        cellLine,
        compound: 'DMSO',
        dose: '0 µM',
      };

      // tBHQ dose series (A02-A05)
      wellArray[0][1] = {
        wellId: 'A02',
        row: 'A',
        col: 2,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '0.1 µM',
      };

      wellArray[0][2] = {
        wellId: 'A03',
        row: 'A',
        col: 3,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '1 µM',
      };

      wellArray[0][3] = {
        wellId: 'A04',
        row: 'A',
        col: 4,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '10 µM',
      };

      wellArray[0][4] = {
        wellId: 'A05',
        row: 'A',
        col: 5,
        type: 'experimental',
        cellLine,
        compound: 'tBHQ',
        dose: '100 µM',
      };

      // Sentinels (A06-A08)
      wellArray[0][5] = {
        wellId: 'A06',
        row: 'A',
        col: 6,
        type: 'sentinel',
        cellLine,
        compound: 'DMSO',
        dose: '0 µM',
        sentinelType: 'reference',
      };

      wellArray[0][6] = {
        wellId: 'A07',
        row: 'A',
        col: 7,
        type: 'sentinel',
        cellLine,
        compound: 'tBHQ',
        dose: '1 µM',
        sentinelType: 'mild',
      };

      wellArray[0][7] = {
        wellId: 'A08',
        row: 'A',
        col: 8,
        type: 'sentinel',
        cellLine,
        compound: 'tBHQ',
        dose: '10 µM',
        sentinelType: 'strong',
      };

      return wellArray;
    }

    // Fallback: return empty array for any other mode
    return wellArray;
  };

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

  // Render a single plate grid
  const renderPlateGrid = (plateNumber: number, timepoint: string, template: 'A' | 'B') => {
    const wells = mode === 'demo' ? getWellsForTemplate('A') : getWellsForTemplate(template);
    const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

    return (
      <div key={`${timepoint}-${plateNumber}`} className="flex-shrink-0">
        {/* Plate label */}
        <div className="text-center mb-2">
          <div className="text-sm font-semibold text-violet-400">
            Plate {plateNumber} - {timepoint} - Template {template}
          </div>
          <div className="text-xs text-slate-500">Biological replicate {((plateNumber - 1) % 3) + 1}</div>
        </div>

        <div className="inline-block py-4">
          {/* Column headers */}
          <div className="flex mb-1">
            <div className="w-6"></div>
            {Array.from({ length: 12 }, (_, i) => (
              <div key={i} className="w-10 mr-0.5 text-center text-[10px] text-slate-400">
                {i + 1}
              </div>
            ))}
          </div>

          {/* Rows */}
          {wells.map((row, rowIdx) => (
          <div key={rowIdx} className="flex items-center mb-1">
            {/* Row label */}
            <div className="w-6 text-[10px] text-slate-400 text-right pr-1">
              {rows[rowIdx]}
            </div>

            {/* Wells */}
            {row.map((well, colIdx) => {
              const wellStyle = getWellStyle(well);
              return (
                <div
                  key={colIdx}
                  className="w-10 h-8 mr-0.5 rounded flex items-center justify-center group relative cursor-pointer transition-all hover:ring-2 hover:ring-white/50"
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
    );
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Plate Map Preview</h3>
          <p className="text-sm text-slate-400 mt-1">
            {mode === 'demo' && '8 wells - tBHQ dose-response (0.1→100%, 1→90%, 10→70%, 100→20%) + 3 sentinels'}
            {mode === 'benchmark' && 'Plate 1 (12h) - Template A: 2 cell lines, 40 wells per cell line + 16 sentinels (96 total)'}
            {mode === 'full' && 'Phase 0 design: 2 cell lines, 48 wells per cell line per plate'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-400">
            {mode === 'full' && 'All 6 plates: 3 @ 12h + 3 @ 48h (Templates A, B, A at each timepoint)'}
          </div>
        </div>
      </div>

      {/* Grid and Legend Layout */}
      {mode === 'demo' ? (
        <div className="flex gap-6 items-start">
          {/* Demo mode: single plate */}
          <div className="overflow-x-auto overflow-y-visible">
            {renderPlateGrid(1, 'Demo', 'A')}
          </div>
          {/* Legend for demo mode */}
          <div className="flex-1 space-y-3 text-xs pt-12">
            <div className="space-y-2">
              <div className="text-violet-400 font-semibold">Demo Mode Layout:</div>
              <div className="text-slate-300">
                <div>• A01: DMSO control (0 µM)</div>
                <div>• A02-A05: tBHQ dose series</div>
                <div className="ml-4 text-slate-400">
                  <div>→ 0.1 µM (minimal effect)</div>
                  <div>→ 1.0 µM (mild stress)</div>
                  <div>→ 10 µM (strong effect)</div>
                  <div>→ 100 µM (toxic)</div>
                </div>
                <div>• A06-A08: Sentinels (QC)</div>
                <div className="ml-4 text-slate-400">
                  <div>→ DMSO reference</div>
                  <div>→ Mild stress (1 µM)</div>
                  <div>→ Strong stress (10 µM)</div>
                </div>
              </div>
              <div className="text-slate-400 mt-3 pt-3 border-t border-slate-700">
                Red fill = tBHQ, darker = higher dose<br/>
                Black border = Sentinel wells
              </div>
            </div>
          </div>
        </div>
      ) : mode === 'benchmark' ? (
        /* Benchmark mode: 1 plate (Plate 1 - 12h - Template A) */
        <div className="overflow-x-auto overflow-y-visible">
          {renderPlateGrid(1, '12h', 'A')}
        </div>
      ) : (
        /* Full mode: all 6 plates in 2x3 grid */
        <div className="space-y-8">
          {/* 12h timepoint - 3 plates */}
          <div>
            <div className="text-lg font-semibold text-violet-400 mb-4">12h Timepoint</div>
            <div className="flex gap-6 overflow-x-auto">
              {renderPlateGrid(1, '12h', 'A')}
              {renderPlateGrid(2, '12h', 'B')}
              {renderPlateGrid(3, '12h', 'A')}
            </div>
          </div>

          {/* 48h timepoint - 3 plates */}
          <div>
            <div className="text-lg font-semibold text-violet-400 mb-4">48h Timepoint</div>
            <div className="flex gap-6 overflow-x-auto">
              {renderPlateGrid(4, '48h', 'A')}
              {renderPlateGrid(5, '48h', 'B')}
              {renderPlateGrid(6, '48h', 'A')}
            </div>
          </div>
        </div>
      )}

      {/* Legend for benchmark and full mode */}
      {(mode === 'benchmark' || mode === 'full') && (
        <div className="mt-6 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
          <div className="grid grid-cols-4 gap-6 text-xs">
            {/* Cell Lines (Borders) */}
            <div>
              <div className="text-slate-400 font-semibold mb-2">Cell Lines (border):</div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded border-2" style={{ borderColor: '#8b5cf6', backgroundColor: '#1e293b' }}></div>
                  <span className="text-slate-300 text-[10px]">A549 (A-D)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded border-2" style={{ borderColor: '#ec4899', backgroundColor: '#1e293b' }}></div>
                  <span className="text-slate-300 text-[10px]">HepG2 (E-H)</span>
                </div>
              </div>
            </div>

            {/* Compounds (Fill) */}
            <div>
              <div className="text-slate-400 font-semibold mb-2">Compounds (fill):</div>
              <div className="space-y-0.5">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#ef4444' }}></div>
                  <span className="text-slate-300 text-[10px]">tBHQ</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#f97316' }}></div>
                  <span className="text-slate-300 text-[10px]">H₂O₂</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#f59e0b' }}></div>
                  <span className="text-slate-300 text-[10px]">tunicamycin</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#eab308' }}></div>
                  <span className="text-slate-300 text-[10px]">thapsigargin</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#84cc16' }}></div>
                  <span className="text-slate-300 text-[10px]">CCCP</span>
                </div>
              </div>
            </div>

            <div>
              <div className="text-slate-400 font-semibold mb-2 invisible">More:</div>
              <div className="space-y-0.5">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#22c55e' }}></div>
                  <span className="text-slate-300 text-[10px]">oligomycin</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#14b8a6' }}></div>
                  <span className="text-slate-300 text-[10px]">etoposide</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#06b6d4' }}></div>
                  <span className="text-slate-300 text-[10px]">MG132</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#3b82f6' }}></div>
                  <span className="text-slate-300 text-[10px]">nocodazole</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#8b5cf6' }}></div>
                  <span className="text-slate-300 text-[10px]">paclitaxel</span>
                </div>
              </div>
            </div>

            {/* Dose & Controls */}
            <div>
              <div className="text-slate-400 font-semibold mb-2">Dose (opacity):</div>
              <div className="space-y-0.5 mb-3">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.3)' }}></div>
                  <span className="text-slate-300 text-[10px]">0.1 µM</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.5)' }}></div>
                  <span className="text-slate-300 text-[10px]">1 µM</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.7)' }}></div>
                  <span className="text-slate-300 text-[10px]">10 µM</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.9)' }}></div>
                  <span className="text-slate-300 text-[10px]">100 µM</span>
                </div>
              </div>
              <div className="text-slate-400 font-semibold mb-1">Controls:</div>
              <div className="space-y-0.5">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded border-2" style={{ backgroundColor: '#000000', borderColor: '#000000' }}></div>
                  <span className="text-slate-300 text-[10px]">Sentinel</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: '#475569' }}></div>
                  <span className="text-slate-300 text-[10px]">DMSO</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Full mode explanation */}
      {mode === 'full' && (
        <div className="mt-4 text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3 border border-slate-700">
          <strong>Phase 0 Design:</strong> 6 assay plates total. Each plate has 2 cell lines (48 wells each).
          Template A and B ensure timepoint and spatial effects can be separated. Sentinels in fixed positions
          across all plates for QC monitoring. Border color = cell line, fill color = compound, opacity = dose.
        </div>
      )}

    </div>
  );
};

export default PlateMapPreview;
