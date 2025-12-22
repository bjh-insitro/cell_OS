import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface PlateDesign {
  id: string;
  name: string;
  version: string;
  status: 'proposed' | 'planned' | 'executed' | 'archived';
  intent: string;
  wells_total: number;
  wells_used: number;
  timepoint_hours: number;
  cell_lines: number;
  treatments: string[];
  design_goals: string[];
  cost_estimate?: number;
  thumbnail_color: string;
}

const PLATE_DESIGNS: PlateDesign[] = [
  {
    id: 'cal_384_rules_world_v2',
    name: 'CAL_384_RULES_WORLD_v2',
    version: '2.0',
    status: 'proposed',
    intent: 'Learn measurement rules: plate physics, pipeline behavior, noise floor, feature coupling, failure modes',
    wells_total: 384,
    wells_used: 384,
    timepoint_hours: 48,
    cell_lines: 2,
    treatments: ['Interleaved HepG2/A549', 'Density gradient', 'Stain probes', 'Focus probes', 'Timing probes', 'Anchors (Nocodazole, Thapsigargin)', 'Contrastive tiles'],
    design_goals: [
      'Break cell line/spatial confounds with interleaved rows',
      'Expose density-driven confounds (3-level gradient)',
      'Measure staining sensitivity (0.9x vs 1.1x scale)',
      'Detect fixation timing jitter effects',
      'Stress-test focus drift robustness',
      'Establish orthogonal anchor phenotypes',
      'Measure local repeatability with contrastive tiles',
      'Background controls (no-cell wells) for baseline'
    ],
    cost_estimate: 1950,
    thumbnail_color: 'from-indigo-600 to-indigo-700'
  },
  {
    id: 'cal_384_rules_world_v1',
    name: 'CAL_384_RULES_WORLD_v1',
    version: '1.0',
    status: 'proposed',
    intent: 'Learn the measurement rules of the world before exploring biology',
    wells_total: 384,
    wells_used: 384,
    timepoint_hours: 48,
    cell_lines: 2,
    treatments: ['DMSO (vehicle)', 'Anchor Mild (1µM)', 'Anchor Strong (100µM)', 'Tiles (2x2 vehicle replicates for QC)'],
    design_goals: [
      'Learn plate spatial effects (edges, gradients)',
      'Learn noise floor (tiles show local vs global variation)',
      'Learn feature family variance',
      'Learn cell line-specific spatial sensitivity (HepG2, A549)',
      'Establish dynamic range with anchors',
      'Avoid compound exploration - this is about the instrument'
    ],
    cost_estimate: 1850,
    thumbnail_color: 'from-slate-600 to-slate-700'
  },
  {
    id: 'dose_response_sweep_v1',
    name: 'Dose-Response Sweep v1',
    version: '1.0',
    status: 'planned',
    intent: 'Map dose-response curves for 6 compounds across dynamic range',
    wells_total: 384,
    wells_used: 336,
    timepoint_hours: 24,
    cell_lines: 1,
    treatments: ['6 compounds', '8 doses each', '7 replicates per dose'],
    design_goals: [
      'Establish IC50 values',
      'Characterize Hill slopes',
      'Identify saturating doses',
      'Map dynamic range per compound'
    ],
    cost_estimate: 1650,
    thumbnail_color: 'from-blue-600 to-blue-700'
  },
  {
    id: 'time_course_12h_v1',
    name: 'Time-Course 12h v1',
    version: '1.0',
    status: 'planned',
    intent: 'Characterize temporal dynamics of stress responses',
    wells_total: 384,
    wells_used: 288,
    timepoint_hours: 12,
    cell_lines: 1,
    treatments: ['4 compounds', '6 timepoints', '12 replicates each'],
    design_goals: [
      'Map temporal trajectories',
      'Identify mechanism windows',
      'Distinguish early vs late responses',
      'Establish kinetic parameters'
    ],
    cost_estimate: 1750,
    thumbnail_color: 'from-green-600 to-green-700'
  },
  {
    id: 'mechanism_recovery_v1',
    name: 'Mechanism Recovery v1',
    version: '1.0',
    status: 'planned',
    intent: 'Validate that known mechanism classes are separable in morphology space',
    wells_total: 384,
    wells_used: 360,
    timepoint_hours: 48,
    cell_lines: 2,
    treatments: ['12 compounds (4 mechanisms)', '5 doses each', '3 replicates'],
    design_goals: [
      'Confirm ER stress signature',
      'Confirm mitochondrial signature',
      'Confirm proteasome signature',
      'Confirm oxidative stress signature',
      'Measure cross-mechanism confusion'
    ],
    cost_estimate: 1900,
    thumbnail_color: 'from-purple-600 to-purple-700'
  }
];

interface PlateDesignCatalogProps {
  isDarkMode: boolean;
}

