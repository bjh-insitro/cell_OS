import React from 'react';

export interface LegendItem {
  label: string;
  color: string;
  borderColor?: string;
  borderWidth?: number;
  description?: string;
}

export interface PlateLegendProps {
  items: LegendItem[];
  isDarkMode: boolean;
  layout?: 'horizontal' | 'vertical';
  title?: string;
  className?: string;
}

export default function PlateLegend({
  items,
  isDarkMode,
  layout = 'horizontal',
  title,
  className = '',
}: PlateLegendProps) {
  const containerClass =
    layout === 'horizontal'
      ? 'flex flex-wrap gap-4 items-center justify-center'
      : 'space-y-2';

  return (
    <div className={className}>
      {title && (
        <div className={`font-bold text-sm mb-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
          {title}
        </div>
      )}
      <div className={containerClass}>
        {items.map((item, index) => (
          <div key={index} className="flex items-center gap-2">
            <div
              className={`w-4 h-4 rounded ${item.color}`}
              style={{
                border: item.borderWidth ? `${item.borderWidth}px solid ${item.borderColor}` : undefined,
              }}
            />
            <div>
              <span className="text-slate-300">
                {item.label}
              </span>
              {item.description && (
                <div className="text-xs text-slate-400">
                  {item.description}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
