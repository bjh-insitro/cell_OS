import React, { useMemo } from 'react';
import {
    ComposedChart,
    Line,
    Area,
    XAxis,
    YAxis,
    ZAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Scatter,
    ErrorBar,
    ReferenceDot,
    ReferenceLine
} from 'recharts';

interface DataPoint {
    dose: number;
    response: number;
    error?: number;
    isNew?: boolean;
}

interface DoseResponseChartProps {
    ec50: { value: number; uncertainty: number };
    hillSlope: { value: number; uncertainty: number };
    dataPoints: DataPoint[];
    isDarkMode: boolean;
    showConfidenceInterval?: boolean;
    highlightNewData?: boolean;
    projectedDoses?: number[];
}

// Hill equation: min + (max - min) / (1 + (x / EC50)^-Slope)
// Simplified for normalized data (0-100%): 100 / (1 + (x / EC50)^Slope) (assuming inhibitory)
// Note: Standard Hill usually has slope > 0 for inhibition if using IC50 logic
const calculateHill = (dose: number, ec50: number, slope: number) => {
    return 100 / (1 + Math.pow(dose / ec50, slope));
};

const DoseResponseChart: React.FC<DoseResponseChartProps> = ({
    ec50,
    hillSlope,
    dataPoints,
    isDarkMode,
    showConfidenceInterval = true,
    highlightNewData = false,
    projectedDoses = []
}) => {
    // Generate curve data
    const curveData = useMemo(() => {
        console.log('DoseResponseChart ec50:', ec50, 'hillSlope:', hillSlope);
        const data = [];
        // Log scale points for smooth curve
        for (let i = 0; i <= 100; i++) {
            const dose = Math.exp(Math.log(0.1) + (i / 100) * (Math.log(100) - Math.log(0.1)));

            const response = calculateHill(dose, ec50.value, hillSlope.value);

            let lower = 0;
            let upper = 0;

            if (showConfidenceInterval) {
                // Approximate confidence interval simulation
                // Wider near EC50, scaled by uncertainty parameter
                const distFromEc50 = Math.abs(Math.log10(dose) - Math.log10(ec50.value));
                const uncertaintyFactor = ec50.uncertainty * 0.5 * Math.exp(-distFromEc50);
                // Simple heuristic for visualization

                lower = Math.max(0, response - uncertaintyFactor * 20); // Scale factor for visual
                upper = Math.min(120, response + uncertaintyFactor * 20);
            }

            data.push({
                dose,
                response,
                range: [lower, upper]
            });
        }
        return data;
    }, [ec50, hillSlope, showConfidenceInterval]);

    // Transform scatter data for Recharts
    const scatterData = useMemo(() => {
        console.log('DoseResponseChart dataPoints:', dataPoints);
        const transformed = dataPoints.map((p, i) => ({
            x: p.dose,
            y: p.response,
            errorY: p.error,
            isNew: p.isNew,
            index: 1  // Constant size for all points
        }));
        console.log('Transformed scatterData:', transformed);
        return transformed;
    }, [dataPoints]);

    const projectedData = useMemo(() => {
        return projectedDoses.map(d => ({
            x: d,
            y: calculateHill(d, ec50.value, hillSlope.value) // Place on curve
        }));
    }, [projectedDoses, ec50, hillSlope]);

    return (
        <div style={{ width: '100%', height: '300px', minHeight: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                    data={curveData}
                    margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                >
                    <CartesianGrid
                        strokeDasharray="3 3"
                        stroke={isDarkMode ? '#334155' : '#e2e8f0'}
                        vertical={false}
                    />
                    <XAxis
                        dataKey="dose"
                        type="number"
                        scale="log"
                        domain={[0.1, 100]}
                        ticks={[0.1, 1, 10, 100]}
                        allowDataOverflow={false}
                        stroke={isDarkMode ? '#94a3b8' : '#64748b'}
                        tickFormatter={(val) => {
                            if (val >= 1000) return `${val / 1000}mM`;
                            if (val < 0.1) return `${val}µM`;
                            return `${val}µM`;
                        }}
                        label={{
                            value: 'Concentration (µM)',
                            position: 'bottom',
                            offset: 0,
                            fill: isDarkMode ? '#94a3b8' : '#64748b'
                        }}
                    />
                    <YAxis
                        domain={[0, 120]}
                        stroke={isDarkMode ? '#94a3b8' : '#64748b'}
                        label={{
                            value: 'Viability (%)',
                            angle: -90,
                            position: 'insideLeft',
                            fill: isDarkMode ? '#94a3b8' : '#64748b'
                        }}
                    />
                    <Tooltip
                        content={({ active, payload }) => {
                            if (active && payload && payload.length) {
                                const data = payload[0].payload;
                                return (
                                    <div className={`p-2 rounded border text-xs ${isDarkMode ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-zinc-200 text-zinc-900'
                                        }`}>
                                        {data.dose ? (
                                            // Curve tooltip
                                            <>
                                                <div>Dose: {data.dose.toFixed(1)} µM</div>
                                                <div>Model: {data.response.toFixed(1)}%</div>
                                            </>
                                        ) : (
                                            // Scatter tooltip (x/y from scatter)
                                            <>
                                                <div>Dose: {data.x} µM</div>
                                                <div>Measured: {data.y}%</div>
                                            </>
                                        )}
                                    </div>
                                );
                            }
                            return null;
                        }}
                    />

                    {/* Uncertainty Band */}
                    {showConfidenceInterval && (
                        <Area
                            data={curveData}
                            dataKey="range"
                            stroke="none"
                            fill={isDarkMode ? '#ef4444' : '#fca5a5'}
                            fillOpacity={0.15}
                        />
                    )}

                    {/* Model Curve */}
                    <Line
                        data={curveData}
                        dataKey="response"
                        stroke={isDarkMode ? '#8b5cf6' : '#7c3aed'}
                        strokeWidth={2}
                        dot={false}
                        activeDot={false}
                    />

                    {/* Existing Data Points */}
                    {dataPoints.filter(d => !d.isNew).map((point, i) => (
                        <React.Fragment key={`point-${i}`}>
                            {/* Error bars rendered as reference areas */}
                            <ReferenceLine
                                segment={[
                                    { x: point.dose, y: point.response - (point.error || 0) },
                                    { x: point.dose, y: point.response + (point.error || 0) }
                                ]}
                                stroke={isDarkMode ? '#60a5fa' : '#3b82f6'}
                                strokeWidth={2}
                                isFront={false}
                            />
                            <ReferenceDot
                                x={point.dose}
                                y={point.response}
                                r={6}
                                fill={isDarkMode ? '#60a5fa' : '#3b82f6'}
                                stroke={isDarkMode ? '#1e40af' : '#2563eb'}
                                strokeWidth={2}
                                isFront
                            />
                        </React.Fragment>
                    ))}

                    {/* New Data Points (highlighted) */}
                    <Scatter
                        data={scatterData.filter(d => d.isNew)}
                        fill={isDarkMode ? '#4ade80' : '#16a34a'}
                        shape="star" // Just distinct shape or color
                    >
                        <ErrorBar dataKey="errorY" width={4} strokeWidth={2} stroke={isDarkMode ? '#4ade80' : '#16a34a'} direction="y" />
                    </Scatter>

                    {/* Proposed Doses (on axis or curve) */}
                    {projectedDoses.length > 0 && (
                        <Scatter
                            data={projectedData}
                            fill="transparent"
                            stroke={isDarkMode ? '#facc15' : '#eab308'}
                            strokeWidth={2}
                            shape={(props: any) => {
                                const { cx, cy } = props;
                                return (
                                    <g>
                                        <line x1={cx} y1={cy - 5} x2={cx} y2={cy + 5} stroke={props.stroke} strokeWidth={2} />
                                        <line x1={cx - 5} y1={cy} x2={cx + 5} y2={cy} stroke={props.stroke} strokeWidth={2} />
                                    </g>
                                );
                            }}
                        />
                    )}

                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
};

export default DoseResponseChart;
