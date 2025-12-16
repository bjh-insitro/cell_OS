/**
 * Design Plate Preview - Visualization of actual plate layout from design catalog
 *
 * Shows 96-well plate with actual design data (matches PlateMapPreview visual style)
 */

import React from 'react';

interface Well {
  well_pos?: string;
  row?: string;
  col?: number;
  well_id?: string;
  compound: string;
  is_sentinel: boolean;
  dose_uM: number;
  cell_line: string;
}

interface DesignPlatePreviewProps {
  plateId: string;
  wells: Well[];
}

const DesignPlatePreview: React.FC<DesignPlatePreviewProps> = ({ plateId, wells }) => {
  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
  const cols = Array.from({ length: 12 }, (_, i) => i + 1);

  // Helper to generate 88-well positions (skipping reserved corners)
  const generateWellPositions = () => {
    const positions: string[] = [];
    const reserved = new Set(['A1', 'A12', 'A6', 'A7', 'H1', 'H12', 'H6', 'H7']);

    for (const row of rows) {
      for (const col of cols) {
        const pos = `${row}${col}`;
        if (!reserved.has(pos)) {
          positions.push(pos);
        }
      }
    }
    return positions;
  };

  // Helper to normalize well position (e.g., "A01" -> "A1", "H12" -> "H12")
  const normalizePosition = (pos: string): string => {
    const row = pos[0];
    const col = parseInt(pos.slice(1));
    return `${row}${col}`;
  };

  // Create well lookup
  const wellMap = new Map<string, Well>();

  wells.forEach((well, index) => {
    if (well.well_pos) {
      // Normalize position to handle both "A1" and "A01" formats
      const normalizedPos = normalizePosition(well.well_pos);
      wellMap.set(normalizedPos, well);
    } else if (well.well_id) {
      // v1 format: infer position from sequential index
      const positions = generateWellPositions();
      if (index < positions.length) {
        wellMap.set(positions[index], well);
      }
    }
  });

  // Compound colors (matching PlateMapPreview)
  const getCompoundColor = (compound: string): string => {
    const colors: Record<string, string> = {
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
    return colors[compound] || '#6366f1';
  };

  // Cell line colors (for borders)
  const getCellLineColor = (cellLine: string): string => {
    const colors: Record<string, string> = {
      A549: '#8b5cf6', // purple
      HepG2: '#ec4899', // pink
    };
    return colors[cellLine] || '#6366f1';
  };

  // Dose-based opacity
  const getDoseOpacity = (dose: number): number => {
    if (dose <= 0.1) return 0.3;
    if (dose <= 1) return 0.5;
    if (dose <= 10) return 0.7;
    return 0.9;
  };

  // Well styling (matching PlateMapPreview)
  const getWellStyle = (well: Well | undefined, wellPos: string) => {
    // Reserved corners
    const reserved = new Set(['A1', 'A12', 'A6', 'A7', 'H1', 'H12', 'H6', 'H7']);
    if (reserved.has(wellPos)) {
      return {
        background: '#0f172a',
        borderColor: '#1e293b',
        borderWidth: '1px',
      };
    }

    if (!well) {
      return {
        background: '#1e293b',
        borderColor: '#334155',
        borderWidth: '1px',
      };
    }

    // Get cell line border color
    const cellLineBorderColor = getCellLineColor(well.cell_line);

    // Sentinels with compound: diagonal split (white + compound color)
    if (well.is_sentinel && well.compound !== 'DMSO') {
      const compoundColor = getCompoundColor(well.compound);
      const opacity = getDoseOpacity(well.dose_uM);

      const r = parseInt(compoundColor.slice(1, 3), 16);
      const g = parseInt(compoundColor.slice(3, 5), 16);
      const b = parseInt(compoundColor.slice(5, 7), 16);

      return {
        background: `linear-gradient(135deg, #ffffff 50%, rgba(${r}, ${g}, ${b}, ${opacity}) 50%)`,
        borderColor: cellLineBorderColor,
        borderWidth: '2px',
      };
    }

    // Sentinels (DMSO/vehicle): white fill with cell line border
    if (well.is_sentinel) {
      return {
        background: '#ffffff',
        borderColor: cellLineBorderColor,
        borderWidth: '2px',
      };
    }

    // DMSO: gray fill with cell line border
    if (well.compound === 'DMSO') {
      return {
        background: '#475569',
        borderColor: cellLineBorderColor,
        borderWidth: '2px',
      };
    }

    // Experimental wells: compound color fill with cell line border
    const compoundColor = getCompoundColor(well.compound);
    const opacity = getDoseOpacity(well.dose_uM);

    const r = parseInt(compoundColor.slice(1, 3), 16);
    const g = parseInt(compoundColor.slice(3, 5), 16);
    const b = parseInt(compoundColor.slice(5, 7), 16);

    return {
      background: `rgba(${r}, ${g}, ${b}, ${opacity})`,
      borderColor: cellLineBorderColor,
      borderWidth: '2px',
    };
  };

  return (
    <div className="flex-shrink-0">
      {/* Plate label */}
      <div className="text-center mb-2">
        <div className="text-xs font-semibold text-violet-400">{plateId}</div>
      </div>

      <div className="inline-block py-1">
        {/* Column headers */}
        <div className="flex mb-0.5">
          <div className="w-3"></div>
          {cols.map((col) => (
            <div key={col} className="w-4 mr-0.5 text-center text-[7px] text-slate-400 font-mono">
              {col}
            </div>
          ))}
        </div>

        {/* Rows */}
        {rows.map((row) => (
          <div key={row} className="flex items-center mb-0.5">
            {/* Row label */}
            <div className="w-3 text-[7px] text-slate-400 text-right pr-0.5 font-mono">{row}</div>

            {/* Wells */}
            {cols.map((col) => {
              const wellPos = `${row}${col}`;
              const well = wellMap.get(wellPos);
              const wellStyle = getWellStyle(well, wellPos);

              return (
                <div
                  key={col}
                  className="w-4 h-3 mr-0.5 rounded-sm flex items-center justify-center group relative cursor-pointer transition-all hover:ring-1 hover:ring-white/50"
                  style={{
                    background: wellStyle.background,
                    borderColor: wellStyle.borderColor,
                    borderWidth: wellStyle.borderWidth,
                    borderStyle: 'solid',
                  }}
                  title={
                    well
                      ? `${wellPos}\n${well.compound}\n${well.dose_uM} µM\n${well.cell_line}${
                          well.is_sentinel ? '\nSentinel' : ''
                        }`
                      : `${wellPos}\nEmpty`
                  }
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

export default DesignPlatePreview;
