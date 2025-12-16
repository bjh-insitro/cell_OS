/**
 * S3 Watcher Control Component
 *
 * Controls the background S3 watcher for auto-syncing database from JupyterHub
 */

import React, { useState, useEffect } from 'react';

interface WatcherStatus {
  running: boolean;
  pid: string | null;
  message: string;
}

const S3WatcherControl: React.FC = () => {
  const [status, setStatus] = useState<WatcherStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/thalamus/watcher/status');
      if (!response.ok) throw new Error('Failed to fetch watcher status');
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching watcher status:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  useEffect(() => {
    fetchStatus();
    // Poll status every 10 seconds
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/thalamus/watcher/start', {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to start watcher');
      await fetchStatus();
    } catch (err) {
      console.error('Error starting watcher:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/thalamus/watcher/stop', {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to stop watcher');
      await fetchStatus();
    } catch (err) {
      console.error('Error stopping watcher:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (!status && !error) {
    return null; // Still loading initial status
  }

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between">
        {/* Status Info */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`
              w-3 h-3 rounded-full
              ${status?.running ? 'bg-green-500 animate-pulse' : 'bg-slate-600'}
            `} />
            <span className="text-sm font-semibold text-white">
              S3 Auto-Sync
            </span>
          </div>
          <div className="text-xs text-slate-400">
            {status?.running ? (
              <>
                Running <span className="text-slate-500">(PID: {status.pid})</span> • Checks S3 every 30s
              </>
            ) : (
              'Not running'
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {status?.running ? (
            <button
              onClick={handleStop}
              disabled={loading}
              className={`
                px-4 py-2 rounded-lg text-sm font-semibold transition-all
                ${loading
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-red-600/20 text-red-400 hover:bg-red-600/30 border border-red-600/50'
                }
              `}
            >
              {loading ? 'Stopping...' : 'Stop Watcher'}
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={loading}
              className={`
                px-4 py-2 rounded-lg text-sm font-semibold transition-all
                ${loading
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-green-600/20 text-green-400 hover:bg-green-600/30 border border-green-600/50'
                }
              `}
            >
              {loading ? 'Starting...' : 'Start Watcher'}
            </button>
          )}

          <button
            onClick={fetchStatus}
            disabled={loading}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-300 hover:bg-slate-700/50 transition-all"
            title="Refresh status"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Workflow Diagram */}
      <div className="mt-4 pt-4 border-t border-slate-700">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Automated Workflow
        </div>

        <div className="grid grid-cols-3 gap-4 items-center">
          {/* Step 1: JupyterHub */}
          <div className="flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center mb-2">
              <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
            <div className="text-xs font-semibold text-white mb-1">JupyterHub</div>
            <div className="text-xs text-slate-500">Runs simulation</div>
            <div className="text-xs text-blue-400 mt-1">Auto-uploads DB</div>
          </div>

          {/* Arrow 1 */}
          <div className="flex flex-col items-center">
            <svg className="w-full h-6 text-slate-600" viewBox="0 0 100 24" fill="none">
              <path d="M5 12 L95 12" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4"/>
              <path d="M90 8 L95 12 L90 16" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
            <div className="text-xs text-slate-500 mt-1">boto3</div>
          </div>

          {/* Step 2: S3 */}
          <div className="flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-lg bg-orange-500/10 border border-orange-500/30 flex items-center justify-center mb-2">
              <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
              </svg>
            </div>
            <div className="text-xs font-semibold text-white mb-1">AWS S3</div>
            <div className="text-xs text-slate-500">Cloud storage</div>
            <div className="text-xs text-orange-400 mt-1">s3://insitro-user/brig/</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 items-center mt-2">
          {/* Step 3: Mac */}
          <div className="col-start-3 flex flex-col items-center text-center">
            <div className={`
              w-12 h-12 rounded-lg flex items-center justify-center mb-2
              ${status?.running
                ? 'bg-green-500/10 border border-green-500/30'
                : 'bg-slate-700/30 border border-slate-600/30'
              }
            `}>
              <svg className={`w-6 h-6 ${status?.running ? 'text-green-400' : 'text-slate-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="text-xs font-semibold text-white mb-1">Your Mac</div>
            <div className="text-xs text-slate-500">Local dashboard</div>
            <div className={`text-xs mt-1 ${status?.running ? 'text-green-400' : 'text-slate-500'}`}>
              {status?.running ? '✓ Auto-downloads' : 'Watcher stopped'}
            </div>
          </div>

          {/* Arrow 2 (pointing left and down) */}
          <div className="col-start-2 flex flex-col items-center">
            <svg className="w-full h-6 text-slate-600" viewBox="0 0 100 24" fill="none">
              <path d="M95 12 L5 12" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4"/>
              <path d="M10 8 L5 12 L10 16" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
            <div className="text-xs text-slate-500 mt-1">watch script</div>
          </div>
        </div>

        {/* Timing Info */}
        <div className="mt-3 pt-3 border-t border-slate-700/50">
          <div className="text-xs text-slate-400">
            {status?.running ? (
              <>
                💡 <strong>Auto-sync active:</strong> Checks S3 every 30s, downloads new results automatically
              </>
            ) : (
              <>
                ℹ️ Start the watcher before running simulations to enable automatic sync
              </>
            )}
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 pt-3 border-t border-red-900/30">
          <div className="text-xs text-red-400">
            ⚠️ <strong>Error:</strong> {error}
          </div>
        </div>
      )}
    </div>
  );
};

export default S3WatcherControl;
