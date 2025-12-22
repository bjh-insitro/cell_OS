import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, RefreshCw } from 'lucide-react';
import CalibrationPlateViewer from '../components/CalibrationPlateViewer';

const AVAILABLE_DESIGNS = [
  {
    id: 'microscope',
    name: 'CAL_384_MICROSCOPE_BEADS_DYES_v1',
    description: 'Microscope calibration - dyes, beads, no cells',
    version: 'microscope'
  },
  {
    id: 'v1',
    name: 'CAL_384_RULES_WORLD_v1',
    description: 'Simple calibration - anchors, tiles, vehicle',
    version: 'v1'
  },
  {
    id: 'v2',
    name: 'CAL_384_RULES_WORLD_v2',
    description: 'Advanced - interleaved cells, density gradient, probes',
    version: 'v2'
  },
  {
    id: 'lh',
    name: 'CAL_384_LH_ARTIFACTS_v1',
    description: 'Liquid handler artifacts - channel bias, carryover, mixing',
    version: 'lh'
  },
  {
    id: 'variance',
    name: 'CAL_VARIANCE_PARTITION_v1',
    description: 'Variance components - local vs global, quadrants, replicates',
    version: 'variance'
  },
  {
    id: 'wash',
    name: 'CAL_EL406_WASH_DAMAGE_v1',
    description: 'EL406 wash stress - aspiration shear, residual volume effects',
    version: 'wash'
  },
  {
    id: 'dynamic',
    name: 'CAL_DYNAMIC_RANGE_v1',
    description: 'Dynamic range - dose-response curves, saturation mapping',
    version: 'dynamic'
  }
];

