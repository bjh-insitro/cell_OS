/**
 * Dynamic PCA Visualization for Mechanism Recovery
 * Three-panel scatter plot showing separation across dose ranges
 */

import React from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';

interface PCAData {
  separation_ratio: number;
  centroid_distance: number;
  n_wells: number;
  pc_scores: number[][];
  metadata: Array<{ stress_axis: string }>;
}

interface Props {
  allDoses: PCAData;
  midDose: PCAData;
  highDose: PCAData;
}

const STRESS_COLORS: Record<string, string> = {
  er_stress: '#ef4444',      // Red
  mitochondrial: '#3b82f6',  // Blue
  oxidative: '#f97316',      // Orange
  proteasome: '#a855f7',     // Purple
  dna_damage: '#22c55e',     // Green
  microtubule: '#f59e0b',    // Amber
};

const transformPCAData = (pcaData: PCAData) => {
  if (!pcaData.pc_scores || pcaData.pc_scores.length === 0) return { points: [], centroids: [] };

  const points = pcaData.pc_scores.map((scores, idx) => ({
    pc1: scores[0],
    pc2: scores[1],
    stress_axis: pcaData.metadata[idx].stress_axis,
    color: STRESS_COLORS[pcaData.metadata[idx].stress_axis] || '#9ca3af'
  }));

  // Compute centroids for each stress axis
  const centroidMap: Record<string, { pc1: number[], pc2: number[] }> = {};
  points.forEach(point => {
    if (!centroidMap[point.stress_axis]) {
      centroidMap[point.stress_axis] = { pc1: [], pc2: [] };
    }
    centroidMap[point.stress_axis].pc1.push(point.pc1);
    centroidMap[point.stress_axis].pc2.push(point.pc2);
  });

  const centroids = Object.entries(centroidMap).map(([stress_axis, coords]) => ({
    pc1: coords.pc1.reduce((a, b) => a + b, 0) / coords.pc1.length,
    pc2: coords.pc2.reduce((a, b) => a + b, 0) / coords.pc2.length,
    stress_axis,
    color: STRESS_COLORS[stress_axis] || '#9ca3af'
  }));

  return { points, centroids };
};

// Custom X-shape for centroids (matching matplotlib style)
const renderCentroidShape = (props: any) => {
  const { cx, cy, fill } = props;
  const size = 5; // Tiny X marker size

  return (
    <g>
      {/* Black outline strokes (ULTRA thick border) */}
      <line
        x1={cx - size}
        y1={cy - size}
        x2={cx + size}
        y2={cy + size}
        stroke="#000"
        strokeWidth={12}
        strokeLinecap="round"
      />
      <line
        x1={cx - size}
        y1={cy + size}
        x2={cx + size}
        y2={cy - size}
        stroke="#000"
        strokeWidth={12}
        strokeLinecap="round"
      />
      {/* Colored center strokes (extra thick fill) */}
      <line
        x1={cx - size}
        y1={cy - size}
        x2={cx + size}
        y2={cy + size}
        stroke={fill}
        strokeWidth={6}
        strokeLinecap="round"
      />
      <line
        x1={cx - size}
        y1={cy + size}
        x2={cx + size}
        y2={cy - size}
        stroke={fill}
        strokeWidth={6}
        strokeLinecap="round"
      />
    </g>
  );
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  const isCentroid = payload[0].dataKey === 'pc2' && payload[0].value === data.pc2 &&
                     payload.length === 1 && data.stress_axis;

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl">
      <p className="text-sm font-semibold text-white mb-1">
        {data.stress_axis.replace('_', ' ').toUpperCase()}
        {isCentroid && <span className="text-xs text-violet-400 ml-2">✕ CENTROID</span>}
      </p>
      <p className="text-xs text-slate-300">
        PC1: {data.pc1.toFixed(2)}
      </p>
      <p className="text-xs text-slate-300">
        PC2: {data.pc2.toFixed(2)}
      </p>
    </div>
  );
};

const MechanismRecoveryPCAViz: React.FC<Props> = ({ allDoses, midDose, highDose }) => {
  const allDosesData = transformPCAData(allDoses);
  const midDoseData = transformPCAData(midDose);
  const highDoseData = transformPCAData(highDose);

  const renderPanel = (
    data: ReturnType<typeof transformPCAData>,
    title: string,
    subtitle: string,
    separationRatio: number
  ) => (
    <div className="flex-1">
      <div className="text-center mb-3">
        <h4 className="text-md font-bold text-white">{title}</h4>
        <p className="text-xs text-slate-400">{subtitle}</p>
        <p className="text-sm font-semibold text-violet-400 mt-1">
          Separation: {separationRatio.toFixed(3)}
        </p>
      </div>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 10, bottom: 40, left: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            type="number"
            dataKey="pc1"
            name="PC1"
            stroke="#94a3b8"
            label={{ value: 'PC1', position: 'bottom', fill: '#94a3b8', fontSize: 12 }}
          />
          <YAxis
            type="number"
            dataKey="pc2"
            name="PC2"
            stroke="#94a3b8"
            label={{ value: 'PC2', angle: -90, position: 'left', fill: '#94a3b8', fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Z-axis to control point size - minimum size */}
          <ZAxis range={[1, 1]} />

          {/* Data points - tiny dots */}
          <Scatter
            data={data.points}
            fill="#8884d8"
            isAnimationActive={false}
          >
            {data.points.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.color}
                opacity={0.5}
              />
            ))}
          </Scatter>

          {/* Centroids with X markers */}
          <Scatter
            data={data.centroids}
            fill="#000000"
            shape={renderCentroidShape}
            isAnimationActive={false}
          >
            {data.centroids.map((entry, index) => (
              <Cell
                key={`centroid-${index}`}
                fill={entry.color}
                stroke="#000000"
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );

  return (
    <div className="bg-slate-800/30 border border-slate-700 rounded-lg p-6">
      <h3 className="text-lg font-bold text-white mb-4">PCA Visualization</h3>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4 justify-center">
        {Object.entries(STRESS_COLORS).map(([axis, color]) => (
          <div key={axis} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: color, opacity: 0.6 }}
            />
            <span className="text-xs text-slate-300">
              {axis.replace('_', ' ')}
            </span>
          </div>
        ))}
      </div>

      {/* Three panels */}
      <div className="flex gap-4">
        {renderPanel(
          allDosesData,
          'All Doses Mixed',
          `n=${allDoses.n_wells}`,
          allDoses.separation_ratio
        )}
        {renderPanel(
          midDoseData,
          'Mid-Dose 12h',
          `n=${midDose.n_wells}`,
          midDose.separation_ratio
        )}
        {renderPanel(
          highDoseData,
          'High-Dose 48h',
          `n=${highDose.n_wells}`,
          highDose.separation_ratio
        )}
      </div>

      <p className="text-slate-400 text-sm mt-4 text-center">
        Three-panel PCA comparison showing stress class separability across dose ranges.
        Left: classes collapse when mixing all doses. Middle: clean separation at mid-dose 12h.
        Right: partial separation at high-dose 48h.
      </p>
    </div>
  );
};

export default MechanismRecoveryPCAViz;
