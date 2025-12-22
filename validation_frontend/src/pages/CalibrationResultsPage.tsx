import React from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import PlateResultsViewer, { WellMeasurement } from '../components/shared/PlateResultsViewer';

export default function CalibrationResultsPage() {
  const { plateId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const { plateData, measurements } = location.state || {};

  if (!measurements) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
        <div className="container mx-auto max-w-6xl">
          <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6 text-center">
            <div className="text-red-300">No simulation data available</div>
            <button
              onClick={() => navigate('/calibration-plate')}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all"
            >
              Back to Calibration Plates
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
      <div className="container mx-auto max-w-6xl">
        {/* Back button */}
        <button
          onClick={() => navigate('/calibration-plate')}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Calibration Plates
        </button>

        {/* Results Viewer */}
        <PlateResultsViewer
          plateId={plateId || 'Unknown Plate'}
          format="384"
          measurements={measurements}
          isDarkMode={true}
          title="Cell Painting Simulation Results"
          showSentinelChart={true}
          onWellClick={(wellId) => {
            console.log('Clicked well:', wellId);
            // Could open detail modal showing:
            // - All 5 channel values
            // - Feature extraction results
            // - Images (if available)
            // - Treatment/dose/cell line metadata
          }}
        />

        {/* Info Box */}
        <div className="mt-6 bg-indigo-900/20 border border-indigo-700/50 rounded-xl p-6">
          <div className="text-sm font-semibold text-indigo-300 mb-2">
            About This Simulation
          </div>
          <div className="text-xs text-indigo-200 space-y-1">
            <div>• This is <strong>mock data</strong> generated to demonstrate the visualization</div>
            <div>• Real simulations will connect to Cell OS backend via API</div>
            <div>• Treatment effects are simulated (e.g., Nocodazole affects Mito/DNA, vehicle is baseline)</div>
            <div>• Spatial patterns show edge effects and gradients</div>
            <div>• Outliers are randomly injected to test detection</div>
            <div>• Click wells on the plate map to see individual measurements</div>
            <div>• Switch channels to see different stains (DNA, ER, AGP, Mito, RNA)</div>
            <div>• Sentinel chart shows well-by-well progression to identify artifacts</div>
          </div>
        </div>
      </div>
    </div>
  );
}