export default function CalibrationPlatePage() {
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [selectedDesign, setSelectedDesign] = useState('v1');
  const [showSimulateModal, setShowSimulateModal] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [plateData, setPlateData] = useState<any>(null);

  const currentDesign = AVAILABLE_DESIGNS.find(d => d.id === selectedDesign) || AVAILABLE_DESIGNS[0];

  const generateJHCommand = (plateId: string, seed: number = 42, autoCommit: boolean = true) => {
    const platePath = `validation_frontend/public/plate_designs/${plateId}.json`;
    const baseCommand = `cd ~/repos/cell_OS && PYTHONPATH=. python3 src/cell_os/plate_executor_v2_parallel.py ${platePath} --seed ${seed}`;
    return autoCommit ? `${baseCommand} --auto-commit` : baseCommand;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2000);
  };

  const handleSimulate = (plateDataFromViewer: any) => {
    console.log('Starting simulation for plate:', plateDataFromViewer.plate.plate_id);
    setPlateData(plateDataFromViewer);
    setShowSimulateModal(true);
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDarkMode
      ? 'bg-gradient-to-b from-slate-900 to-slate-800'
      : 'bg-gradient-to-b from-zinc-50 to-white'
      }`}>
      {/* Header */}
      <div className={`backdrop-blur-sm border-b sticky top-0 z-50 transition-colors duration-300 ${isDarkMode
        ? 'bg-slate-800/80 border-slate-700'
        : 'bg-white/80 border-zinc-200'
        }`}>
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <button
                onClick={() => navigate('/documentary')}
                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${isDarkMode
                  ? 'text-slate-400 hover:text-white'
                  : 'text-zinc-500 hover:text-zinc-900'
                  }`}
              >
                ← Back to Documentary
              </button>
              <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'
                }`}>
                Calibration Plate Designs
              </h1>
              <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                }`}>
                Learn the measurement rules before exploring biology
              </p>
            </div>

            <div className="flex items-center gap-4">
              {/* Design Selector */}
              <div className="min-w-[300px]">
                <select
                  value={selectedDesign}
                  onChange={(e) => setSelectedDesign(e.target.value)}
                  className={`w-full px-4 py-2 rounded-lg border-2 transition-all ${isDarkMode
                    ? 'bg-slate-700 border-slate-600 text-white hover:border-indigo-500'
                    : 'bg-white border-zinc-300 text-zinc-900 hover:border-indigo-500'
                    }`}
                >
                  {AVAILABLE_DESIGNS.map(design => (
                    <option key={design.id} value={design.id}>
                      {design.name} - {design.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dark Mode Toggle */}
              <button
                onClick={() => setIsDarkMode(!isDarkMode)}
                className={`p-2 rounded-lg transition-all ${isDarkMode
                  ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                  : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                  }`}
                title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-6 max-w-6xl">
        <CalibrationPlateViewer
          isDarkMode={isDarkMode}
          designVersion={selectedDesign}
          onSimulate={handleSimulate}
        />
      </div>

      {/* Simulate on JH Modal */}
      {showSimulateModal && plateData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`max-w-3xl w-full rounded-lg shadow-xl ${isDarkMode ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
            {/* Modal Header */}
            <div className={`p-6 border-b ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    🚀 Run on JupyterHub
                  </div>
                  <div className={`text-sm mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                    {plateData.plate.plate_id} - Parallel Execution (31 workers)
                  </div>
                </div>
                <button
                  onClick={() => setShowSimulateModal(false)}
                  className={`text-2xl ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-zinc-400 hover:text-zinc-900'}`}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {/* Instructions */}
              <div>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  Instructions:
                </div>
                <ol className={`text-sm space-y-1 list-decimal list-inside ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  <li>Copy the command below</li>
                  <li>Open a terminal on JupyterHub</li>
                  <li>Paste and run the command</li>
                  <li>Results will auto-commit when complete (~2-3 minutes)</li>
                </ol>
              </div>

              {/* Command Box */}
              <div>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  Command:
                </div>
                <div className="relative">
                  <pre className={`p-4 rounded-lg text-sm font-mono overflow-x-auto ${isDarkMode ? 'bg-slate-900 text-green-400' : 'bg-zinc-100 text-zinc-900'}`}>
                    {generateJHCommand(plateData.plate.plate_id)}
                  </pre>
                  <button
                    onClick={() => copyToClipboard(generateJHCommand(plateData.plate.plate_id))}
                    className={`absolute top-2 right-2 px-3 py-1 rounded text-xs font-medium transition-all ${
                      copiedCommand
                        ? isDarkMode
                          ? 'bg-green-600 text-white'
                          : 'bg-green-500 text-white'
                        : isDarkMode
                          ? 'bg-slate-700 hover:bg-slate-600 text-white'
                          : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                    }`}
                  >
                    {copiedCommand ? '✓ Copied!' : 'Copy'}
                  </button>
                </div>
              </div>

              {/* Execution Details */}
              <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-900/50' : 'bg-zinc-50'}`}>
                <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                  What happens:
                </div>
                <ul className={`text-sm space-y-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  <li>✓ Executes 384 wells in parallel (31 workers)</li>
                  <li>✓ Per-well isolated simulation (correct time semantics)</li>
                  <li>✓ All provocations applied (stain/focus/fixation)</li>
                  <li>✓ Realistic background wells</li>
                  <li>✓ Auto-commits results to git when complete</li>
                  <li>✓ Expected duration: ~2-3 minutes</li>
                </ul>
              </div>

              {/* Advanced Options */}
              <details className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                <summary className="text-sm font-bold cursor-pointer">
                  Advanced options
                </summary>
                <div className="mt-2 space-y-2 text-sm">
                  <div>
                    <strong>Custom seed:</strong>
                    <pre className={`mt-1 p-2 rounded text-xs ${isDarkMode ? 'bg-slate-900' : 'bg-zinc-100'}`}>
                      {generateJHCommand(plateData.plate.plate_id, 123)}
                    </pre>
                  </div>
                  <div>
                    <strong>Without auto-commit:</strong>
                    <pre className={`mt-1 p-2 rounded text-xs ${isDarkMode ? 'bg-slate-900' : 'bg-zinc-100'}`}>
                      {generateJHCommand(plateData.plate.plate_id, 42, false)}
                    </pre>
                  </div>
                  <div>
                    <strong>Fewer workers (16):</strong>
                    <pre className={`mt-1 p-2 rounded text-xs ${isDarkMode ? 'bg-slate-900' : 'bg-zinc-100'}`}>
                      {generateJHCommand(plateData.plate.plate_id)} --workers 16
                    </pre>
                  </div>
                </div>
              </details>
            </div>

            {/* Modal Footer */}
            <div className={`p-6 border-t ${isDarkMode ? 'border-slate-700' : 'border-zinc-200'}`}>
              <div className="flex justify-between items-center">
                <button
                  onClick={() => {
                    navigate(`/calibration-results-loader/${plateData.plate.plate_id}?seed=42`);
                    setShowSimulateModal(false);
                  }}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    : 'bg-indigo-500 hover:bg-indigo-600 text-white'
                    }`}
                >
                  📊 View Results When Ready
                </button>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowSimulateModal(false)}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                      ? 'bg-slate-700 hover:bg-slate-600 text-white'
                      : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                      }`}
                  >
                    Close
                  </button>
                  <button
                    onClick={() => {
                      copyToClipboard(generateJHCommand(plateData.plate.plate_id));
                      setShowSimulateModal(false);
                    }}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                      ? 'bg-green-600 hover:bg-green-500 text-white'
                      : 'bg-green-500 hover:bg-green-600 text-white'
                      }`}
                  >
                    Copy & Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
