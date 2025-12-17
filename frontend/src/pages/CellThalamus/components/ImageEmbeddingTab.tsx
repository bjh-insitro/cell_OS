/**
 * Tab: Image → Embedding Visualization
 *
 * Educational visualization showing how DINO ViT transforms a cell image into an embedding
 */

import React, { useState } from 'react';

interface ImageEmbeddingTabProps {
  selectedDesignId: string | null;
}

const ImageEmbeddingTab: React.FC<ImageEmbeddingTabProps> = ({ selectedDesignId }) => {
  const [currentStep, setCurrentStep] = useState<number>(0);

  // Steps in the DINO ViT pipeline
  const steps = [
    {
      title: 'Raw Cell Image',
      description: 'Start with a 224×224 pixel RGB image of a cell captured from microscopy',
      visual: 'cell-image',
      explanation: 'Each pixel contains RGB color values (0-255). The image shows cellular structures like nucleus, mitochondria, and membranes stained with fluorescent markers.',
    },
    {
      title: 'Patch Extraction',
      description: 'Divide image into 16×16 pixel patches (14×14 grid = 196 patches)',
      visual: 'patches',
      explanation: 'Vision Transformers work with patches instead of individual pixels. Each 16×16 patch becomes a "token" - similar to how words are tokens in language models.',
    },
    {
      title: 'Linear Projection',
      description: 'Flatten each patch (16×16×3 = 768 values) and project to embedding dimension',
      visual: 'projection',
      explanation: 'Each patch is converted to a 768-dimensional vector through a learned linear transformation. This creates the initial patch embeddings.',
    },
    {
      title: 'Position Embeddings',
      description: 'Add learnable position embeddings to preserve spatial relationships',
      visual: 'position',
      explanation: 'Since patches are processed in parallel, we add position information so the model knows where each patch came from in the original image (top-left, center, bottom-right, etc.).',
    },
    {
      title: 'Self-Attention (Layer 1-12)',
      description: 'Each patch attends to all other patches to capture global context',
      visual: 'attention',
      explanation: 'Multi-head self-attention allows each patch to "look at" all other patches and determine which ones are relevant. For example, a nucleus patch might attend strongly to nearby cytoplasm patches.',
    },
    {
      title: 'CLS Token Output',
      description: 'Extract the [CLS] token from the final layer as the image embedding',
      visual: 'cls-token',
      explanation: 'The [CLS] (classification) token aggregates information from all patches. After 12 transformer layers, it contains a holistic 768-dimensional representation of the entire cell image.',
    },
    {
      title: 'Final Embedding',
      description: '768-dimensional vector encoding morphological features of the cell',
      visual: 'embedding',
      explanation: 'This embedding captures high-level features like cell shape, organelle distribution, texture patterns, and staining intensity - learned through self-supervised training on millions of images.',
    },
  ];

  const currentStepData = steps[currentStep];

  // Mock visualization components for each step
  const renderVisualization = () => {
    switch (currentStepData.visual) {
      case 'cell-image':
        return (
          <div className="relative w-96 h-96 mx-auto bg-slate-900 rounded-lg border border-slate-700 flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">🔬</div>
              <div className="text-slate-400 text-sm">224×224 px RGB Image</div>
              <div className="text-slate-500 text-xs mt-2">3 channels (R, G, B)</div>
            </div>
          </div>
        );

      case 'patches':
        return (
          <div className="relative w-96 h-96 mx-auto bg-slate-900 rounded-lg border border-slate-700 p-4">
            <div className="grid grid-cols-14 gap-0.5 w-full h-full">
              {Array.from({ length: 196 }).map((_, idx) => (
                <div
                  key={idx}
                  className="bg-violet-500/20 border border-violet-500/30 hover:bg-violet-500/40 transition-colors cursor-pointer"
                  title={`Patch ${idx + 1}`}
                />
              ))}
            </div>
            <div className="absolute bottom-2 left-2 right-2 text-center text-xs text-slate-400 bg-slate-900/80 rounded px-2 py-1">
              14×14 grid = 196 patches (each 16×16 px)
            </div>
          </div>
        );

      case 'projection':
        return (
          <div className="flex items-center justify-center gap-8">
            <div className="text-center">
              <div className="w-20 h-20 bg-violet-500/20 border-2 border-violet-500 rounded flex items-center justify-center">
                <div className="text-2xl">📐</div>
              </div>
              <div className="text-xs text-slate-400 mt-2">16×16×3</div>
              <div className="text-xs text-slate-500">= 768 values</div>
            </div>
            <div className="text-4xl text-violet-400">→</div>
            <div className="text-center">
              <div className="w-32 h-20 bg-green-500/20 border-2 border-green-500 rounded flex items-center justify-center">
                <div className="text-xs text-green-400 font-mono">[768-dim vector]</div>
              </div>
              <div className="text-xs text-slate-400 mt-2">Learned projection</div>
            </div>
          </div>
        );

      case 'position':
        return (
          <div className="flex flex-col items-center gap-6">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="px-4 py-2 bg-green-500/20 border border-green-500 rounded">
                  <div className="text-xs text-green-400 font-mono">Patch Embedding</div>
                </div>
              </div>
              <div className="text-2xl text-violet-400">+</div>
              <div className="text-center">
                <div className="px-4 py-2 bg-blue-500/20 border border-blue-500 rounded">
                  <div className="text-xs text-blue-400 font-mono">Position Embedding</div>
                </div>
              </div>
              <div className="text-2xl text-violet-400">=</div>
              <div className="text-center">
                <div className="px-4 py-2 bg-violet-500/20 border border-violet-500 rounded">
                  <div className="text-xs text-violet-400 font-mono">Positioned Patch</div>
                </div>
              </div>
            </div>
            <div className="text-xs text-slate-400 text-center max-w-md">
              Position embeddings encode spatial location (row, column) so patches know their neighbors
            </div>
          </div>
        );

      case 'attention':
        return (
          <div className="relative w-96 h-96 mx-auto bg-slate-900 rounded-lg border border-slate-700 p-4">
            {/* Simplified attention visualization */}
            <div className="relative w-full h-full">
              {/* Center patch (query) */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-12 bg-violet-500 rounded border-2 border-white z-10">
                <div className="text-xs text-white text-center leading-[3rem]">Query</div>
              </div>

              {/* Surrounding patches with attention lines */}
              {[
                { x: '20%', y: '20%', strength: 0.9 },
                { x: '80%', y: '20%', strength: 0.6 },
                { x: '20%', y: '80%', strength: 0.7 },
                { x: '80%', y: '80%', strength: 0.4 },
                { x: '50%', y: '10%', strength: 0.8 },
                { x: '50%', y: '90%', strength: 0.5 },
                { x: '10%', y: '50%', strength: 0.85 },
                { x: '90%', y: '50%', strength: 0.3 },
              ].map((patch, idx) => (
                <React.Fragment key={idx}>
                  {/* Attention line */}
                  <svg className="absolute inset-0 pointer-events-none">
                    <line
                      x1="50%"
                      y1="50%"
                      x2={patch.x}
                      y2={patch.y}
                      stroke="#8b5cf6"
                      strokeWidth={patch.strength * 3}
                      opacity={patch.strength * 0.6}
                    />
                  </svg>
                  {/* Key/Value patch */}
                  <div
                    className="absolute w-8 h-8 bg-green-500/30 rounded border border-green-500"
                    style={{ left: patch.x, top: patch.y, transform: 'translate(-50%, -50%)' }}
                  />
                </React.Fragment>
              ))}
            </div>
            <div className="absolute bottom-2 left-2 right-2 text-center text-xs text-slate-400 bg-slate-900/80 rounded px-2 py-1">
              Each patch attends to others (line thickness = attention weight)
            </div>
          </div>
        );

      case 'cls-token':
        return (
          <div className="flex flex-col items-center gap-6">
            <div className="flex items-center gap-4">
              <div className="flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 bg-green-500/20 border border-green-500 rounded text-xs text-green-400"
                  >
                    Patch {idx + 1}
                  </div>
                ))}
                <div className="text-center text-slate-500 text-xs">+ 191 more...</div>
              </div>
              <div className="text-4xl text-violet-400">→</div>
              <div className="px-4 py-8 bg-violet-500/30 border-2 border-violet-500 rounded">
                <div className="text-lg text-violet-400 font-bold">[CLS]</div>
                <div className="text-xs text-slate-400 mt-1">Aggregated</div>
              </div>
            </div>
            <div className="text-xs text-slate-400 text-center max-w-md">
              The [CLS] token sits alongside patches and aggregates global image information through attention
            </div>
          </div>
        );

      case 'embedding':
        return (
          <div className="flex flex-col items-center gap-6">
            <div className="relative">
              <div className="flex gap-0.5">
                {Array.from({ length: 96 }).map((_, idx) => {
                  const value = Math.sin(idx * 0.2) * 0.5 + 0.5; // Mock embedding values
                  return (
                    <div
                      key={idx}
                      className="w-1 bg-gradient-to-t from-violet-600 to-pink-500 rounded-t"
                      style={{ height: `${value * 80 + 20}px` }}
                    />
                  );
                })}
              </div>
              <div className="text-center text-xs text-slate-400 mt-2">
                768-dimensional embedding vector (showing first 96 dims)
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                <div className="text-violet-400 font-semibold mb-1">Captures:</div>
                <div className="text-slate-400">• Cell shape & size</div>
                <div className="text-slate-400">• Organelle distribution</div>
                <div className="text-slate-400">• Texture patterns</div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                <div className="text-green-400 font-semibold mb-1">Use cases:</div>
                <div className="text-slate-400">• Similarity search</div>
                <div className="text-slate-400">• Clustering</div>
                <div className="text-slate-400">• Classification</div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Image → Embedding Pipeline</h2>
        <p className="text-slate-400">
          Learn how DINO ViT transforms cell microscopy images into vector embeddings
        </p>
      </div>

      {/* Progress indicator */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          {steps.map((step, idx) => (
            <React.Fragment key={idx}>
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all cursor-pointer ${
                  idx === currentStep
                    ? 'bg-violet-600 border-violet-400 text-white'
                    : idx < currentStep
                    ? 'bg-green-600 border-green-400 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-400'
                }`}
                onClick={() => setCurrentStep(idx)}
              >
                {idx < currentStep ? '✓' : idx + 1}
              </div>
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 ${
                    idx < currentStep ? 'bg-green-500' : 'bg-slate-700'
                  }`}
                />
              )}
            </React.Fragment>
          ))}
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
            Step {currentStep + 1} of {steps.length}
          </div>
        </div>
      </div>

      {/* Current step visualization */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-8">
        <div className="text-center mb-8">
          <h3 className="text-xl font-bold text-white mb-2">{currentStepData.title}</h3>
          <p className="text-slate-400">{currentStepData.description}</p>
        </div>

        {/* Visualization */}
        <div className="min-h-[400px] flex items-center justify-center mb-8">
          {renderVisualization()}
        </div>

        {/* Explanation */}
        <div className="bg-slate-900/50 rounded-lg p-6 border border-slate-700">
          <div className="text-sm font-semibold text-violet-400 mb-2">💡 Explanation:</div>
          <div className="text-slate-300 leading-relaxed">{currentStepData.explanation}</div>
        </div>
      </div>

      {/* Navigation buttons */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
          disabled={currentStep === 0}
          className={`px-6 py-3 rounded-lg font-medium transition-all ${
            currentStep === 0
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-violet-600 text-white hover:bg-violet-700'
          }`}
        >
          ← Previous Step
        </button>

        <div className="text-slate-400 text-sm">
          {currentStep === steps.length - 1
            ? 'Tutorial complete!'
            : `${steps.length - currentStep - 1} steps remaining`}
        </div>

        <button
          onClick={() => setCurrentStep(Math.min(steps.length - 1, currentStep + 1))}
          disabled={currentStep === steps.length - 1}
          className={`px-6 py-3 rounded-lg font-medium transition-all ${
            currentStep === steps.length - 1
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-violet-600 text-white hover:bg-violet-700'
          }`}
        >
          Next Step →
        </button>
      </div>

      {/* Additional resources */}
      <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-6">
        <div className="text-sm font-semibold text-blue-400 mb-3">📚 Learn More:</div>
        <div className="space-y-2 text-sm text-slate-300">
          <div>
            • <strong>DINO paper:</strong> Self-supervised vision transformers by Caron et al. (2021)
          </div>
          <div>
            • <strong>ViT architecture:</strong> "An Image is Worth 16x16 Words" by Dosovitskiy et al. (2020)
          </div>
          <div>
            • <strong>Attention mechanism:</strong> "Attention is All You Need" by Vaswani et al. (2017)
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageEmbeddingTab;
