/**
 * Design Plate Preview - Visualization of actual plate layout from design catalog
 *
 * Supports 96-well and 384-well plates with actual design data
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
  sentinel_type?: string;
}

type PlateFormat = '96' | '384';

interface DesignPlatePreviewProps {
  plateId: string;
  wells: Well[];
  format?: PlateFormat;
  size?: 'small' | 'medium' | 'large';
  reservedWells?: Set<string>;
}

const PLATE_CONFIG: Record<PlateFormat, { rows: string[]; cols: number[] }> = {
  '96': {
    rows: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
    cols: Array.from({ length: 12 }, (_, i) => i + 1),
  },
  '384': {
    rows: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'],
    cols: Array.from({ length: 24 }, (_, i) => i + 1),
  },
};

const SIZE_CONFIG: Record<PlateFormat, Record<'small' | 'medium' | 'large', { well: string; wellH: string; gap: string; font: string; label: string }>> = {
  '96': {
    small: { well: 'w-4', wellH: 'h-3', gap: 'mr-0.5 mb-0.5', font: 'text-[7px]', label: 'w-3' },
    medium: { well: 'w-6', wellH: 'h-5', gap: 'mr-1 mb-1', font: 'text-[8px]', label: 'w-4' },
    large: { well: 'w-8', wellH: 'h-6', gap: 'mr-1 mb-1', font: 'text-xs', label: 'w-6' },
  },
  '384': {
    small: { well: 'w-2', wellH: 'h-1.5', gap: 'mr-px mb-px', font: 'text-[5px]', label: 'w-2' },
    medium: { well: 'w-3', wellH: 'h-2.5', gap: 'mr-0.5 mb-0.5', font: 'text-[6px]', label: 'w-3' },
    large: { well: 'w-4', wellH: 'h-3', gap: 'mr-0.5 mb-0.5', font: 'text-[7px]', label: 'w-4' },
  },
};

const DesignPlatePreview: React.FC<DesignPlatePreviewProps> = ({
  plateId,
  wells,
  format = '96',
  size = 'small',
  reservedWells,
}) => {
  const { rows, cols } = PLATE_CONFIG[format];
  const sizeConfig = SIZE_CONFIG[format][size];

  // Default reserved wells for 96-well format (legacy)
  const defaultReserved96 = new Set(['A1', 'A12', 'A6', 'A7', 'H1', 'H12', 'H6', 'H7']);
  const reserved = reservedWells || (format === '96' ? defaultReserved96 : new Set<string>());

  // Helper to generate well positions (skipping reserved)
  const generateWellPositions = () => {
    const positions: string[] = [];

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

  // Compound colors (matching PlateMapPreview + menadione)
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
      menadione: '#f97316', // orange (redox cycler)
    };
    return colors[compound] || '#6366f1';
  };

  // Dose color for continuous dose gradients (e.g., menadione 0-150 µM)
  const getDoseColor = (dose: number, maxDose: number = 150): string => {
    if (dose <= 0) return '#475569'; // gray for vehicle
    const normalized = Math.min(dose / maxDose, 1.0);
    // Gradient from light orange to dark red
    const r = Math.round(255 - normalized * 50);
    const g = Math.round(150 - normalized * 100);
    const b = Math.round(50 - normalized * 50);
    return `rgb(${r}, ${g}, ${b})`;
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

  // Sentinel type colors
  const getSentinelColor = (sentinelType?: string): string => {
    const colors: Record<string, string> = {
      vehicle: '#ffffff',
      mild_menadione: '#fbbf24', // amber
      strong_menadione: '#ef4444', // red
    };
    return colors[sentinelType || 'vehicle'] || '#ffffff';
  };

  // Well styling (matching PlateMapPreview)
  const getWellStyle = (well: Well | undefined, wellPos: string) => {
    // Reserved wells
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

    // Sentinels: use sentinel type color with distinct border
    if (well.is_sentinel) {
      const sentinelColor = getSentinelColor(well.sentinel_type);
      // For treated sentinels, show dose intensity
      if (well.dose_uM > 0) {
        return {
          background: sentinelColor,
          borderColor: '#fbbf24', // amber border for all sentinels
          borderWidth: '2px',
        };
      }
      // Vehicle sentinel
      return {
        background: sentinelColor,
        borderColor: '#fbbf24',
        borderWidth: '2px',
      };
    }

    // DMSO/Vehicle: gray fill
    if (well.compound === 'DMSO' || well.dose_uM <= 0) {
      return {
        background: '#475569',
        borderColor: cellLineBorderColor,
        borderWidth: '1px',
      };
    }

    // Experimental wells: dose-based color gradient
    const doseColor = getDoseColor(well.dose_uM);
    return {
      background: doseColor,
      borderColor: cellLineBorderColor,
      borderWidth: '1px',
    };
  };

  return (
    <div className="flex-shrink-0">
      {/* Plate label */}
      <div className="text-center mb-2">
        <div className={`${sizeConfig.font} font-semibold text-violet-400`}>{plateId}</div>
        <div className={`${sizeConfig.font} text-slate-500`}>{format}-well</div>
      </div>

      <div className="inline-block py-1">
        {/* Column headers */}
        <div className="flex mb-0.5">
          <div className={sizeConfig.label}></div>
          {cols.map((col) => (
            <div
              key={col}
              className={`${sizeConfig.well} ${sizeConfig.gap.split(' ')[0]} text-center ${sizeConfig.font} text-slate-400 font-mono`}
            >
              {/* Only show every 4th column label for 384-well to avoid crowding */}
              {format === '384' ? (col % 4 === 0 || col === 1 ? col : '') : col}
            </div>
          ))}
        </div>

        {/* Rows */}
        {rows.map((row) => (
          <div key={row} className={`flex items-center ${sizeConfig.gap.split(' ')[1]}`}>
            {/* Row label */}
            <div className={`${sizeConfig.label} ${sizeConfig.font} text-slate-400 text-right pr-0.5 font-mono`}>
              {row}
            </div>

            {/* Wells */}
            {cols.map((col) => {
              const wellPos = `${row}${col}`;
              const well = wellMap.get(wellPos);
              const wellStyle = getWellStyle(well, wellPos);

              return (
                <div
                  key={col}
                  className={`${sizeConfig.well} ${sizeConfig.wellH} ${sizeConfig.gap.split(' ')[0]} rounded-sm flex items-center justify-center group relative cursor-pointer transition-all hover:ring-1 hover:ring-white/50`}
                  style={{
                    background: wellStyle.background,
                    borderColor: wellStyle.borderColor,
                    borderWidth: wellStyle.borderWidth,
                    borderStyle: 'solid',
                  }}
                  title={
                    well
                      ? `${wellPos}\n${well.compound}\n${well.dose_uM} µM\n${well.cell_line}${
                          well.is_sentinel ? `\nSentinel (${well.sentinel_type || 'vehicle'})` : ''
                        }`
                      : `${wellPos}\nEmpty`
                  }
                />
              );
            })}
          </div>
        ))}
      </div>

      {/* Legend for 384-well plates */}
      {format === '384' && size !== 'small' && (
        <div className={`mt-2 flex flex-wrap gap-2 ${sizeConfig.font} text-slate-400`}>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 rounded-sm bg-white border-2 border-amber-400"></div>
            <span>Vehicle Sentinel</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 rounded-sm bg-amber-400 border-2 border-amber-400"></div>
            <span>Mild Sentinel</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 rounded-sm bg-red-500 border-2 border-amber-400"></div>
            <span>Strong Sentinel</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 rounded-sm" style={{ background: getDoseColor(5) }}></div>
            <span>Low Dose</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 rounded-sm" style={{ background: getDoseColor(150) }}></div>
            <span>High Dose</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default DesignPlatePreview;
