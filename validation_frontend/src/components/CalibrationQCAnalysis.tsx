import React, { useMemo } from 'react';
import { WellMeasurement } from './shared/PlateResultsViewer';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

interface CalibrationQCAnalysisProps {
  measurements: WellMeasurement[];
  isDarkMode: boolean;
}

interface TileMetrics {
  position: string;
  cv_dna: number;
  cv_er: number;
  cv_agp: number;
  cv_mito: number;
  cv_rna: number;
  n_wells: number;
}

interface AnchorMetrics {
  channel: string;
  dmso_mean: number;
  mild_mean: number;
  strong_mean: number;
  z_factor_mild: number;
  z_factor_strong: number;
  separation_ratio: number;
}

interface SpatialMetrics {
  row: string;
  col: number;
  value: number;
}

export default function CalibrationQCAnalysis({ measurements, isDarkMode }: CalibrationQCAnalysisProps) {

  // Calculate CV (coefficient of variation) for a set of values
  const calculateCV = (values: number[]): number => {
    if (values.length === 0) return 0;
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    if (mean === 0) return 0;
    const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
    const stdDev = Math.sqrt(variance);
    return (stdDev / mean) * 100;
  };

  // Calculate Z-factor: https://en.wikipedia.org/wiki/Z-factor
  // Z' = 1 - (3*(σp + σn)) / |μp - μn|
  // Z' > 0.5 is excellent, 0 < Z' < 0.5 is doable, Z' < 0 is not suitable
  const calculateZFactor = (positive: number[], negative: number[]): number => {
    if (positive.length === 0 || negative.length === 0) return -999;

    const meanPos = positive.reduce((a, b) => a + b, 0) / positive.length;
    const meanNeg = negative.reduce((a, b) => a + b, 0) / negative.length;

    const varPos = positive.reduce((sum, val) => sum + Math.pow(val - meanPos, 2), 0) / positive.length;
    const varNeg = negative.reduce((sum, val) => sum + Math.pow(val - meanNeg, 2), 0) / negative.length;

    const stdPos = Math.sqrt(varPos);
    const stdNeg = Math.sqrt(varNeg);

    const denominator = Math.abs(meanPos - meanNeg);
    if (denominator === 0) return -999;

    return 1 - (3 * (stdPos + stdNeg)) / denominator;
  };

  // 1. TILE CV ANALYSIS
  const tileMetrics = useMemo((): TileMetrics[] => {
    // Identify tile regions (2x2 replicates)
    // From the design: tiles at corners and edges
    const tileRegions = [
      { name: 'TL-corner', wells: ['B2', 'B3', 'C2', 'C3'] },
      { name: 'TR-corner', wells: ['B22', 'B23', 'C22', 'C23'] },
      { name: 'BL-corner', wells: ['O2', 'O3', 'P2', 'P3'] },
      { name: 'BR-corner', wells: ['O22', 'O23', 'P22', 'P23'] },
      { name: 'Mid-L', wells: ['G2', 'G3', 'H2', 'H3'] },
      { name: 'Mid-R', wells: ['G22', 'G23', 'H22', 'H23'] },
      { name: 'Mid2-L', wells: ['J2', 'J3', 'K2', 'K3'] },
      { name: 'Mid2-R', wells: ['J22', 'J23', 'K22', 'K23'] },
    ];

    return tileRegions.map(region => {
      const tileMeasurements = measurements.filter(m => region.wells.includes(m.wellId));

      if (tileMeasurements.length === 0) {
        return {
          position: region.name,
          cv_dna: 0,
          cv_er: 0,
          cv_agp: 0,
          cv_mito: 0,
          cv_rna: 0,
          n_wells: 0
        };
      }

      return {
        position: region.name,
        cv_dna: calculateCV(tileMeasurements.map(m => m.channels.dna)),
        cv_er: calculateCV(tileMeasurements.map(m => m.channels.er)),
        cv_agp: calculateCV(tileMeasurements.map(m => m.channels.agp)),
        cv_mito: calculateCV(tileMeasurements.map(m => m.channels.mito)),
        cv_rna: calculateCV(tileMeasurements.map(m => m.channels.rna)),
        n_wells: tileMeasurements.length
      };
    });
  }, [measurements]);

  // 2. ANCHOR Z-FACTOR ANALYSIS
  const anchorMetrics = useMemo((): AnchorMetrics[] => {
    const dmsoWells = measurements.filter(m => m.metadata.treatment?.includes('DMSO') || m.metadata.treatment?.includes('vehicle'));
    const mildWells = measurements.filter(m => m.metadata.treatment?.includes('MILD') || (m.metadata.dose === 1 && m.metadata.compound !== 'DMSO'));
    const strongWells = measurements.filter(m => m.metadata.treatment?.includes('STRONG') || (m.metadata.dose === 100 && m.metadata.compound !== 'DMSO'));

    const channels = ['dna', 'er', 'agp', 'mito', 'rna'] as const;

    return channels.map(channel => {
      const dmsoValues = dmsoWells.map(m => m.channels[channel]);
      const mildValues = mildWells.map(m => m.channels[channel]);
      const strongValues = strongWells.map(m => m.channels[channel]);

      const dmsoMean = dmsoValues.length > 0 ? dmsoValues.reduce((a, b) => a + b, 0) / dmsoValues.length : 0;
      const mildMean = mildValues.length > 0 ? mildValues.reduce((a, b) => a + b, 0) / mildValues.length : 0;
      const strongMean = strongValues.length > 0 ? strongValues.reduce((a, b) => a + b, 0) / strongValues.length : 0;

      const zFactorMild = calculateZFactor(mildValues, dmsoValues);
      const zFactorStrong = calculateZFactor(strongValues, dmsoValues);
      const separationRatio = dmsoMean !== 0 ? Math.abs(strongMean - dmsoMean) / dmsoMean : 0;

      return {
        channel: channel.toUpperCase(),
        dmso_mean: dmsoMean,
        mild_mean: mildMean,
        strong_mean: strongMean,
        z_factor_mild: zFactorMild,
        z_factor_strong: zFactorStrong,
        separation_ratio: separationRatio
      };
    });
  }, [measurements]);

  // 3. SPATIAL HEATMAP DATA (Edge effects)
  const spatialData = useMemo(() => {
    // Group by row and calculate mean DNA signal
    const rowMeans = new Map<string, number[]>();
    measurements.forEach(m => {
      if (!rowMeans.has(m.row)) rowMeans.set(m.row, []);
      rowMeans.get(m.row)!.push(m.channels.dna);
    });

    const rowAverages = Array.from(rowMeans.entries()).map(([row, values]) => ({
      row,
      value: values.reduce((a, b) => a + b, 0) / values.length
    }));

    // Group by column
    const colMeans = new Map<number, number[]>();
    measurements.forEach(m => {
      if (!colMeans.has(m.col)) colMeans.set(m.col, []);
      colMeans.get(m.col)!.push(m.channels.dna);
    });

    const colAverages = Array.from(colMeans.entries()).map(([col, values]) => ({
      col,
      value: values.reduce((a, b) => a + b, 0) / values.length
    }));

    return { rows: rowAverages, cols: colAverages };
  }, [measurements]);

  // 4. CHANNEL CORRELATION MATRIX
  const correlationMatrix = useMemo(() => {
    const channels = ['dna', 'er', 'agp', 'mito', 'rna'] as const;
    const matrix: number[][] = [];

    for (let i = 0; i < channels.length; i++) {
      matrix[i] = [];
      for (let j = 0; j < channels.length; j++) {
        const valuesI = measurements.map(m => m.channels[channels[i]]);
        const valuesJ = measurements.map(m => m.channels[channels[j]]);

        // Calculate Pearson correlation
        const meanI = valuesI.reduce((a, b) => a + b, 0) / valuesI.length;
        const meanJ = valuesJ.reduce((a, b) => a + b, 0) / valuesJ.length;

        let numerator = 0;
        let denomI = 0;
        let denomJ = 0;

        for (let k = 0; k < valuesI.length; k++) {
          const diffI = valuesI[k] - meanI;
          const diffJ = valuesJ[k] - meanJ;
          numerator += diffI * diffJ;
          denomI += diffI * diffI;
          denomJ += diffJ * diffJ;
        }

        const correlation = numerator / Math.sqrt(denomI * denomJ);
        matrix[i][j] = correlation;
      }
    }

    return { channels, matrix };
  }, [measurements]);

  // Helper to render Z-factor badge
  const renderZFactorBadge = (zFactor: number) => {
    if (zFactor < 0) {
      return (
        <span className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-red-900/30 text-red-400 border border-red-700">
          <XCircle className="h-3 w-3" />
          Poor ({zFactor.toFixed(2)})
        </span>
      );
    } else if (zFactor < 0.5) {
      return (
        <span className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-yellow-900/30 text-yellow-400 border border-yellow-700">
          <AlertTriangle className="h-3 w-3" />
          OK ({zFactor.toFixed(2)})
        </span>
      );
    } else {
      return (
        <span className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-green-900/30 text-green-400 border border-green-700">
          <CheckCircle className="h-3 w-3" />
          Excellent ({zFactor.toFixed(2)})
        </span>
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. TILE CV ANALYSIS */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          📊 Replicate Precision (Tile CV Analysis)
        </div>
        <div className={`text-sm mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Coefficient of variation (CV) for 2x2 replicate tiles. Lower CV = better reproducibility. Target: {'<'}10%.
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
                <th className={`text-left p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Position</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>DNA</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>ER</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>AGP</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Mito</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>RNA</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Wells</th>
              </tr>
            </thead>
            <tbody>
              {tileMetrics.map((tile, idx) => (
                <tr key={idx} className={`border-b ${isDarkMode ? 'border-slate-700/50' : 'border-zinc-100'}`}>
                  <td className={`p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>{tile.position}</td>
                  <td className={`p-2 text-right ${tile.cv_dna < 10 ? 'text-green-400' : tile.cv_dna < 20 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {tile.cv_dna.toFixed(1)}%
                  </td>
                  <td className={`p-2 text-right ${tile.cv_er < 10 ? 'text-green-400' : tile.cv_er < 20 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {tile.cv_er.toFixed(1)}%
                  </td>
                  <td className={`p-2 text-right ${tile.cv_agp < 10 ? 'text-green-400' : tile.cv_agp < 20 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {tile.cv_agp.toFixed(1)}%
                  </td>
                  <td className={`p-2 text-right ${tile.cv_mito < 10 ? 'text-green-400' : tile.cv_mito < 20 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {tile.cv_mito.toFixed(1)}%
                  </td>
                  <td className={`p-2 text-right ${tile.cv_rna < 10 ? 'text-green-400' : tile.cv_rna < 20 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {tile.cv_rna.toFixed(1)}%
                  </td>
                  <td className={`p-2 text-right ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {tile.n_wells}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. ANCHOR Z-FACTOR */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          🎯 Assay Quality (Z-Factor)
        </div>
        <div className={`text-sm mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Z-factor measures assay quality. Z' {'>'} 0.5 = excellent, 0-0.5 = acceptable, {'<'} 0 = poor.
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
                <th className={`text-left p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Channel</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>DMSO</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Mild</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Strong</th>
                <th className={`text-left p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Z' (Mild)</th>
                <th className={`text-left p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Z' (Strong)</th>
                <th className={`text-right p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>Separation</th>
              </tr>
            </thead>
            <tbody>
              {anchorMetrics.map((anchor, idx) => (
                <tr key={idx} className={`border-b ${isDarkMode ? 'border-slate-700/50' : 'border-zinc-100'}`}>
                  <td className={`p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'} font-semibold`}>
                    {anchor.channel}
                  </td>
                  <td className={`p-2 text-right ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {anchor.dmso_mean.toFixed(2)}
                  </td>
                  <td className={`p-2 text-right ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {anchor.mild_mean.toFixed(2)}
                  </td>
                  <td className={`p-2 text-right ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {anchor.strong_mean.toFixed(2)}
                  </td>
                  <td className="p-2">
                    {renderZFactorBadge(anchor.z_factor_mild)}
                  </td>
                  <td className="p-2">
                    {renderZFactorBadge(anchor.z_factor_strong)}
                  </td>
                  <td className={`p-2 text-right ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {(anchor.separation_ratio * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. SPATIAL EFFECTS */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          🗺️ Spatial Effects (DNA Channel)
        </div>
        <div className={`text-sm mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Mean signal by row and column. Look for edge effects or gradients.
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Row effects */}
          <div>
            <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              By Row
            </div>
            <div className="space-y-1">
              {spatialData.rows.map((row, idx) => {
                const maxVal = Math.max(...spatialData.rows.map(r => r.value));
                const widthPct = (row.value / maxVal) * 100;
                return (
                  <div key={idx} className="flex items-center gap-2">
                    <div className={`w-6 text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                      {row.row}
                    </div>
                    <div className="flex-1 h-6 bg-slate-700/30 rounded overflow-hidden">
                      <div
                        className="h-full bg-indigo-500"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className={`w-16 text-right text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                      {row.value.toFixed(2)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Column effects */}
          <div>
            <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              By Column
            </div>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {spatialData.cols.map((col, idx) => {
                const maxVal = Math.max(...spatialData.cols.map(c => c.value));
                const widthPct = (col.value / maxVal) * 100;
                return (
                  <div key={idx} className="flex items-center gap-2">
                    <div className={`w-6 text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                      {col.col}
                    </div>
                    <div className="flex-1 h-6 bg-slate-700/30 rounded overflow-hidden">
                      <div
                        className="h-full bg-indigo-500"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className={`w-16 text-right text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                      {col.value.toFixed(2)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 4. CHANNEL CORRELATION MATRIX */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          🔗 Channel Correlation Matrix
        </div>
        <div className={`text-sm mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Pearson correlation between channels. High correlation suggests redundancy or coupling.
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={`p-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}></th>
                {correlationMatrix.channels.map((ch, idx) => (
                  <th key={idx} className={`p-2 text-center ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    {ch.toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {correlationMatrix.channels.map((rowCh, i) => (
                <tr key={i}>
                  <td className={`p-2 font-semibold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    {rowCh.toUpperCase()}
                  </td>
                  {correlationMatrix.channels.map((colCh, j) => {
                    const corr = correlationMatrix.matrix[i][j];
                    const absCorr = Math.abs(corr);
                    // Color scale: high correlation = red, medium = yellow, low = green
                    const bgColor = absCorr > 0.8
                      ? 'bg-red-500'
                      : absCorr > 0.5
                        ? 'bg-yellow-500'
                        : 'bg-green-500';
                    const opacity = absCorr;

                    return (
                      <td key={j} className="p-0">
                        <div
                          className={`${bgColor} p-2 text-center text-white font-semibold`}
                          style={{ opacity }}
                        >
                          {corr.toFixed(2)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={`text-xs mt-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Color intensity = correlation strength. Red = high, Yellow = medium, Green = low.
        </div>
      </div>
    </div>
  );
}
