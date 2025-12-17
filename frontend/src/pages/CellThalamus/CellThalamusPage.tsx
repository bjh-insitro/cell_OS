/**
 * Cell Thalamus Dashboard - Main Page
 *
 * Interactive exploration of Phase 0 variance validation
 * 6 tabs: Run Simulation, Dose-Response, Morphology, Variance, Sentinel, Plate Viewer
 * Additional tutorials/viewing page accessible via button in header
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RunSimulationTab from './components/RunSimulationTab';
import ExperimentsTab from './components/ExperimentsTab';
import MorphologyTab from './components/MorphologyTab';
import DoseResponseTab from './components/DoseResponseTab';
import VarianceTab from './components/VarianceTab';
import SentinelTab from './components/SentinelTab';
import PlateViewerTab from './components/PlateViewerTab';
import DesignCatalogTab from './components/DesignCatalogTab';
import MechanismRecoveryTab from './components/MechanismRecoveryTab';

type TabType = 'run' | 'experiments' | 'catalog' | 'morphology' | 'dose' | 'variance' | 'sentinel' | 'plate' | 'mechanism';

const CellThalamusPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('run');
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(null);

  const tabs = [
    { id: 'run', label: 'Run Simulation', icon: '▶️' },
    { id: 'experiments', label: 'Experiments', icon: '📋' },
    { id: 'catalog', label: 'Design Catalog', icon: '📐' },
    { id: 'dose', label: 'Dose-Response', icon: '📈' },
    { id: 'morphology', label: 'Morphology Manifold', icon: '🎨' },
    { id: 'variance', label: 'Variance Analysis', icon: '📊' },
    { id: 'mechanism', label: 'Mechanism Recovery', icon: '🔬' },
    { id: 'sentinel', label: 'Sentinel Monitor', icon: '🎯' },
    { id: 'plate', label: 'Plate Viewer', icon: '🗺️' },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      {/* Header */}
      <div className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <button
                onClick={() => navigate('/')}
                className="text-slate-400 hover:text-white transition-colors text-sm mb-2 flex items-center gap-1"
              >
                ← Back to Home
              </button>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <span>🧬</span>
                <span>Cell Thalamus v1</span>
              </h1>
              <p className="text-slate-400 mt-1">
                Variance-Aware Measurement Validation
              </p>
            </div>
            <div>
              <button
                onClick={() => navigate('/cell-thalamus/viewing')}
                className="bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium flex items-center gap-2"
              >
                <span>🎬</span>
                <span>Tutorials & Viewing</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-slate-800/30 border-b border-slate-700">
        <div className="container mx-auto px-6">
          <div className="flex space-x-1 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`
                  px-4 py-3 text-sm font-medium transition-all whitespace-nowrap
                  ${activeTab === tab.id
                    ? 'text-violet-400 border-b-2 border-violet-400 bg-slate-800/50'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/30'
                  }
                `}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <div className="container mx-auto px-6 py-8">
        {activeTab === 'run' && (
          <RunSimulationTab
            onSimulationComplete={(designId) => {
              setSelectedDesignId(designId);
              navigate('/cell-thalamus/viewing');
            }}
          />
        )}
        {activeTab === 'experiments' && (
          <ExperimentsTab
            selectedDesignId={selectedDesignId || undefined}
            onSelectDesign={(designId) => {
              setSelectedDesignId(designId);
              setActiveTab('morphology');
            }}
          />
        )}
        {activeTab === 'catalog' && <DesignCatalogTab />}
        {activeTab === 'morphology' && (
          <MorphologyTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'dose' && (
          <DoseResponseTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'variance' && (
          <VarianceTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'mechanism' && (
          <MechanismRecoveryTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'sentinel' && (
          <SentinelTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'plate' && (
          <PlateViewerTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
      </div>

      {/* Glossary Sidebar - Expandable */}
      <div className="fixed bottom-4 right-4">
        <details className="bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-lg shadow-xl max-w-md">
          <summary className="px-4 py-3 cursor-pointer text-sm font-semibold text-violet-400 hover:text-violet-300 transition-colors">
            📖 Glossary
          </summary>
          <div className="px-4 pb-4 text-xs text-slate-300 space-y-3 max-h-96 overflow-y-auto">
            <div>
              <h4 className="font-semibold text-white mb-1">Readouts:</h4>
              <ul className="space-y-1 pl-2">
                <li><strong>ATP:</strong> Luminescent viability assay (scalar anchor)</li>
                <li><strong>ER:</strong> Endoplasmic reticulum morphology</li>
                <li><strong>Mito:</strong> Mitochondrial morphology</li>
                <li><strong>Nucleus:</strong> Nuclear morphology</li>
                <li><strong>Actin:</strong> Cytoskeleton morphology</li>
                <li><strong>RNA:</strong> Translation site morphology</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">Stress Axes:</h4>
              <ul className="space-y-1 pl-2">
                <li><strong>Oxidative:</strong> ROS production (tBHQ, H₂O₂)</li>
                <li><strong>ER Stress:</strong> Protein folding (tunicamycin, thapsigargin)</li>
                <li><strong>Mitochondrial:</strong> Energy dysfunction (CCCP, oligomycin)</li>
                <li><strong>DNA Damage:</strong> Replication stress (etoposide)</li>
                <li><strong>Proteasome:</strong> Protein degradation (MG132)</li>
                <li><strong>Microtubule:</strong> Cytoskeleton (nocodazole)</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">Key Concepts:</h4>
              <ul className="space-y-1 pl-2">
                <li><strong>Sentinel:</strong> QC well with fixed conditions</li>
                <li><strong>SPC:</strong> Statistical Process Control</li>
                <li><strong>Edge Effect:</strong> Spatial artifact on plate edges</li>
                <li><strong>PCA:</strong> Principal Component Analysis</li>
                <li><strong>Manifold:</strong> Low-dimensional structure in high-D data</li>
              </ul>
            </div>
          </div>
        </details>
      </div>
    </div>
  );
};

export default CellThalamusPage;
