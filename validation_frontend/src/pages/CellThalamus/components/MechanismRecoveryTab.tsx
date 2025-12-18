/**
 * Mechanism Recovery Tab - Shows stress class separability analysis
 *
 * Visualizes the three-panel PCA comparison showing where mechanistic
 * information lives in dose/time space:
 * - All doses mixed: collapse (death signature dominates)
 * - Mid-dose 12h: separation (adaptive responses visible)
 * - High-dose 48h: partial separation (differential vulnerability)
 */

import React, { useState, useEffect } from 'react';
import { getCellThalamusService } from '../../../services/CellThalamusService';
import MechanismRecoveryPCAViz from './MechanismRecoveryPCAViz';

interface MechanismRecoveryTabProps {
  selectedDesignId: string | null;
  onDesignChange: (designId: string | null) => void;
}

interface PCAData {
  separation_ratio: number;
  centroid_distance: number;
  n_wells: number;
  pc_scores: number[][];
  metadata: Array<{ stress_axis: string }>;
}

interface SeparationStats {
  all_doses: PCAData;
  mid_dose: PCAData;
  high_dose: PCAData;
  improvement_factor: number;
}

const MechanismRecoveryTab: React.FC<MechanismRecoveryTabProps> = ({
  selectedDesignId,
  onDesignChange,
}) => {
  const [designs, setDesigns] = useState<string[]>([]);
  const [stats, setStats] = useState<SeparationStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available designs
  useEffect(() => {
    const loadDesigns = async () => {
      try {
        const service = getCellThalamusService();
        const designList = await service.getAvailableDesigns();
        setDesigns(designList);

        if (!selectedDesignId && designList.length > 0) {
          onDesignChange(designList[0]);
        }
      } catch (err) {
        console.error('Error loading designs:', err);
      }
    };

    loadDesigns();
  }, []);

  // Load mechanism recovery stats for selected design
  useEffect(() => {
    if (!selectedDesignId) return;

    const loadStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const service = getCellThalamusService();
        const data = await service.getMechanismRecoveryStats(selectedDesignId);
        setStats(data);
      } catch (err) {
        console.error('Error loading mechanism recovery stats:', err);
        setError('Failed to load mechanism recovery analysis. The analysis may not be available for this design.');
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, [selectedDesignId]);

  const renderSeparationCard = (
    title: string,
    subtitle: string,
    ratio: number,
    distance: number,
    nWells: number,
    interpretation: string,
    bgColor: string
  ) => (
    <div className={`${bgColor} rounded-lg p-6 border border-slate-700`}>
      <h3 className="text-lg font-bold text-white mb-1">{title}</h3>
      <p className="text-sm text-slate-400 mb-4">{subtitle}</p>

      <div className="space-y-3">
        <div>
          <div className="text-xs text-slate-400 mb-1">Separation Ratio</div>
          <div className="text-3xl font-bold text-white">{ratio.toFixed(3)}</div>
          <div className="text-xs text-slate-400 mt-1">between / within variance</div>
        </div>

        <div>
          <div className="text-xs text-slate-400 mb-1">Centroid Distance</div>
          <div className="text-xl font-semibold text-white">{distance.toFixed(2)}</div>
          <div className="text-xs text-slate-400 mt-1">avg pairwise in PC space</div>
        </div>

        <div>
          <div className="text-xs text-slate-400 mb-1">Wells Analyzed</div>
          <div className="text-lg font-medium text-white">{nWells}</div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-slate-600">
        <p className="text-sm text-slate-300">{interpretation}</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Mechanism Recovery Analysis</h2>
          <p className="text-slate-400 mt-1">
            Where does mechanistic information live in dose/time space?
          </p>
        </div>

        {/* Design Selector */}
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-400">Design:</label>
          <select
            value={selectedDesignId || ''}
            onChange={(e) => onDesignChange(e.target.value || null)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {designs.map((design) => (
              <option key={design} value={design}>
                {design.substring(0, 8)}...
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Key Insight Panel */}
      <div className="bg-gradient-to-r from-violet-900/30 to-blue-900/30 border border-violet-700/50 rounded-lg p-6">
        <h3 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <span>🎯</span>
          <span>Key Insight</span>
        </h3>
        <p className="text-slate-200 leading-relaxed">
          Mechanistic information doesn't disappear at high doses—it <strong>moves</strong>.
          Death signatures dominate late/high-stress conditions, but adaptive stress responses
          are cleanly separable at mid-doses. This means mechanism is visible <strong>before catastrophe</strong>,
          not during.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-slate-400">Loading analysis...</div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6">
          <h3 className="text-red-400 font-semibold mb-2">Analysis Unavailable</h3>
          <p className="text-slate-300 text-sm">{error}</p>
          <p className="text-slate-400 text-xs mt-3">
            This analysis requires running the mechanism recovery script on the backend.
            See <code className="bg-slate-800 px-2 py-1 rounded">probe_mechanism_recovery.py</code> for details.
          </p>
        </div>
      )}

      {!loading && !error && stats && (
        <>
          {/* Improvement Factor Highlight */}
          <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-emerald-400 font-bold text-lg mb-1">
                  {stats.improvement_factor.toFixed(1)}× Better Separation
                </h3>
                <p className="text-slate-300 text-sm">
                  Mid-dose adaptive responses vs all-doses mixed
                </p>
              </div>
              <div className="text-5xl">📊</div>
            </div>
          </div>

          {/* Three Separation Conditions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {renderSeparationCard(
              'All Doses Mixed',
              'Vehicle, low, mid, high × 12h, 48h',
              stats.all_doses.separation_ratio,
              stats.all_doses.centroid_distance,
              stats.all_doses.n_wells,
              'Classes collapse into overlapping cloud. Death signatures dominate and erase class structure.',
              'bg-slate-800/50'
            )}

            {renderSeparationCard(
              'Mid-Dose 12h',
              '0.5-2× IC50 at early timepoint',
              stats.mid_dose.separation_ratio,
              stats.mid_dose.centroid_distance,
              stats.mid_dose.n_wells,
              'Classes cleanly separate. Adaptive stress responses visible before commitment. This is where information lives.',
              'bg-emerald-900/20'
            )}

            {renderSeparationCard(
              'High-Dose 48h',
              '5-10× IC50 at late timepoint',
              stats.high_dose.separation_ratio,
              stats.high_dose.centroid_distance,
              stats.high_dose.n_wells,
              'Partial separation. Universal death signature compresses space, but differential vulnerability still encoded.',
              'bg-orange-900/20'
            )}
          </div>

          {/* Interpretation Guide */}
          <div className="bg-slate-800/30 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-bold text-white mb-4">Interpretation Guide</h3>

            <div className="space-y-4">
              <div>
                <h4 className="text-violet-400 font-semibold mb-2">What is Separation Ratio?</h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Ratio of between-class variance to within-class variance in PCA space.
                  Values &gt;1 mean classes are more separated than scattered.
                  Values &lt;1 mean within-class noise dominates signal.
                </p>
              </div>

              <div>
                <h4 className="text-violet-400 font-semibold mb-2">Why Does All-Doses Fail?</h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  At extreme toxicity (10×IC50, 48h), all stress pathways converge to common
                  death machinery: membrane rupture, organellar collapse, chromatin condensation.
                  This universal "dead cell" morphology washes out stress-specific signatures when
                  mixed with adaptive responses at lower doses.
                </p>
              </div>

              <div>
                <h4 className="text-violet-400 font-semibold mb-2">Design Implications</h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  For autonomous loop optimization, prioritize <strong>mid-dose (0.5-2×IC50)
                  at early timepoints (12h)</strong> for mechanistic discrimination. Use late
                  timepoints (48h) to validate attrition kinetics (cumulative vs early commitment),
                  not to discover stress class.
                </p>
              </div>
            </div>
          </div>

          {/* PCA Visualization */}
          <MechanismRecoveryPCAViz
            allDoses={stats.all_doses}
            midDose={stats.mid_dose}
            highDose={stats.high_dose}
          />
        </>
      )}
    </div>
  );
};

export default MechanismRecoveryTab;
