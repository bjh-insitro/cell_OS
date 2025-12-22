import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react';
import PlateResultsViewer, { WellMeasurement } from '../components/shared/PlateResultsViewer';
import CalibrationQCAnalysis from '../components/CalibrationQCAnalysis';

export default function CalibrationResultsLoaderPage() {
  const { plateId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const seed = searchParams.get('seed') || '42';
  const runId = searchParams.get('run_id');

  const [measurements, setMeasurements] = useState<WellMeasurement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // Construct results path based on whether we have a run_id
  const resultsPath = runId
    ? `/demo_results/calibration_plates/${plateId}_run_${runId}_seed${seed}.json`
    : `/demo_results/calibration_plates/${plateId}_results_seed${seed}.json`;

  const loadResults = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(resultsPath);

      if (!response.ok) {
        throw new Error(`Results file not found: ${resultsPath}`);
      }

      const data = await response.json();

      // Convert flat_results to WellMeasurement format
      const converted: WellMeasurement[] = data.flat_results.map((r: any) => ({
        wellId: r.well_id,
        row: r.row,
        col: r.col,
        channels: {
          dna: r.morph_nucleus || 0,
          er: r.morph_er || 0,
          agp: r.morph_actin || 0,
          mito: r.morph_mito || 0,
          rna: r.morph_rna || 0
        },
        metadata: {
          cellLine: r.cell_line,
          treatment: r.treatment,
          dose: r.dose_uM,
          time_h: r.time_h,
          viability: r.viability,
          n_cells: r.n_cells,
          compound: r.compound,
          cell_density: r.cell_density,
          stain_scale: r.stain_scale,
          focus_offset_um: r.focus_offset_um,
          fixation_offset_min: r.fixation_offset_min
        }
      }));

      setMeasurements(converted);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResults();
  }, [plateId, seed]);

  const handleRefresh = () => {
    loadResults();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
        <div className="container mx-auto max-w-6xl">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-12 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto mb-4"></div>
            <div className="text-slate-300">Loading results...</div>
            <div className="text-sm text-slate-400 mt-2">
              {resultsPath}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
        <div className="container mx-auto max-w-6xl">
          <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-red-300 font-semibold mb-2">Results Not Found</div>
                <div className="text-red-200/80 text-sm mb-4">{error}</div>
                <div className="text-sm text-red-200/60 mb-4">
                  Expected location: <code className="bg-red-900/50 px-2 py-1 rounded">{resultsPath}</code>
                </div>
                <div className="space-y-2 text-sm text-red-200/80">
                  <div className="font-semibold">Possible reasons:</div>
                  <ul className="list-disc list-inside space-y-1 ml-2">
                    <li>Simulation hasn't completed yet (wait ~2-3 minutes)</li>
                    <li>Results haven't been committed to git yet</li>
                    <li>Results file is in a different location</li>
                    <li>Git hasn't been pulled to update the frontend</li>
                  </ul>
                </div>
                <div className="flex gap-2 mt-6">
                  <button
                    onClick={handleRefresh}
                    className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-all flex items-center gap-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Try Again
                  </button>
                  <button
                    onClick={() => navigate('/calibration-plate')}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-all"
                  >
                    Back to Plate Designs
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
      <div className="container mx-auto max-w-6xl">
        {/* Header with back button and refresh */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/calibration-plate')}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Plate Designs
          </button>
          <div className="flex items-center gap-3">
            <div className="text-xs text-slate-400">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </div>
            <button
              onClick={handleRefresh}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-all text-sm"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </div>

        {/* Results Viewer */}
        <PlateResultsViewer
          plateId={plateId || 'Unknown Plate'}
          format="384"
          measurements={measurements}
          isDarkMode={true}
          title={`${plateId} - Seed ${seed}`}
          showSentinelChart={true}
          onWellClick={(wellId) => {
            console.log('Clicked well:', wellId);
          }}
        />

        {/* Metadata */}
        <div className="mt-6 bg-indigo-900/20 border border-indigo-700/50 rounded-xl p-6">
          <div className="text-sm font-semibold text-indigo-300 mb-2">
            Simulation Details
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-indigo-200">
            <div>
              <div className="text-indigo-400 mb-1">Wells</div>
              <div className="font-semibold">{measurements.length}</div>
            </div>
            <div>
              <div className="text-indigo-400 mb-1">Seed</div>
              <div className="font-semibold">{seed}</div>
            </div>
            <div>
              <div className="text-indigo-400 mb-1">Cell Lines</div>
              <div className="font-semibold">
                {[...new Set(measurements.map(m => m.metadata.cell_line))].join(', ')}
              </div>
            </div>
            <div>
              <div className="text-indigo-400 mb-1">Avg Viability</div>
              <div className="font-semibold">
                {(measurements.reduce((sum, m) => sum + (m.metadata.viability || 0), 0) / measurements.length * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        {/* QC Analysis Section */}
        <div className="mt-6">
          <div className="mb-4">
            <h2 className="text-2xl font-bold text-white mb-2">
              Quality Control Analysis
            </h2>
            <p className="text-slate-400 text-sm">
              Statistical analysis and validation metrics for calibration plate quality
            </p>
          </div>
          <CalibrationQCAnalysis measurements={measurements} isDarkMode={true} />
        </div>
      </div>
    </div>
  );
}
