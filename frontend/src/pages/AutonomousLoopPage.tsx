import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import AutonomousLoopTab from './CellThalamus/components/AutonomousLoopTab';

const AutonomousLoopPage: React.FC = () => {
    const navigate = useNavigate();
    const [isDarkMode, setIsDarkMode] = useState(false);

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
                        <div>
                            <button
                                onClick={() => navigate('/')}
                                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${isDarkMode
                                    ? 'text-slate-400 hover:text-white'
                                    : 'text-zinc-500 hover:text-zinc-900'
                                    }`}
                            >
                                ← Back to Home
                            </button>
                            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'
                                }`}>
                                Autonomous Science Loop
                            </h1>
                            <p className={`mt-1 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'
                                }`}>
                                A visual representation of the cell_OS autonomous experimental loop
                            </p>
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

            {/* Content */}
            <AutonomousLoopTab isDarkMode={isDarkMode} />
        </div>
    );
};

export default AutonomousLoopPage;
