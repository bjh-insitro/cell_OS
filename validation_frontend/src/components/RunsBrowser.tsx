import React, { useState, useEffect } from 'react';
import { Clock, CheckCircle, XCircle, FlaskConical, Download } from 'lucide-react';

interface RunInfo {
  run_id: string;
  timestamp: string;
  plate_id: string;
  seed: number;
  n_wells: number;
  n_success: number;
  n_failed: number;
  cell_lines: string[];
  compounds: string[];
  file_path: string;
}

interface RunsManifest {
  runs: RunInfo[];
}

interface RunsBrowserProps {
  isDarkMode: boolean;
}

export default function RunsBrowser({ isDarkMode }: RunsBrowserProps) {
  const [manifest, setManifest] = useState<RunsManifest | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterPlateId, setFilterPlateId] = useState<string>('all');

  useEffect(() => {
    async function loadManifest() {
      try {
        const response = await fetch('/demo_results/calibration_plates/runs_manifest.json');
        if (!response.ok) {
          throw new Error('Manifest not found. Run a plate simulation first.');
        }
        const data = await response.json();
        setManifest(data);
        if (data.runs.length > 0) {
          setSelectedRun(data.runs[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load runs');
      } finally {
        setLoading(false);
      }
    }
    loadManifest();
  }, []);

  if (loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto mb-4"></div>
          <div>Loading runs...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-center ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
          <FlaskConical className="h-16 w-16 mx-auto mb-4 opacity-50" />
          <div className="text-lg font-bold mb-2">No Runs Yet</div>
          <div className="text-sm">{error}</div>
          <div className="mt-4 text-xs">
            Run a plate simulation on JupyterHub to see results here.
          </div>
        </div>
      </div>
    );
  }

  if (!manifest || manifest.runs.length === 0) {
    return (
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-center ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
          <FlaskConical className="h-16 w-16 mx-auto mb-4 opacity-50" />
          <div className="text-lg font-bold mb-2">No Runs Yet</div>
          <div className="text-sm">Run a plate simulation to see results here.</div>
        </div>
      </div>
    );
  }

  // Get unique plate IDs for filter
  const uniquePlateIds = Array.from(new Set(manifest.runs.map(r => r.plate_id)));

  // Filter runs
  const filteredRuns = filterPlateId === 'all'
    ? manifest.runs
    : manifest.runs.filter(r => r.plate_id === filterPlateId);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSuccessRate = (run: RunInfo) => {
    return ((run.n_success / run.n_wells) * 100).toFixed(1);
  };

  return (
    <div className="space-y-4">
      {/* Header with stats */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
              Simulation Runs
            </div>
            <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
              {manifest.runs.length} total runs across {uniquePlateIds.length} plate designs
            </div>
          </div>

          {/* Plate filter */}
          <select
            value={filterPlateId}
            onChange={(e) => setFilterPlateId(e.target.value)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              isDarkMode
                ? 'bg-slate-700 text-white border border-slate-600'
                : 'bg-white text-zinc-900 border border-zinc-300'
            }`}
          >
            <option value="all">All Plates</option>
            {uniquePlateIds.map(id => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Runs list */}
        <div className="lg:col-span-1 space-y-2">
          <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
            Runs ({filteredRuns.length})
          </div>
          <div className="space-y-2 max-h-[70vh] overflow-auto">
            {filteredRuns.map(run => (
              <button
                key={run.run_id}
                onClick={() => setSelectedRun(run)}
                className={`w-full text-left p-4 rounded-lg border transition-all ${
                  selectedRun?.run_id === run.run_id
                    ? isDarkMode
                      ? 'bg-indigo-900/30 border-indigo-600 shadow-lg'
                      : 'bg-indigo-50 border-indigo-400 shadow-lg'
                    : isDarkMode
                      ? 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                      : 'bg-white border-zinc-200 hover:border-zinc-300'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className={`text-sm font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {run.plate_id}
                  </div>
                  <div className={`text-xs px-2 py-0.5 rounded ${
                    run.n_failed === 0
                      ? isDarkMode ? 'bg-green-900/30 text-green-400' : 'bg-green-100 text-green-700'
                      : isDarkMode ? 'bg-yellow-900/30 text-yellow-400' : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {getSuccessRate(run)}%
                  </div>
                </div>

                <div className={`flex items-center gap-1 text-xs mb-2 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  <Clock className="h-3 w-3" />
                  {formatTimestamp(run.timestamp)}
                </div>

                <div className={`text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                  Run ID: {run.run_id}
                </div>
                <div className={`text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                  Seed: {run.seed}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Selected run details */}
        {selectedRun && (
          <div className="lg:col-span-2">
            <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {selectedRun.plate_id}
                  </div>
                  <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    Run ID: {selectedRun.run_id}
                  </div>
                  <div className={`text-xs ${isDarkMode ? 'text-slate-500' : 'text-zinc-500'}`}>
                    {formatTimestamp(selectedRun.timestamp)}
                  </div>
                </div>

                <a
                  href={`/${selectedRun.file_path}`}
                  download
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    isDarkMode
                      ? 'bg-slate-700 hover:bg-slate-600 text-white'
                      : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                  }`}
                >
                  <Download className="h-4 w-4" />
                  Download
                </a>
              </div>

              {/* Execution stats */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                  <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    Total Wells
                  </div>
                  <div className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {selectedRun.n_wells}
                  </div>
                </div>

                <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                  <div className={`flex items-center gap-1 text-xs ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
                    <CheckCircle className="h-3 w-3" />
                    Successful
                  </div>
                  <div className={`text-2xl font-bold ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
                    {selectedRun.n_success}
                  </div>
                </div>

                <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                  <div className={`flex items-center gap-1 text-xs ${
                    selectedRun.n_failed > 0
                      ? isDarkMode ? 'text-red-400' : 'text-red-600'
                      : isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                  }`}>
                    <XCircle className="h-3 w-3" />
                    Failed
                  </div>
                  <div className={`text-2xl font-bold ${
                    selectedRun.n_failed > 0
                      ? isDarkMode ? 'text-red-400' : 'text-red-600'
                      : isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                  }`}>
                    {selectedRun.n_failed}
                  </div>
                </div>
              </div>

              {/* Parameters */}
              <div className="space-y-4">
                <div>
                  <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    Parameters
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                      <span className="font-bold">Seed:</span> {selectedRun.seed}
                    </div>
                    <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                      <span className="font-bold">Success Rate:</span> {getSuccessRate(selectedRun)}%
                    </div>
                  </div>
                </div>

                <div>
                  <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    Cell Lines ({selectedRun.cell_lines.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedRun.cell_lines.map(line => (
                      <span
                        key={line}
                        className={`text-xs px-3 py-1 rounded-full ${
                          isDarkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {line}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                    Compounds ({selectedRun.compounds.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedRun.compounds.map(compound => (
                      <span
                        key={compound}
                        className={`text-xs px-3 py-1 rounded-full ${
                          isDarkMode ? 'bg-purple-900/30 text-purple-300' : 'bg-purple-100 text-purple-700'
                        }`}
                      >
                        {compound}
                      </span>
                    ))}
                  </div>
                </div>

                <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-indigo-900/20 border border-indigo-700/50' : 'bg-indigo-50 border border-indigo-200'}`}>
                  <div className={`text-sm ${isDarkMode ? 'text-indigo-300' : 'text-indigo-900'}`}>
                    <strong>File:</strong> {selectedRun.file_path.split('/').pop()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
