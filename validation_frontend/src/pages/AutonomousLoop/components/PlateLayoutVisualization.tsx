import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface WellData {
    wellId: string;
    compound: string;
    cellLine: string;
    doseUm: number;
    atpSignal: number;
    row: number;
    col: number;
}

interface PlateLayoutProps {
    data: WellData[];
    isDarkMode: boolean;
    animated?: boolean;
}

const PlateLayoutVisualization: React.FC<PlateLayoutProps> = ({ data, isDarkMode, animated = true }) => {
    const [visibleWells, setVisibleWells] = useState<Set<string>>(new Set());
    const [isAnimating, setIsAnimating] = useState(false);

    // Parse well ID to row/col
    const parseWellId = (wellId: string) => {
        const row = wellId.charCodeAt(0) - 65; // A=0, B=1, etc.
        const col = parseInt(wellId.slice(1)) - 1;
        return { row, col };
    };

    // Group data by compound and dose
    const processedData = data.map(d => ({
        ...d,
        ...parseWellId(d.wellId)
    }));

    // Get color based on ATP signal (viability)
    const getWellColor = (atpSignal: number) => {
        // Higher ATP = more viable = green, Lower ATP = less viable = red
        const viability = Math.max(0, Math.min(1, atpSignal));
        if (viability > 0.7) return isDarkMode ? 'bg-green-500' : 'bg-green-400';
        if (viability > 0.4) return isDarkMode ? 'bg-yellow-500' : 'bg-yellow-400';
        if (viability > 0.1) return isDarkMode ? 'bg-orange-500' : 'bg-orange-400';
        return isDarkMode ? 'bg-red-500' : 'bg-red-400';
    };

    // Animate wells appearing
    useEffect(() => {
        if (!animated) {
            setVisibleWells(new Set(data.map(d => d.wellId)));
            return;
        }

        setIsAnimating(true);
        setVisibleWells(new Set());

        // Sort by dose for logical animation order
        const sortedData = [...data].sort((a, b) => a.doseUm - b.doseUm);

        sortedData.forEach((well, idx) => {
            setTimeout(() => {
                setVisibleWells(prev => new Set([...prev, well.wellId]));
                if (idx === sortedData.length - 1) {
                    setIsAnimating(false);
                }
            }, idx * 150);
        });
    }, [data, animated]);

    // Create 8x12 grid (96-well plate)
    const rows = 8;
    const cols = 12;

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <div>
                    <h4 className={`text-sm font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                        Plate Layout (96-well)
                    </h4>
                    <p className={`text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                        {data.length} wells tested
                    </p>
                </div>
                {isAnimating && (
                    <span className={`text-xs ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`}>
                        Filling wells...
                    </span>
                )}
            </div>

            {/* Plate visualization */}
            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900' : 'bg-slate-100'}`}>
                {/* Column numbers */}
                <div className="flex mb-1">
                    <div className="w-6"></div>
                    {Array.from({ length: cols }).map((_, i) => (
                        <div key={i} className={`w-8 text-center text-[10px] ${isDarkMode ? 'text-slate-600' : 'text-zinc-400'}`}>
                            {i + 1}
                        </div>
                    ))}
                </div>

                {/* Plate grid */}
                {Array.from({ length: rows }).map((_, rowIdx) => (
                    <div key={rowIdx} className="flex items-center">
                        {/* Row letter */}
                        <div className={`w-6 text-center text-[10px] font-medium ${isDarkMode ? 'text-slate-600' : 'text-zinc-400'}`}>
                            {String.fromCharCode(65 + rowIdx)}
                        </div>

                        {/* Wells */}
                        {Array.from({ length: cols }).map((_, colIdx) => {
                            const wellData = processedData.find(d => d.row === rowIdx && d.col === colIdx);
                            const isVisible = wellData && visibleWells.has(wellData.wellId);

                            return (
                                <motion.div
                                    key={`${rowIdx}-${colIdx}`}
                                    initial={animated ? { scale: 0 } : { scale: 1 }}
                                    animate={{ scale: isVisible ? 1 : 1 }}
                                    transition={{ duration: 0.2 }}
                                    className="relative group"
                                >
                                    <div
                                        className={`
                                            w-7 h-7 m-0.5 rounded-full border transition-all
                                            ${wellData && isVisible
                                                ? `${getWellColor(wellData.atpSignal)} border-opacity-50 shadow-sm`
                                                : isDarkMode
                                                    ? 'bg-slate-800 border-slate-700'
                                                    : 'bg-white border-zinc-300'
                                            }
                                            ${wellData && isVisible ? 'cursor-pointer hover:ring-2 hover:ring-indigo-400' : ''}
                                        `}
                                    >
                                        {/* Tooltip on hover */}
                                        {wellData && isVisible && (
                                            <div className={`
                                                absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                                                px-3 py-2 rounded-lg shadow-xl text-xs z-50
                                                pointer-events-none opacity-0 group-hover:opacity-100
                                                transition-opacity duration-200 whitespace-nowrap
                                                ${isDarkMode ? 'bg-slate-800 border border-slate-600 text-slate-200' : 'bg-white border border-zinc-200 text-zinc-600'}
                                            `}>
                                                <div className="space-y-0.5">
                                                    <div className="font-semibold">{wellData.wellId}: {wellData.compound}</div>
                                                    <div>{wellData.cellLine}</div>
                                                    <div>Dose: {wellData.doseUm} µM</div>
                                                    <div>Viability: {(wellData.atpSignal * 100).toFixed(1)}%</div>
                                                </div>
                                                <div className={`absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 transform rotate-45 ${isDarkMode ? 'bg-slate-800 border-b border-r border-slate-600' : 'bg-white border-b border-r border-zinc-200'}`}></div>
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            );
                        })}
                    </div>
                ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                    <div className={`w-3 h-3 rounded-full ${isDarkMode ? 'bg-green-500' : 'bg-green-400'}`}></div>
                    <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>High Viability</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className={`w-3 h-3 rounded-full ${isDarkMode ? 'bg-yellow-500' : 'bg-yellow-400'}`}></div>
                    <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Medium</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className={`w-3 h-3 rounded-full ${isDarkMode ? 'bg-red-500' : 'bg-red-400'}`}></div>
                    <span className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>Low Viability</span>
                </div>
            </div>
        </div>
    );
};

export default PlateLayoutVisualization;
