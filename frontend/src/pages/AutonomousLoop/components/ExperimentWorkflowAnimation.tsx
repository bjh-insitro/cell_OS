import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Beaker, Droplet, Clock, Microscope, Palette, Camera, FlaskConical } from 'lucide-react';

interface WorkflowStep {
    id: string;
    title: string;
    description: string;
    icon: any;
    duration: string;
    color: string;
}

const WORKFLOW_STEPS: WorkflowStep[] = [
    {
        id: 'plating',
        title: 'Cell Plating',
        description: 'Seed 5,000 cells/well in 96-well plate. Cells attach overnight in growth medium.',
        icon: FlaskConical,
        duration: '24h incubation',
        color: 'from-blue-500 to-blue-600'
    },
    {
        id: 'treatment',
        title: 'Drug Treatment',
        description: 'Add compounds at specified doses. Automated liquid handler dispenses precise volumes.',
        icon: Droplet,
        duration: '~30 min',
        color: 'from-purple-500 to-purple-600'
    },
    {
        id: 'incubation',
        title: 'Incubation',
        description: 'Cells respond to treatment. Cellular stress pathways activate, morphology changes.',
        icon: Clock,
        duration: '12-48h',
        color: 'from-orange-500 to-orange-600'
    },
    {
        id: 'fixation',
        title: 'Fixation',
        description: 'Add paraformaldehyde to preserve cell structure. Arrests all cellular processes.',
        icon: Beaker,
        duration: '20 min',
        color: 'from-red-500 to-red-600'
    },
    {
        id: 'staining',
        title: 'Cell Painting',
        description: 'Apply 5-channel fluorescent dyes: ER, mitochondria, nucleus, actin, RNA.',
        icon: Palette,
        duration: '3h',
        color: 'from-pink-500 to-pink-600'
    },
    {
        id: 'imaging',
        title: 'High-Content Imaging',
        description: 'Automated microscope captures 9 fields/well across 5 fluorescent channels.',
        icon: Camera,
        duration: '~4h/plate',
        color: 'from-green-500 to-green-600'
    },
    {
        id: 'analysis',
        title: 'Image Analysis',
        description: 'CellProfiler extracts 1,500+ morphological features per cell. ATP viability measured.',
        icon: Microscope,
        duration: '~2h compute',
        color: 'from-cyan-500 to-cyan-600'
    }
];

interface ExperimentWorkflowAnimationProps {
    isDarkMode: boolean;
    autoPlay?: boolean;
    onComplete?: () => void;
}

