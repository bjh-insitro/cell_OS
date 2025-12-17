/**
 * Cell Thalamus Viewing Page
 *
 * Educational and visualization tabs: Experiment Visualization and Image → Embedding
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ExperimentVisualizationTab from './components/ExperimentVisualizationTab';
import ImageEmbeddingTab from './components/ImageEmbeddingTab';

type TabType = 'visualization' | 'embedding';

const ViewingPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('visualization');
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(null);

  const tabs = [
    { id: 'visualization', label: 'Experiment Visualization', icon: '🎬' },
    { id: 'embedding', label: 'Image → Embedding', icon: '🔬' },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      {/* Header */}
      <div className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <button
                onClick={() => navigate('/cell-thalamus')}
                className="text-slate-400 hover:text-white transition-colors text-sm mb-2 flex items-center gap-1"
              >
                ← Back to Cell Thalamus
              </button>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <span>🧬</span>
                <span>Cell Thalamus - Viewing</span>
              </h1>
              <p className="text-slate-400 mt-1">
                Educational Visualizations & Tutorials
              </p>
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
        {activeTab === 'visualization' && (
          <ExperimentVisualizationTab
            selectedDesignId={selectedDesignId}
            onDesignChange={setSelectedDesignId}
          />
        )}
        {activeTab === 'embedding' && (
          <ImageEmbeddingTab selectedDesignId={selectedDesignId} />
        )}
      </div>
    </div>
  );
};

export default ViewingPage;
