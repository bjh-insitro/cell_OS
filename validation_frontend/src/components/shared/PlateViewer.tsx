import React from 'react';

export type PlateFormat = '96' | '384' | '1536';
export type WellData = {
  id: string;
  color?: string;
  label?: string;
  tooltip?: {
    title: string;
    lines: string[];
  };
  borderColor?: string;
  borderWidth?: number;
};

export interface PlateViewerProps {
  format: PlateFormat;
  wells: WellData[];
  isDarkMode: boolean;
  size?: 'small' | 'medium' | 'large';
  showLabels?: boolean;
  showAxisLabels?: boolean;
  onWellClick?: (wellId: string) => void;
  className?: string;
}

interface PlateDimensions {
  rows: number;
  cols: number;
  wellWidth: string;
  wellHeight: string;
  fontSize: string;
}

const PLATE_DIMENSIONS: Record<PlateFormat, Record<'small' | 'medium' | 'large', PlateDimensions>> = {
  '96': {
    small: { rows: 8, cols: 12, wellWidth: 'w-4', wellHeight: 'h-4', fontSize: 'text-[6px]' },
    medium: { rows: 8, cols: 12, wellWidth: 'w-8', wellHeight: 'h-7', fontSize: 'text-xs' },
    large: { rows: 8, cols: 12, wellWidth: 'w-16', wellHeight: 'h-14', fontSize: 'text-xs' }, // Cell Thalamus size
  },
  '384': {
    small: { rows: 16, cols: 24, wellWidth: 'w-2', wellHeight: 'h-2', fontSize: 'text-[6px]' },
    medium: { rows: 16, cols: 24, wellWidth: 'w-8', wellHeight: 'h-7', fontSize: 'text-xs' }, // Scaled from 96-well large
    large: { rows: 16, cols: 24, wellWidth: 'w-12', wellHeight: 'h-10', fontSize: 'text-xs' },
  },
  '1536': {
    small: { rows: 32, cols: 48, wellWidth: 'w-1', wellHeight: 'h-1', fontSize: 'text-[4px]' },
    medium: { rows: 32, cols: 48, wellWidth: 'w-4', wellHeight: 'h-4', fontSize: 'text-[6px]' },
    large: { rows: 32, cols: 48, wellWidth: 'w-8', wellHeight: 'h-7', fontSize: 'text-xs' },
  },
};

function getRowLabel(rowIndex: number): string {
  return String.fromCharCode(65 + rowIndex); // A, B, C, ...
}

function getWellId(row: number, col: number, format: PlateFormat): string {
  return `${getRowLabel(row)}${col + 1}`;
}

export default function PlateViewer({
  format,
  wells,
  isDarkMode,
  size = 'medium',
  showLabels = true,
  showAxisLabels = true,
  onWellClick,
  className = '',
}: PlateViewerProps) {
  const dims = PLATE_DIMENSIONS[format][size];

  // Create a map for quick well lookup
  const wellMap = new Map<string, WellData>();
  wells.forEach(well => wellMap.set(well.id, well));

  // Get default well appearance
  const getDefaultWellColor = () => {
    return isDarkMode ? 'bg-slate-800/50' : 'bg-zinc-100';
  };

  const getDefaultBorderColor = () => {
    return isDarkMode ? '#475569' : '#d4d4d8';
  };

  return (
    <div className={`inline-block ${className}`}>
      <div className="overflow-x-auto">
        <div className="inline-block min-w-full">
          {/* Column headers */}
          {showAxisLabels && (
            <div className="flex">
              <div className={`flex-shrink-0 ${size === 'small' ? 'w-3' : 'w-10'}`}></div>
              {Array.from({ length: dims.cols }).map((_, col) => (
                <div
                  key={col}
                  className={`flex-shrink-0 ${dims.wellWidth} ${size === 'small' ? 'mr-0.5' : 'mr-1'} text-center ${dims.fontSize} ${
                    isDarkMode ? 'text-slate-400' : 'text-zinc-500'
                  } mb-1`}
                >
                  {col + 1}
                </div>
              ))}
            </div>
          )}

          {/* Plate grid */}
          {Array.from({ length: dims.rows }).map((_, row) => (
            <div key={row} className={`flex items-center ${size === 'small' ? 'mb-0.5' : 'mb-1'}`}>
              {/* Row label */}
              {showAxisLabels && (
                <div
                  className={`flex-shrink-0 ${size === 'small' ? 'w-3' : 'w-10'} ${dims.fontSize} ${
                    isDarkMode ? 'text-slate-400' : 'text-zinc-500'
                  } text-right pr-2`}
                >
                  {getRowLabel(row)}
                </div>
              )}

              {/* Wells */}
              {Array.from({ length: dims.cols }).map((_, col) => {
                const wellId = getWellId(row, col, format);
                const wellData = wellMap.get(wellId);
                const color = wellData?.color || getDefaultWellColor();
                const borderColor = wellData?.borderColor || getDefaultBorderColor();
                const borderWidth = wellData?.borderWidth || 2;
                const hasTooltip = wellData?.tooltip;

                return (
                  <div
                    key={wellId}
                    className={`flex-shrink-0 ${dims.wellWidth} ${dims.wellHeight} ${size === 'small' ? 'mr-0.5' : 'mr-1'} rounded border-${borderWidth} flex items-center justify-center transition-all group relative ${color} ${
                      onWellClick ? 'cursor-pointer hover:ring-2 hover:ring-violet-500' : ''
                    }`}
                    style={{ borderColor }}
                    onClick={() => onWellClick?.(wellId)}
                    title={hasTooltip ? undefined : wellId}
                  >
                    {/* Well label */}
                    {showLabels && wellData?.label && (
                      <span className={`${dims.fontSize} font-mono text-white opacity-60 group-hover:opacity-100`}>
                        {wellData.label}
                      </span>
                    )}

                    {/* Show well ID on hover for medium/large - Cell Thalamus style */}
                    {size !== 'small' && !wellData?.label && (
                      <span
                        className={`${dims.fontSize} font-mono text-white opacity-60 group-hover:opacity-100`}
                      >
                        {wellId}
                      </span>
                    )}

                    {/* Tooltip - Cell Thalamus style */}
                    {hasTooltip && size !== 'small' && (
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                        <div className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs whitespace-nowrap">
                          <div className="font-semibold text-white">{wellData.tooltip.title}</div>
                          {wellData.tooltip.lines.map((line, i) => (
                            <div key={i} className="text-slate-400">
                              {line}
                            </div>
                          ))}
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
    </div>
  );
}