const ExperimentWorkflowAnimation: React.FC<ExperimentWorkflowAnimationProps> = ({
    isDarkMode,
    autoPlay = true,
    onComplete
}) => {
    const [currentStep, setCurrentStep] = useState(0);
    const [isPlaying, setIsPlaying] = useState(autoPlay);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (!isPlaying || isPaused) return;

        const timer = setTimeout(() => {
            if (currentStep < WORKFLOW_STEPS.length - 1) {
                setCurrentStep(prev => prev + 1);
            } else {
                setIsPlaying(false);
                if (onComplete) onComplete();
            }
        }, 3000); // 3 seconds per step

        return () => clearTimeout(timer);
    }, [currentStep, isPlaying, isPaused, onComplete]);

    const handleStepClick = (index: number) => {
        setCurrentStep(index);
        setIsPaused(true);
    };

    const handlePlayPause = () => {
        if (currentStep === WORKFLOW_STEPS.length - 1 && !isPlaying) {
            // Restart from beginning
            setCurrentStep(0);
            setIsPlaying(true);
            setIsPaused(false);
        } else if (!isPlaying) {
            // Start playing from current position
            setIsPlaying(true);
            setIsPaused(false);
        } else {
            // Toggle pause
            setIsPaused(!isPaused);
        }
    };

    const handleRestart = () => {
        setCurrentStep(0);
        setIsPlaying(true);
        setIsPaused(false);
    };

    const step = WORKFLOW_STEPS[currentStep];
    const Icon = step.icon;

    return (
        <div className="space-y-6">
            {/* Main Animation Display */}
            <div className={`relative rounded-xl overflow-hidden border ${isDarkMode ? 'border-slate-700 bg-slate-900' : 'border-zinc-200 bg-white'}`}>
                <AnimatePresence mode="wait">
                    <motion.div
                        key={currentStep}
                        initial={{ opacity: 0, x: 100 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -100 }}
                        transition={{ duration: 0.5 }}
                        className="p-8"
                    >
                        {/* Step Header */}
                        <div className="flex items-start gap-4 mb-6">
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ delay: 0.2, type: "spring" }}
                                className={`p-4 rounded-xl bg-gradient-to-br ${step.color} text-white shadow-lg`}
                            >
                                <Icon className="w-8 h-8" />
                            </motion.div>
                            <div className="flex-1">
                                <motion.div
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.3 }}
                                >
                                    <div className="flex items-center gap-3 mb-2">
                                        <h3 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                            {step.title}
                                        </h3>
                                        <span className={`text-sm px-3 py-1 rounded-full ${isDarkMode ? 'bg-slate-800 text-slate-400' : 'bg-zinc-100 text-zinc-600'}`}>
                                            Step {currentStep + 1} of {WORKFLOW_STEPS.length}
                                        </span>
                                    </div>
                                    <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                        Duration: {step.duration}
                                    </p>
                                </motion.div>
                            </div>
                        </div>

                        {/* Step Description */}
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.4 }}
                            className={`text-lg ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'} leading-relaxed`}
                        >
                            {step.description}
                        </motion.p>

                        {/* Visual Representation */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.5 }}
                            className={`mt-6 p-6 rounded-lg ${isDarkMode ? 'bg-slate-800/50' : 'bg-zinc-50'}`}
                        >
                            {/* Plate visualization for each step */}
                            <div className="flex justify-center items-center gap-4">
                                {/* Mini 96-well plate representation */}
                                <div className="grid grid-cols-12 gap-1">
                                    {Array.from({ length: 96 }).map((_, i) => {
                                        const row = Math.floor(i / 12);
                                        const col = i % 12;
                                        const isActive = (
                                            (currentStep >= 0 && row < 4) || // First half wells for plating
                                            (currentStep >= 1 && col < 6) || // Different pattern for treatment
                                            (currentStep >= 2) // All wells after incubation
                                        );

                                        return (
                                            <motion.div
                                                key={i}
                                                initial={{ scale: 0 }}
                                                animate={{
                                                    scale: isActive ? 1 : 0.7,
                                                    opacity: isActive ? 1 : 0.3
                                                }}
                                                transition={{
                                                    delay: i * 0.005,
                                                    duration: 0.2
                                                }}
                                                className={`
                                                    w-3 h-3 rounded-full
                                                    ${isActive
                                                        ? `bg-gradient-to-br ${step.color}`
                                                        : isDarkMode ? 'bg-slate-700' : 'bg-zinc-300'
                                                    }
                                                `}
                                            />
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Step-specific visual cue */}
                            <div className="mt-4 text-center">
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.8, duration: 1, repeat: Infinity, repeatType: "reverse" }}
                                    className={`inline-flex items-center gap-2 text-sm ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}
                                >
                                    {currentStep === 0 && "💧 Cells settling..."}
                                    {currentStep === 1 && "💉 Dispensing compounds..."}
                                    {currentStep === 2 && "⏰ Cells responding to stress..."}
                                    {currentStep === 3 && "🧪 Fixing cell structure..."}
                                    {currentStep === 4 && "🎨 Applying fluorescent dyes..."}
                                    {currentStep === 5 && "📸 Capturing images..."}
                                    {currentStep === 6 && "🤖 Extracting features..."}
                                </motion.div>
                            </div>
                        </motion.div>
                    </motion.div>
                </AnimatePresence>

                {/* Progress Bar */}
                <div className={`absolute bottom-0 left-0 right-0 h-1 ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-200'}`}>
                    <motion.div
                        className={`h-full bg-gradient-to-r ${step.color}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${((currentStep + 1) / WORKFLOW_STEPS.length) * 100}%` }}
                        transition={{ duration: 0.5 }}
                    />
                </div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between">
                <div className="flex gap-2">
                    <button
                        onClick={handlePlayPause}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                            isDarkMode
                                ? 'bg-violet-600 hover:bg-violet-500 text-white'
                                : 'bg-violet-500 hover:bg-violet-600 text-white'
                        }`}
                    >
                        {isPaused || !isPlaying ? '▶️ Play' : '⏸️ Pause'}
                    </button>
                    <button
                        onClick={handleRestart}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                            isDarkMode
                                ? 'bg-slate-700 hover:bg-slate-600 text-white'
                                : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                        }`}
                    >
                        🔄 Restart
                    </button>
                </div>

                {/* Step Dots */}
                <div className="flex gap-2">
                    {WORKFLOW_STEPS.map((s, i) => (
                        <button
                            key={s.id}
                            onClick={() => handleStepClick(i)}
                            className={`
                                w-3 h-3 rounded-full transition-all
                                ${i === currentStep
                                    ? `bg-gradient-to-r ${s.color} scale-125`
                                    : isDarkMode ? 'bg-slate-700 hover:bg-slate-600' : 'bg-zinc-300 hover:bg-zinc-400'
                                }
                            `}
                            title={s.title}
                        />
                    ))}
                </div>
            </div>

            {/* Timeline */}
            <div className={`rounded-lg overflow-hidden border ${isDarkMode ? 'border-slate-700 bg-slate-800/50' : 'border-zinc-200 bg-zinc-50'}`}>
                <div className="p-4">
                    <h4 className={`text-sm font-semibold mb-3 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                        Complete Protocol Timeline
                    </h4>
                    <div className="space-y-2">
                        {WORKFLOW_STEPS.map((s, i) => {
                            const StepIcon = s.icon;
                            return (
                                <button
                                    key={s.id}
                                    onClick={() => handleStepClick(i)}
                                    className={`
                                        w-full text-left p-3 rounded-lg transition-all
                                        ${i === currentStep
                                            ? isDarkMode ? 'bg-slate-700 border-2 border-violet-500' : 'bg-white border-2 border-violet-400'
                                            : isDarkMode ? 'bg-slate-900/50 hover:bg-slate-800' : 'bg-white hover:bg-zinc-50'
                                        }
                                    `}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg bg-gradient-to-br ${s.color} text-white`}>
                                            <StepIcon className="w-4 h-4" />
                                        </div>
                                        <div className="flex-1">
                                            <div className={`text-sm font-medium ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                                {s.title}
                                            </div>
                                            <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-zinc-500'}`}>
                                                {s.duration}
                                            </div>
                                        </div>
                                        {i === currentStep && (
                                            <motion.div
                                                initial={{ scale: 0 }}
                                                animate={{ scale: 1 }}
                                                className="text-violet-500"
                                            >
                                                ▶️
                                            </motion.div>
                                        )}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ExperimentWorkflowAnimation;
