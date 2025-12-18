/**
 * Tab 1: Run Simulation on JupyterHub
 *
 * Instructions for running Cell Thalamus campaigns on JupyterHub
 */

import React from 'react';
import S3WatcherControl from './S3WatcherControl';

interface RunSimulationTabProps {
  onSimulationComplete: (designId: string) => void;
}

const RunSimulationTab: React.FC<RunSimulationTabProps> = () => {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Run on JupyterHub</h2>
        <p className="text-slate-400">
          Simulations now run directly on JupyterHub for maximum performance
        </p>
      </div>

      {/* S3 Watcher Control */}
      <S3WatcherControl />

      {/* Quick Start */}
      <div className="bg-gradient-to-r from-violet-900/30 to-blue-900/30 border border-violet-500/50 rounded-xl p-6">
        <div className="flex items-start gap-3">
          <div className="text-3xl">🚀</div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-violet-300 mb-2">Quick Start</h3>
            <ol className="text-sm text-slate-300 space-y-2">
              <li><strong>1.</strong> SSH to JupyterHub: <code className="text-violet-400">ssh jupyterhub.insitro.com</code></li>
              <li><strong>2.</strong> Navigate: <code className="text-violet-400">cd /mnt/shared/brig/cell_OS</code></li>
              <li><strong>3.</strong> Run with design catalog (RECOMMENDED): <code className="text-violet-400">python3 standalone_cell_thalamus.py --design-json data/designs/phase0_design_v3_mixed_celllines_checkerboard.json --seed 0</code></li>
              <li><strong>4.</strong> Alternative - Legacy mode: <code className="text-violet-400">python3 standalone_cell_thalamus.py --mode full --workers 64 --cell-lines A549 HepG2 iPSC_NGN2 iPSC_Microglia --seed 0</code></li>
              <li><strong>5.</strong> Sync to Mac: <code className="text-violet-400">./scripts/sync_aws_db.sh</code></li>
              <li><strong>6.</strong> View results in this dashboard!</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Available Modes */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Available Modes</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Demo Mode */}
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-violet-400">Demo Mode</div>
              <button
                onClick={() => copyToClipboard('python3 standalone_cell_thalamus.py --mode demo --workers 4')}
                className="text-xs text-slate-400 hover:text-violet-400"
              >
                📋 Copy
              </button>
            </div>
            <div className="text-xs text-slate-400 mb-3">Quick validation test</div>
            <div className="bg-slate-800 rounded p-2 mb-3">
              <code className="text-xs text-green-400">
                --mode demo --workers 4
              </code>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>• 8 wells</div>
              <div>• ~1 second</div>
              <div>• Tests system works</div>
            </div>
          </div>

          {/* Benchmark Mode */}
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-violet-400">Benchmark Mode</div>
              <button
                onClick={() => copyToClipboard('python3 standalone_cell_thalamus.py --mode benchmark --workers 64')}
                className="text-xs text-slate-400 hover:text-violet-400"
              >
                📋 Copy
              </button>
            </div>
            <div className="text-xs text-slate-400 mb-3">Medium-scale validation</div>
            <div className="bg-slate-800 rounded p-2 mb-3">
              <code className="text-xs text-green-400">
                --mode benchmark --workers 64
              </code>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>• 48 wells</div>
              <div>• ~1 second (64 workers)</div>
              <div>• Correlation testing</div>
            </div>
          </div>

          {/* Full Mode */}
          <div className="bg-slate-900/50 rounded-lg p-4 border border-violet-700">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-violet-400">Full Mode ⭐</div>
              <button
                onClick={() => copyToClipboard('python3 standalone_cell_thalamus.py --mode full --workers 64')}
                className="text-xs text-slate-400 hover:text-violet-400"
              >
                📋 Copy
              </button>
            </div>
            <div className="text-xs text-slate-400 mb-3">Production campaign</div>
            <div className="bg-slate-800 rounded p-2 mb-3">
              <code className="text-xs text-green-400">
                --mode full --workers 64
              </code>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>• 2,304 wells</div>
              <div>• ~0.3 seconds (7,500+ wells/sec)</div>
              <div>• Complete Phase 0</div>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Stats */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Performance Validated</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 text-center">
            <div className="text-2xl font-bold text-green-400">✅</div>
            <div className="text-xs text-slate-400 mt-2">Bit-Identical</div>
            <div className="text-xs text-slate-500 mt-1">Same seed = same results</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 text-center">
            <div className="text-2xl font-bold text-green-400">✅</div>
            <div className="text-xs text-slate-400 mt-2">Worker Invariant</div>
            <div className="text-xs text-slate-500 mt-1">1 worker = 64 workers</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 text-center">
            <div className="text-2xl font-bold text-green-400">✅</div>
            <div className="text-xs text-slate-400 mt-2">Observer Independent</div>
            <div className="text-xs text-slate-500 mt-1">Measurement doesn't perturb physics</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 text-center">
            <div className="text-2xl font-bold text-violet-400">7,575</div>
            <div className="text-xs text-slate-400 mt-2">Wells/Second</div>
            <div className="text-xs text-slate-500 mt-1">Full mode, 64 workers</div>
          </div>
        </div>
      </div>

      {/* Workflow */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Complete Workflow</h3>
        <div className="space-y-4">
          {/* Step 1 */}
          <div className="flex gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-500 flex items-center justify-center text-white font-bold">
              1
            </div>
            <div className="flex-1">
              <div className="font-semibold text-white mb-1">Run on JupyterHub</div>
              <div className="bg-slate-900 rounded-lg p-3 mb-2">
                <code className="text-sm text-green-400">python3 standalone_cell_thalamus.py --mode full --workers 64 --seed 0</code>
              </div>
              <div className="text-xs text-slate-400">
                Results auto-upload to: <code className="text-violet-400">s3://insitro-user/brig/cell_thalamus_results.db</code>
              </div>
            </div>
          </div>

          {/* Step 2 */}
          <div className="flex gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-500 flex items-center justify-center text-white font-bold">
              2
            </div>
            <div className="flex-1">
              <div className="font-semibold text-white mb-1">Sync to Mac</div>
              <div className="bg-slate-900 rounded-lg p-3 mb-2">
                <code className="text-sm text-green-400">./scripts/sync_aws_db.sh</code>
              </div>
              <div className="text-xs text-slate-400">
                Downloads to: <code className="text-violet-400">data/cell_thalamus_results.db</code>
              </div>
            </div>
          </div>

          {/* Step 3 */}
          <div className="flex gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-500 flex items-center justify-center text-white font-bold">
              3
            </div>
            <div className="flex-1">
              <div className="font-semibold text-white mb-1">Explore Results</div>
              <div className="text-sm text-slate-300 mb-2">
                Use the dashboard tabs to visualize and analyze results:
              </div>
              <div className="text-xs text-slate-400 space-y-1 ml-4">
                <div>• <strong>Dose-Response Explorer:</strong> Potency curves across cell lines</div>
                <div>• <strong>Plate Map Viewer:</strong> Spatial patterns and QC</div>
                <div>• <strong>Mechanism Recovery:</strong> PCA validation of stress axes</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Troubleshooting */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Troubleshooting</h3>
        <div className="space-y-3 text-sm">
          <div>
            <div className="font-semibold text-slate-300 mb-1">No designs showing in dropdown?</div>
            <div className="text-slate-400">
              Make sure you've synced the database: <code className="text-violet-400">./scripts/sync_aws_db.sh</code>
            </div>
          </div>
          <div>
            <div className="font-semibold text-slate-300 mb-1">Schema version error?</div>
            <div className="text-slate-400">
              Delete old database on JH: <code className="text-violet-400">rm cell_thalamus_results.db</code>
            </div>
          </div>
          <div>
            <div className="font-semibold text-slate-300 mb-1">Test determinism?</div>
            <div className="text-slate-400">
              Run validation suite: <code className="text-violet-400">./quick_jh_test.sh</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RunSimulationTab;
