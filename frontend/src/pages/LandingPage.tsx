import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LandingPage: React.FC = () => {
    const navigate = useNavigate();

    const [cellLine, setCellLine] = useState('A549');
    const [stressor, setStressor] = useState('Oxidative Stress');
    const [perturbation, setPerturbation] = useState('Whole Genome Cas9N');
    const [measurement, setMeasurement] = useState('insitro Paint');

    const handleEnter = () => {
        if (
            cellLine === 'A549' &&
            stressor === 'Oxidative Stress' &&
            perturbation === 'Whole Genome Cas9N' &&
            measurement === 'insitro Paint'
        ) {
            navigate('/dashboard');
        } else {
            navigate('/under-development');
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4">
            <div className="w-full max-w-6xl">
                <h1 className="text-4xl md:text-5xl font-bold text-white text-center mb-4 tracking-tight">
                    cell_OS
                </h1>
                <p className="text-slate-400 text-center mb-16 text-lg">
                    Select your experimental parameters to view status
                </p>

                <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 shadow-2xl">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {/* Cell Line Dropdown */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Cell Line</label>
                            <div className="relative">
                                <select
                                    value={cellLine}
                                    onChange={(e) => setCellLine(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 appearance-none focus:outline-none focus:ring-2 focus:ring-violet-500 hover:border-violet-500/50 transition-colors cursor-pointer"
                                >
                                    <option>A549</option>
                                    <option>HepG2</option>
                                    <option>U2OS</option>
                                </select>
                                <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                </div>
                            </div>
                        </div>

                        {/* Stressor Dropdown */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-pink-400 uppercase tracking-wider">Stressor</label>
                            <div className="relative">
                                <select
                                    value={stressor}
                                    onChange={(e) => setStressor(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 appearance-none focus:outline-none focus:ring-2 focus:ring-pink-500 hover:border-pink-500/50 transition-colors cursor-pointer"
                                >
                                    <option>Oxidative Stress</option>
                                    <option disabled>Mitochondrial dysfunction</option>
                                    <option disabled>ER stress and proteostasis</option>
                                    <option disabled>Lipid handling</option>
                                    <option disabled>Lysosomal and trafficking defects</option>
                                    <option disabled>Fibrotic / ECM remodeling</option>
                                </select>
                                <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                </div>
                            </div>
                        </div>

                        {/* Perturbation Dropdown */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-teal-400 uppercase tracking-wider">Perturbation</label>
                            <div className="relative">
                                <select
                                    value={perturbation}
                                    onChange={(e) => setPerturbation(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 appearance-none focus:outline-none focus:ring-2 focus:ring-teal-500 hover:border-teal-500/50 transition-colors cursor-pointer"
                                >
                                    <option>Whole Genome Cas9N</option>
                                </select>
                                <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                </div>
                            </div>
                        </div>

                        {/* Measurement Dropdown */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-orange-400 uppercase tracking-wider">Measurement</label>
                            <div className="relative">
                                <select
                                    value={measurement}
                                    onChange={(e) => setMeasurement(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-3 appearance-none focus:outline-none focus:ring-2 focus:ring-orange-500 hover:border-orange-500/50 transition-colors cursor-pointer"
                                >
                                    <option>insitro Paint</option>
                                </select>
                                <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
                        <button
                            onClick={handleEnter}
                            className="px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-full shadow-lg hover:shadow-blue-500/25 transition-all transform hover:scale-105 active:scale-95"
                        >
                            View Status Dashboard
                        </button>
                        <button
                            onClick={() => navigate('/cell-thalamus')}
                            className="px-8 py-3 bg-violet-600 hover:bg-violet-500 text-white font-bold rounded-full shadow-lg hover:shadow-violet-500/25 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2 justify-center"
                        >
                            <span>🧬</span>
                            <span>Cell Thalamus v1</span>
                        </button>
                    </div>
                </div>

                {/* Cell Thalamus Info Card */}
                <div className="mt-8 bg-violet-900/20 backdrop-blur-sm border border-violet-500/30 rounded-xl p-6">
                    <h3 className="text-xl font-bold text-violet-300 mb-2 flex items-center gap-2">
                        <span>🧬</span>
                        <span>Cell Thalamus v1 - Phase 0</span>
                    </h3>
                    <p className="text-slate-300 text-sm">
                        Variance-aware measurement validation dashboard. Run Phase 0 simulations to validate
                        that biological variance dominates technical noise before scaling to the Printed Tensor.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <span className="px-3 py-1 bg-violet-500/20 text-violet-300 rounded-full text-xs font-semibold">
                            Cell Painting
                        </span>
                        <span className="px-3 py-1 bg-violet-500/20 text-violet-300 rounded-full text-xs font-semibold">
                            ATP Viability
                        </span>
                        <span className="px-3 py-1 bg-violet-500/20 text-violet-300 rounded-full text-xs font-semibold">
                            Variance Analysis
                        </span>
                        <span className="px-3 py-1 bg-violet-500/20 text-violet-300 rounded-full text-xs font-semibold">
                            SPC Monitoring
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LandingPage;