export default function PlateDesignCatalog({ isDarkMode }: PlateDesignCatalogProps) {
  const navigate = useNavigate();
  const [selectedDesign, setSelectedDesign] = useState<PlateDesign | null>(null);

  const getStatusColor = (status: PlateDesign['status']) => {
    switch (status) {
      case 'proposed':
        return isDarkMode ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' : 'bg-yellow-100 text-yellow-700 border-yellow-300';
      case 'planned':
        return isDarkMode ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : 'bg-blue-100 text-blue-700 border-blue-300';
      case 'executed':
        return isDarkMode ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-green-100 text-green-700 border-green-300';
      case 'archived':
        return isDarkMode ? 'bg-gray-500/20 text-gray-400 border-gray-500/30' : 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-2xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          Plate Design Catalog
        </div>
        <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
          Browse experimental plate designs for the epistemic agent. Each design has specific goals and learns different aspects of the measurement system.
        </div>
      </div>

      {/* Design Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PLATE_DESIGNS.map(design => (
          <div
            key={design.id}
            className={`rounded-lg border cursor-pointer transition-all ${
              selectedDesign?.id === design.id
                ? isDarkMode
                  ? 'bg-indigo-900/30 border-indigo-600 shadow-lg'
                  : 'bg-indigo-50 border-indigo-400 shadow-lg'
                : isDarkMode
                  ? 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                  : 'bg-white border-zinc-200 hover:border-zinc-300'
            }`}
            onClick={() => setSelectedDesign(design)}
          >
            {/* Thumbnail */}
            <div className={`h-24 bg-gradient-to-br ${design.thumbnail_color} rounded-t-lg flex items-center justify-center`}>
              <div className="text-white text-4xl font-bold opacity-20">
                {design.wells_used}/{design.wells_total}
              </div>
            </div>

            {/* Content */}
            <div className="p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className={`font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {design.name}
                  </div>
                  <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'}`}>
                    v{design.version}
                  </div>
                </div>
                <span className={`px-2 py-1 rounded text-xs border ${getStatusColor(design.status)}`}>
                  {design.status}
                </span>
              </div>

              <div className={`text-sm mb-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                {design.intent}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  <div className="font-bold">{design.wells_used}</div>
                  <div>wells</div>
                </div>
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  <div className="font-bold">{design.timepoint_hours}h</div>
                  <div>timepoint</div>
                </div>
                <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
                  <div className="font-bold">{design.cell_lines}</div>
                  <div>cell lines</div>
                </div>
              </div>

              {/* Treatments */}
              <div className="mb-3">
                <div className={`text-xs font-bold mb-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  Treatments:
                </div>
                <div className="flex flex-wrap gap-1">
                  {design.treatments.map((t, i) => (
                    <span
                      key={i}
                      className={`text-xs px-2 py-0.5 rounded ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-zinc-100 text-zinc-700'}`}
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>

              {/* Cost */}
              {design.cost_estimate && (
                <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                  Est. cost: <span className="font-bold">${design.cost_estimate}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Selected Design Detail */}
      {selectedDesign && (
        <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                {selectedDesign.name}
              </div>
              <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                {selectedDesign.intent}
              </div>
            </div>
            {(selectedDesign.id === 'cal_384_rules_world_v1' || selectedDesign.id === 'cal_384_rules_world_v2') && (
              <div className="flex gap-2">
                {selectedDesign.id === 'cal_384_rules_world_v1' && (
                  <button
                    onClick={() => navigate('/calibration-plate')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                      : 'bg-indigo-500 hover:bg-indigo-600 text-white'
                      }`}
                  >
                    View Full Design →
                  </button>
                )}
                {selectedDesign.id === 'cal_384_rules_world_v2' && (
                  <button
                    onClick={() => navigate('/calibration-plate-v2')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                      : 'bg-indigo-500 hover:bg-indigo-600 text-white'
                      }`}
                  >
                    View Full Design →
                  </button>
                )}
                <a
                  href={`/plate_designs/${selectedDesign.name}.json`}
                  download
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${isDarkMode
                    ? 'bg-slate-700 hover:bg-slate-600 text-white'
                    : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                    }`}
                >
                  Download JSON
                </a>
              </div>
            )}
          </div>

          <div className={`text-sm font-bold mb-2 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
            Design Goals:
          </div>
          <ul className={`text-sm space-y-1 list-disc list-inside mb-4 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
            {selectedDesign.design_goals.map((goal, i) => (
              <li key={i}>{goal}</li>
            ))}
          </ul>

          {selectedDesign.cost_estimate && (
            <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
              <span className="font-bold">Estimated Cost:</span> ${selectedDesign.cost_estimate}
              <span className="ml-2 text-xs">
                (includes plate, reagents, imaging, analysis)
              </span>
            </div>
          )}
        </div>
      )}

      {/* Design Principles */}
      <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-zinc-200'}`}>
        <div className={`text-lg font-bold mb-3 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
          Design Principles
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <div className={`font-bold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              📏 Calibration Before Biology
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Always run instrument calibration plates before exploring compound biology. Learn the measurement rules first.
            </div>
          </div>
          <div>
            <div className={`font-bold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              🎯 Design for Specific Questions
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Each plate should answer specific questions. Don't try to answer everything at once.
            </div>
          </div>
          <div>
            <div className={`font-bold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              💰 Cost-Aware Batch Sizing
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Amortize fixed costs ($465/cycle) by using more wells during calibration, fewer during biology.
            </div>
          </div>
          <div>
            <div className={`font-bold ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
              ✅ Include Sanity Checks
            </div>
            <div className={isDarkMode ? 'text-slate-400' : 'text-zinc-600'}>
              Every plate should have built-in validation: anchors, tiles, controls to verify measurement quality.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
