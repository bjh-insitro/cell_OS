/**
 * Epistemic Provenance Demo - Interactive Tutorial
 * Clean, step-by-step walkthrough of how the epistemic agent works
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, ChevronRight, Play } from 'lucide-react';

const EpistemicProvenancePage: React.FC = () => {
    const navigate = useNavigate();
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [tutorialStep, setTutorialStep] = useState(0);
    const [showTutorial, setShowTutorial] = useState(true);

    // Tutorial steps with progressive disclosure
    const tutorialSteps = [
        {
            title: "Building Knowledge as a Moat",
            subtitle: "How epistemic lift creates competitive advantage in life sciences",
            content: (
                <div className="space-y-6">
                    <div>
                        <p className="text-xl font-semibold mb-3">
                            The Strategic Goal: Epistemic Lift
                        </p>
                        <p className="text-lg mb-4">
                            In life sciences, <strong>knowledge is the moat</strong>. The company that understands biology better - faster - wins.
                        </p>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                        <p className="font-semibold mb-3 text-lg">What is epistemic lift?</p>
                        <div className="space-y-3 text-sm">
                            <p>
                                <strong>Epistemic lift</strong> is the rate at which you can accumulate <em>trustworthy</em> knowledge about biological systems.
                            </p>
                            <p>
                                It's not just running more experiments - it's building a reliable map of how biology works, where every data point you trust
                                compounds into better predictions, better designs, better therapeutics.
                            </p>
                            <p className="font-semibold">
                                High epistemic lift = You learn biology faster than your competitors = You build an unassailable knowledge moat.
                            </p>
                        </div>
                    </div>

                    <div>
                        <p className="text-xl font-semibold mb-3">
                            The Problem: Speed vs. Reliability
                        </p>
                        <p className="text-lg mb-4">
                            Automated labs promise speed. But there's a critical tradeoff:
                        </p>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-red-900/30 border-l-4 border-red-500' : 'bg-red-100 border-l-4 border-red-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Fast but wrong = negative epistemic lift</p>
                        <div className="space-y-2 text-sm">
                            <p>
                                • Traditional automated labs run experiments fast, but don't track their own measurement reliability
                            </p>
                            <p>
                                • They produce data even when noise is too high - <strong>unreliable data that looks scientific but isn't reproducible</strong>
                            </p>
                            <p>
                                • Result: You accumulate "knowledge" that's actually wrong. This is <strong>negative epistemic lift</strong> - you're moving away from truth.
                            </p>
                            <p className="font-semibold mt-2">
                                Bad data is worse than no data. It poisons your models, wastes downstream resources, and sends you in the wrong direction.
                            </p>
                        </div>
                    </div>

                    <div>
                        <p className="text-xl font-semibold mb-3">
                            The Vision: Automated epistemic rigor
                        </p>
                        <p className="text-lg">
                            What if we could automate experiments <em>and</em> guarantee every result is trustworthy?
                        </p>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                        <p className="font-semibold mb-3 text-lg">The Epistemic Agent: Infrastructure for reliable knowledge</p>
                        <div className="space-y-3 text-sm">
                            <p>
                                <strong>Core idea:</strong> An automated lab that tracks its own measurement uncertainty and refuses to make claims it can't statistically justify.
                            </p>
                            <p>
                                <strong>Key innovation:</strong> The system can <strong>abort</strong> - explicitly refuse to act when it can't guarantee reliability.
                                This isn't a failure, it's epistemic honesty encoded as a constraint.
                            </p>
                            <p>
                                <strong>Why this creates a moat:</strong> Every experiment that passes through this system is statistically validated.
                                You accumulate knowledge at maximum speed <em>subject to the constraint of reliability</em>.
                                This compounds - reliable data builds better models, which design better experiments, which generate more reliable data.
                            </p>
                            <p className="font-semibold">
                                Your competitors are running faster but accumulating garbage. You're building a fortress of trustworthy knowledge they can't replicate.
                            </p>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-indigo-900/30 border-l-4 border-indigo-500' : 'bg-indigo-100 border-l-4 border-indigo-600'}`}>
                        <p className="font-semibold mb-2 text-lg">The Journey: From Instrument Trust to Causal Models</p>
                        <p className="text-sm mb-4">
                            Building a knowledge moat requires a progression through phases, each building on the last:
                        </p>
                        <div className="space-y-4">
                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-indigo-800/40' : 'bg-white'}`}>
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-sm">1</div>
                                    <div className="flex-1">
                                        <p className="font-semibold mb-1">Phase 1: Instrument Trust (Pay-for-calibration)</p>
                                        <p className="text-xs">
                                            <strong>Question:</strong> "Can I trust my measurements?"<br/>
                                            <strong>Goal:</strong> Prove the instrument has low enough noise to detect biological signals.<br/>
                                            <strong>Output:</strong> A calibrated measurement system with known, bounded uncertainty.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-indigo-800/40' : 'bg-white'}`}>
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-sm">2</div>
                                    <div className="flex-1">
                                        <p className="font-semibold mb-1">Phase 2: Causal Exploration</p>
                                        <p className="text-xs">
                                            <strong>Question:</strong> "What are the mechanisms?"<br/>
                                            <strong>Goal:</strong> Use the trusted instrument to run perturbation experiments - knock down genes, add compounds, vary conditions.<br/>
                                            <strong>Output:</strong> A map of which perturbations cause which phenotypes. Initial causal hypotheses.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-indigo-800/40' : 'bg-white'}`}>
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-sm">3</div>
                                    <div className="flex-1">
                                        <p className="font-semibold mb-1">Phase 3: Mechanism Disambiguation</p>
                                        <p className="text-xs">
                                            <strong>Question:</strong> "How do these mechanisms interact?"<br/>
                                            <strong>Goal:</strong> Design combinatorial experiments to distinguish between competing causal models. Test interaction effects.<br/>
                                            <strong>Output:</strong> A validated causal model - not just correlations, but mechanistic understanding of how biology works.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-indigo-800/40' : 'bg-white'}`}>
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-sm">4</div>
                                    <div className="flex-1">
                                        <p className="font-semibold mb-1">Phase 4: Predictive Models (The Moat)</p>
                                        <p className="text-xs">
                                            <strong>Question:</strong> "What will happen if I do X?"<br/>
                                            <strong>Goal:</strong> Use causal models to predict outcomes of new perturbations without running experiments.<br/>
                                            <strong>Output:</strong> Predictive models competitors can't replicate because they don't have your epistemic infrastructure.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="mt-4 pt-4 border-t border-indigo-400/30">
                            <p className="text-xs font-semibold">
                                Phase 1 (instrument trust) is the foundation. Without it, phases 2-4 collapse - you'd be building causal models on unreliable data,
                                which means your "knowledge moat" is built on sand.
                            </p>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-amber-900/30 border-l-4 border-amber-500' : 'bg-amber-100 border-l-4 border-amber-600'}`}>
                        <p className="text-lg font-semibold mb-2">What this tutorial covers: Phase 1 (Instrument Trust)</p>
                        <p className="text-sm mb-3">
                            This walkthrough focuses on the <strong>first phase</strong>: How does the epistemic agent establish instrument trust?
                        </p>
                        <p className="text-sm mb-3">
                            You'll see the pay-for-calibration system in action - how the agent decides whether to calibrate or abort,
                            and why this foundation is necessary before any causal experimentation can begin.
                        </p>
                        <p className="text-xs text-amber-800 dark:text-amber-200 font-semibold">
                            Future tutorials will show phases 2-4: how we use this trusted instrument to build causal models and ultimately achieve epistemic lift.
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 1: The Cold Start Problem",
            subtitle: "Why you can't do biology without knowing your instrument",
            content: (
                <div className="space-y-4">
                    <div>
                        <p className="text-lg mb-3">
                            <strong>Scenario:</strong> You just built an automated lab. You have robots, imaging systems, liquid handlers - everything ready to go.
                        </p>
                        <p className="text-lg">
                            But there's a critical question you can't answer yet: <strong>"Can this instrument detect real biological effects?"</strong>
                        </p>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-amber-900/30 border-l-4 border-amber-500' : 'bg-amber-100 border-l-4 border-amber-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Why this matters: Signal vs. Noise</p>
                        <div className="space-y-3 text-sm">
                            <p>
                                Every biological measurement has two components:
                            </p>
                            <div className={`p-3 rounded ${isDarkMode ? 'bg-amber-800/30' : 'bg-amber-50'}`}>
                                <p className="font-mono text-xs mb-2">Measured value = True biological signal + Measurement noise</p>
                            </div>
                            <p>
                                <strong>Example:</strong> You treat cells with a drug and measure viability = 0.75. What does this mean?
                            </p>
                            <ul className="ml-6 space-y-1 list-disc">
                                <li>If noise is low (±0.05): The drug killed ~25% of cells. <strong>Real biological effect.</strong></li>
                                <li>If noise is high (±0.20): The measurement could be anywhere from 0.55 to 0.95. <strong>You learned nothing.</strong></li>
                            </ul>
                            <p className="font-semibold mt-3">
                                Until you know your instrument's noise level, you can't tell if a measurement reflects biology or just experimental variability.
                            </p>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-red-900/30 border-l-4 border-red-500' : 'bg-red-100 border-l-4 border-red-600'}`}>
                        <p className="font-semibold mb-2">The constraint: No biology without instrument trust</p>
                        <div className="text-sm space-y-2">
                            <p>
                                The system is in <code className="px-1 bg-black/20 rounded font-mono">pre_gate</code> regime.
                                This means:
                            </p>
                            <ul className="ml-6 space-y-1 list-disc">
                                <li><strong>All biological experiments are blocked.</strong> You're not allowed to test drugs, screen conditions, or measure phenotypes.</li>
                                <li><strong>Only calibration experiments are permitted.</strong> The first actions must establish instrument trust.</li>
                                <li><strong>If you can't afford calibration, you must abort.</strong> No exceptions - the system won't produce unreliable data.</li>
                            </ul>
                            <p className="font-semibold mt-3">
                                This is Phase 1: You must earn instrument trust before any causal exploration can begin.
                            </p>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                        <p className="font-semibold mb-2">What happens next?</p>
                        <p className="text-sm">
                            To establish instrument trust, the agent must understand: What is my budget? What does calibration cost? Can I afford it?
                        </p>
                        <p className="text-sm mt-2">
                            Let's start by understanding the physical constraints...
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 2: Understanding Budget",
            subtitle: "The physical constraint that forces hard choices",
            content: (
                <div className="space-y-4">
                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                        <p className="font-semibold mb-3 text-lg">What is "budget"?</p>
                        <p className="text-sm mb-3">In an automated lab, experiments are run in microplates - plastic trays with small wells where you culture cells and test conditions.</p>

                        <div className={`p-3 rounded ${isDarkMode ? 'bg-blue-800/30' : 'bg-blue-50'}`}>
                            <p className="text-xs mb-2">A <strong>384-well plate</strong> has 384 individual compartments arranged in a grid (16 rows × 24 columns).</p>
                            <p className="text-xs">Each well = one experimental unit where you can:</p>
                            <ul className="text-xs ml-4 mt-1 space-y-1 list-disc">
                                <li>Plate cells at a specific density</li>
                                <li>Apply a compound at a specific dose</li>
                                <li>Image and extract measurements</li>
                            </ul>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                        <p className="font-semibold mb-3">Why is budget limited?</p>
                        <p className="text-sm mb-3">Wells represent real, constrained resources:</p>
                        <ul className="ml-6 space-y-2 text-sm list-disc">
                            <li><strong>Physical capacity:</strong> You have a fixed number of plates/wells available</li>
                            <li><strong>Time:</strong> Imaging 384 wells takes hours. More wells = longer experimental cycles.</li>
                            <li><strong>Cost:</strong> Cells, reagents, compounds, and consumables cost money</li>
                            <li><strong>Opportunity cost:</strong> Wells used for calibration can't be used for biology experiments</li>
                        </ul>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                        <p className="font-semibold mb-2 text-lg">For this scenario: ~1200 wells total</p>
                        <p className="text-sm mb-3">About <strong>3 full 384-well plates</strong> worth of experimental capacity.</p>
                        <p className="text-sm">
                            This budget must cover <em>everything</em>: all calibration cycles needed to establish instrument trust,
                            plus any biological experiments we run afterward.
                        </p>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-amber-900/30 border-l-4 border-amber-500' : 'bg-amber-100 border-l-4 border-amber-600'}`}>
                        <p className="font-semibold mb-2">The hard tradeoff</p>
                        <p className="text-sm">
                            Every well spent on calibration is a well you can't use for biology. But without proper calibration,
                            any "biological data" you generate is worthless. This creates a fundamental tension in resource allocation.
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 3: Within-Run vs Between-Run Noise",
            subtitle: "Why one calibration cycle isn't enough",
            content: (
                <div className="space-y-4">
                    <p className="text-lg">
                        To truly trust an instrument, you need to understand <strong>two</strong> types of measurement noise:
                    </p>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Within-Run Noise (σ_within)</p>
                        <p className="text-sm mb-2">Variability <strong>within a single experimental cycle</strong>.</p>
                        <p className="text-sm mb-3">
                            <strong>Example:</strong> You plate 13 replicates of the same condition on one plate. They should all be identical, but they're not.
                            Some wells read 0.78, others 0.82, others 0.80. This spread is within-run noise.
                        </p>
                        <p className="text-sm font-semibold">
                            What causes it: Random variability in pipetting, cell seeding, imaging position, local microenvironment within the plate.
                        </p>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-red-900/30 border-l-4 border-red-500' : 'bg-red-100 border-l-4 border-red-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Between-Run Noise (σ_between)</p>
                        <p className="text-sm mb-2">Variability <strong>across independent experimental cycles</strong>.</p>
                        <p className="text-sm mb-3">
                            <strong>Example:</strong> You run the same calibration experiment on Day 1, Day 2, and Day 3.
                            Day 1 average = 0.80, Day 2 average = 0.85, Day 3 average = 0.78. This spread between days is between-run noise.
                        </p>
                        <p className="text-sm mb-2 font-semibold">What causes it:</p>
                        <ul className="text-sm ml-6 space-y-1 list-disc">
                            <li>Cell batch differences (passage number, genetic drift)</li>
                            <li>Environmental fluctuations (temperature, CO₂, humidity)</li>
                            <li>Reagent lot changes (media, serum, compounds)</li>
                            <li>Instrument drift (focus, illumination, calibration)</li>
                        </ul>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Total Noise = Both Combined</p>
                        <div className={`p-3 rounded mb-3 ${isDarkMode ? 'bg-purple-800/30' : 'bg-purple-50'}`}>
                            <p className="font-mono text-sm">σ_total = √(σ_within² + σ_between²)</p>
                        </div>
                        <p className="text-sm mb-3">
                            <strong>This is critical:</strong> If you only run one calibration cycle, you only measure σ_within.
                            You have <em>no idea</em> how much noise comes from between-run variability.
                        </p>
                        <p className="text-sm font-semibold">
                            Production-grade instrument trust requires measuring both. That means running multiple independent calibration cycles
                            across different days, batches, and conditions.
                        </p>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                        <p className="font-semibold mb-2">What happens next?</p>
                        <p className="text-sm">
                            The agent must design a multi-cycle calibration strategy. How many cycles? Which conditions? Can we afford it?
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 4: The Calibration Decision",
            subtitle: "Can we afford multi-cycle calibration?",
            content: (
                <div className="space-y-4">
                    <p className="text-lg mb-3">
                        The agent must decide: <strong>Can we afford full instrument trust, or must we abort?</strong>
                    </p>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-amber-900/30 border-l-4 border-amber-500' : 'bg-amber-100 border-l-4 border-amber-600'}`}>
                        <p className="font-semibold mb-3 text-lg">The Constraint: Multi-cycle calibration is mandatory</p>
                        <div className="text-sm space-y-3">
                            <p>
                                From Step 3, we know: Production-grade instrument trust requires measuring both σ_within AND σ_between.
                                That means running <strong>at least 4 independent calibration cycles</strong> across different days, batches, and conditions.
                            </p>
                            <p>
                                <strong>This is non-negotiable.</strong> If you only run one cycle, you're blind to between-run variability.
                                Your "calibrated" instrument could have high day-to-day noise and you'd never know.
                            </p>
                            <p className="font-semibold">
                                So the question isn't "should we run multiple cycles?" - the question is "can we afford to?"
                            </p>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                        <p className="font-semibold mb-4 text-lg">Calculating the Cost</p>

                        <div className="space-y-4">
                            <div>
                                <p className="text-sm font-semibold mb-2">Per-cycle cost breakdown:</p>
                                <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                    <p className="text-xs mb-2"><strong>Goal:</strong> Get rel_width &lt; 0.25 for each cycle</p>
                                    <p className="text-xs mb-2"><strong>Requirement:</strong> ~140 degrees of freedom per cycle</p>
                                    <p className="text-xs mb-3"><strong>Design:</strong> Dose-response curve with high replication</p>

                                    <div className="space-y-1 text-xs">
                                        <p>• 12 dose levels (for dose-response curve across measurement range)</p>
                                        <p>• 13 replicates per dose (to get tight within-dose variance estimate)</p>
                                        <p>• df = (13 - 1) replicates × 12 doses = <strong>144 ✓</strong></p>
                                        <p className="font-semibold mt-2">→ Cost per cycle: <strong>12 × 13 = 156 wells</strong></p>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <p className="text-sm font-semibold mb-2">Multi-cycle calibration plan:</p>
                                <div className={`p-4 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                    <div className="space-y-2 text-xs">
                                        <div className="flex items-start gap-2">
                                            <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-[10px]">1</div>
                                            <div className="flex-1">
                                                <p className="font-semibold">Cycle 1 (Day 1, Batch A): 156 wells</p>
                                                <p className="text-[11px] mt-1">Establishes baseline within-run noise for this configuration</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-2">
                                            <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-[10px]">2</div>
                                            <div className="flex-1">
                                                <p className="font-semibold">Cycle 2 (Day 2, Batch A, same cells): 156 wells</p>
                                                <p className="text-[11px] mt-1">Tests day-to-day environmental variability (temperature, humidity, instrument drift)</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-2">
                                            <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-[10px]">3</div>
                                            <div className="flex-1">
                                                <p className="font-semibold">Cycle 3 (Day 3, Batch B, new cell batch): 156 wells</p>
                                                <p className="text-[11px] mt-1">Tests batch-to-batch cell variability (different passage number, genetic drift)</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-2">
                                            <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0 text-[10px]">4</div>
                                            <div className="flex-1">
                                                <p className="font-semibold">Cycle 4 (Day 7, Batch A): 156 wells</p>
                                                <p className="text-[11px] mt-1">Tests temporal stability (longer-term instrument drift, reagent degradation)</p>
                                            </div>
                                        </div>
                                    </div>

                                    <div className={`mt-3 pt-3 border-t ${isDarkMode ? 'border-slate-600' : 'border-zinc-200'}`}>
                                        <p className="text-xs font-semibold">Total calibration cost: <strong>4 cycles × 156 wells = 624 wells</strong></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-blue-100 border-l-4 border-blue-600'}`}>
                        <p className="font-semibold mb-3 text-lg">Budget Check: Can we afford it?</p>
                        <div className="space-y-3 text-sm">
                            <div className={`p-3 rounded ${isDarkMode ? 'bg-blue-800/30' : 'bg-blue-50'}`}>
                                <p className="mb-2"><strong>Available budget:</strong> 1200 wells</p>
                                <p className="mb-2"><strong>Calibration cost:</strong> 624 wells</p>
                                <p className="mt-3 font-semibold">1200 ≥ 624? <span className="text-green-600 dark:text-green-400">YES ✓</span></p>
                            </div>

                            <p className="font-semibold text-green-600 dark:text-green-400">
                                ✓ Decision: Proceed with multi-cycle calibration
                            </p>

                            <p>
                                We have enough budget to run all 4 calibration cycles and establish full instrument trust.
                            </p>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-red-900/30 border-l-4 border-red-500' : 'bg-red-100 border-l-4 border-red-600'}`}>
                        <p className="font-semibold mb-3 text-lg">What if budget were only 500 wells?</p>
                        <div className="space-y-2 text-sm">
                            <p className="mb-2">
                                <strong>Calibration cost:</strong> 624 wells<br/>
                                <strong>Available budget:</strong> 500 wells
                            </p>
                            <p className="font-semibold text-red-600 dark:text-red-400">
                                ✗ Decision: ABORT
                            </p>
                            <p>
                                500 &lt; 624 → Cannot afford full multi-cycle calibration → Cannot establish instrument trust →
                                Any "biological data" would be unreliable.
                            </p>
                            <p className="mt-3 font-semibold">
                                The system refuses to proceed. This is epistemic honesty: if you can't afford to do it right, don't do it at all.
                            </p>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                        <p className="font-semibold mb-2">Key insight: Pay-for-calibration as forcing function</p>
                        <p className="text-sm">
                            This isn't just "use more replicates" - it's an <strong>economic constraint that enforces epistemic rigor</strong>.
                            The high cost of proper calibration (50%+ of budget) forces you to invest in reliability before you can make any knowledge claims.
                            This is how you build a knowledge moat: every bit of data is trustworthy, compounding into a fortress your competitors can't replicate.
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 5: Running the Multi-Cycle Calibration",
            subtitle: "Execute the 4-cycle calibration plan",
            content: (
                <div className="space-y-4">
                    <p className="text-lg mb-3">
                        The agent executes the calibration plan: 4 independent experimental cycles over 7 days.
                    </p>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                        <div className="mb-4">
                            <div className="text-sm font-semibold text-zinc-500 mb-3">What calibration needs</div>
                            <div className="space-y-4">
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0">1</div>
                                    <div className="flex-1">
                                        <div className="font-semibold mb-2">High statistical power</div>
                                        <div className="text-sm text-zinc-600 dark:text-zinc-400 mb-2">
                                            Goal: Get <code className="px-1 bg-black/20 rounded">rel_width &lt; 0.25</code>
                                        </div>
                                        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                            <div className="text-xs font-semibold mb-1">What is rel_width?</div>
                                            <div className="text-xs space-y-1">
                                                <p><strong>rel_width = (confidence interval width) / (measured signal)</strong></p>
                                                <p>It measures uncertainty <em>relative to</em> what you're measuring.</p>
                                                <p className="mt-2"><strong>Example:</strong> If you measure cell survival = 0.80 ± 0.10:</p>
                                                <p className="ml-3">• Confidence interval width = 2 × 0.10 = 0.20</p>
                                                <p className="ml-3">• rel_width = 0.20 / 0.80 = <strong>0.25</strong></p>
                                                <p className="mt-2 text-amber-600 dark:text-amber-400">
                                                    <strong>Why 0.25 matters:</strong> At this threshold, you can distinguish a 20% biological effect from noise.
                                                    Below this, confidence intervals are narrow enough for biology.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0">2</div>
                                    <div className="flex-1">
                                        <div className="font-semibold mb-2">Need ~140 degrees of freedom</div>
                                        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                            <div className="text-xs font-semibold mb-1">What are degrees of freedom?</div>
                                            <div className="text-xs space-y-1">
                                                <p><strong>Degrees of freedom (df)</strong> = number of independent measurements that go into computing noise.</p>
                                                <p className="mt-2"><strong>Why ~140 df?</strong></p>
                                                <p className="ml-3">• More df → narrower confidence interval → lower rel_width</p>
                                                <p className="ml-3">• To get rel_width &lt; 0.25, empirically need df ≥ 140</p>
                                                <p className="ml-3">• This is determined by the t-distribution statistics</p>
                                                <p className="mt-2 text-blue-600 dark:text-blue-400">
                                                    <strong>Translation:</strong> You need about 140+ independent measurements to be confident
                                                    enough in your noise estimate to make biological claims.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0">3</div>
                                    <div className="flex-1">
                                        <div className="font-semibold mb-2">Design an experiment that gets 140 df</div>
                                        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                            <div className="text-xs space-y-1">
                                                <p><strong>Solution: Dose-response curve with high replication</strong></p>
                                                <p className="mt-2">• Choose 12 dose levels of a well-characterized compound (Staurosporine)</p>
                                                <p>• Use 13 replicates per dose level</p>
                                                <p>• <strong>df = (replicates - 1) × dose_levels = (13 - 1) × 12 = 144 ✓</strong></p>
                                                <p className="mt-2">• Total wells needed: 12 × 13 = <strong>156 wells</strong></p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold flex-shrink-0">4</div>
                                    <div className="flex-1">
                                        <div className="font-semibold mb-2">Check if we can afford it</div>
                                        <div className={`p-3 rounded ${isDarkMode ? 'bg-slate-700' : 'bg-white'}`}>
                                            <div className="text-xs space-y-1">
                                                <p>• <strong>Cost:</strong> 156 wells</p>
                                                <p>• <strong>Available budget:</strong> 384 wells</p>
                                                <p className="mt-2 text-green-600 dark:text-green-400 font-semibold">
                                                    ✓ 384 &gt; 156 — We can afford calibration!
                                                </p>
                                                <p className="mt-2 text-xs text-zinc-500">
                                                    <strong>If budget were only 100 wells:</strong> Can't get 140 df → can't reach rel_width &lt; 0.25
                                                    → would be forced to abort rather than produce unreliable data.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                        <p className="font-semibold mb-2">✓ Decision: Run calibration experiment</p>
                        <p className="text-sm">
                            Budget (384) &gt; Cost (156) → The agent has enough resources to achieve statistical confidence. Proceed!
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 3: Running the Experiment",
            subtitle: "Execute calibration and measure noise",
            content: (
                <div className="space-y-4">
                    <div className={`p-6 rounded-lg border-2 ${isDarkMode ? 'bg-blue-900/20 border-blue-500' : 'bg-blue-50 border-blue-500'}`}>
                        <div className="flex items-start gap-4">
                            <div className="text-4xl">🔬</div>
                            <div className="flex-1">
                                <div className="font-bold text-xl mb-3">Executing: calibrate_noise_sigma</div>
                                <div className="space-y-2 text-sm">
                                    <div>• Plate 384 wells with HEK293 cells</div>
                                    <div>• Apply Staurosporine at 12 dose levels</div>
                                    <div>• Incubate 24 hours</div>
                                    <div>• Image all wells (morphology readout)</div>
                                    <div>• Extract morphology features</div>
                                    <div>• Compute pooled noise estimate</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                        <div className="text-sm font-semibold text-zinc-500 mb-3">Results</div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-xs text-zinc-500">Pooled σ</div>
                                <div className="text-2xl font-mono font-bold">0.18</div>
                            </div>
                            <div>
                                <div className="text-xs text-zinc-500">Mean Signal</div>
                                <div className="text-2xl font-mono font-bold">0.82</div>
                            </div>
                            <div>
                                <div className="text-xs text-zinc-500">Degrees of Freedom</div>
                                <div className="text-2xl font-mono font-bold">140</div>
                            </div>
                            <div>
                                <div className="text-xs text-zinc-500">Computed rel_width</div>
                                <div className="text-2xl font-mono font-bold text-green-600">0.22</div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-green-900/30 border-l-4 border-green-500' : 'bg-green-100 border-l-4 border-green-600'}`}>
                        <p className="font-semibold mb-2">✓ Success: rel_width = 0.22 &lt; 0.25 threshold</p>
                        <p className="text-sm">
                            The confidence interval is narrow enough. The agent has earned statistical confidence!
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "Step 4: Gate Earned",
            subtitle: "System now has permission to act",
            content: (
                <div className="space-y-4">
                    <p className="text-lg">
                        The agent crossed the threshold. It can now make reliable biological measurements.
                    </p>

                    <div className={`p-6 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                        <div className="text-sm font-semibold text-zinc-500 mb-3">State Changes</div>
                        <div className="space-y-4">
                            <div className="flex items-center gap-4">
                                <div className="flex-1">
                                    <div className="text-xs text-zinc-500">Regime</div>
                                    <div className="font-mono text-lg">
                                        <span className="text-orange-600">pre_gate</span>
                                        <span className="mx-2">→</span>
                                        <span className="text-green-600">in_gate</span>
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="flex-1">
                                    <div className="text-xs text-zinc-500">Budget</div>
                                    <div className="font-mono text-lg">
                                        384 <span className="text-red-600">-156</span> = 228 wells remaining
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="flex-1">
                                    <div className="text-xs text-zinc-500">Gate Slack</div>
                                    <div className="font-mono text-lg text-green-600">
                                        +0.03 (comfortable margin)
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-purple-900/30 border-l-4 border-purple-500' : 'bg-purple-100 border-l-4 border-purple-600'}`}>
                        <p className="font-semibold mb-2">What happens next?</p>
                        <p className="text-sm">
                            The agent can now run biological experiments - dose-response curves, biomarker assays, condition testing -
                            as long as noise stays below 0.40 (exit threshold). If noise drifts too high, the gate is revoked and recalibration is required.
                        </p>
                    </div>
                </div>
            ),
        },
        {
            title: "What You Just Learned",
            subtitle: "Key principles of the epistemic agent",
            content: (
                <div className="space-y-4">
                    <div className="space-y-3">
                        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                            <div className="font-semibold mb-2">🎯 Pay-for-calibration</div>
                            <p className="text-sm">
                                The system must earn statistical confidence before acting. No free passes.
                            </p>
                        </div>

                        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                            <div className="font-semibold mb-2">🚪 Gate thresholds</div>
                            <p className="text-sm">
                                Enter gate at rel_width &lt; 0.25, exit at rel_width &gt; 0.40. These encode reliability requirements.
                            </p>
                        </div>

                        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                            <div className="font-semibold mb-2">🛑 Aborts are features</div>
                            <p className="text-sm">
                                If budget is too low to calibrate, the system aborts. This is transparency, not failure.
                            </p>
                        </div>

                        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-slate-800' : 'bg-zinc-100'}`}>
                            <div className="font-semibold mb-2">📊 Regimes are epistemic states</div>
                            <p className="text-sm">
                                pre_gate = "I can't make claims", in_gate = "I can make claims", gate_revoked = "I lost calibration"
                            </p>
                        </div>
                    </div>

                    <div className={`mt-6 p-6 rounded-lg ${isDarkMode ? 'bg-blue-900/30 border-2 border-blue-500' : 'bg-blue-100 border-2 border-blue-600'}`}>
                        <p className="font-semibold text-lg mb-3">Ready to explore real runs?</p>
                        <p className="text-sm mb-4">
                            Now you can explore actual epistemic agent runs and see how these principles play out in practice.
                        </p>
                        <button
                            onClick={() => setShowTutorial(false)}
                            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors"
                        >
                            Explore Real Runs →
                        </button>
                    </div>
                </div>
            ),
        },
    ];

    const currentStep = tutorialSteps[tutorialStep];

    return (
        <div
            className={`min-h-screen transition-colors duration-300 ${
                isDarkMode ? 'bg-gradient-to-b from-slate-900 to-slate-800' : 'bg-gradient-to-b from-zinc-50 to-white'
            }`}
        >
            {/* Header */}
            <div
                className={`backdrop-blur-sm border-b sticky top-0 z-50 transition-colors duration-300 ${
                    isDarkMode ? 'bg-slate-800/80 border-slate-700' : 'bg-white/80 border-zinc-200'
                }`}
            >
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <button
                                onClick={() => navigate('/')}
                                className={`transition-colors text-sm mb-2 flex items-center gap-1 ${
                                    isDarkMode ? 'text-slate-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'
                                }`}
                            >
                                ← Back to Home
                            </button>
                            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                Epistemic Agent Tutorial
                            </h1>
                        </div>

                        {/* Dark Mode Toggle */}
                        <button
                            onClick={() => setIsDarkMode(!isDarkMode)}
                            className={`p-2 rounded-lg transition-all ${
                                isDarkMode
                                    ? 'bg-slate-700 hover:bg-slate-600 text-yellow-400'
                                    : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
                            }`}
                        >
                            {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Tutorial Content */}
            {showTutorial && (
                <div className="container mx-auto px-6 py-12">
                    <div className="max-w-4xl mx-auto">
                        {/* Progress Indicator */}
                        <div className="flex items-center justify-center gap-2 mb-12">
                            {tutorialSteps.map((_, idx) => (
                                <div
                                    key={idx}
                                    className={`h-2 rounded-full transition-all ${
                                        idx === tutorialStep
                                            ? 'w-12 bg-blue-600'
                                            : idx < tutorialStep
                                            ? 'w-8 bg-green-500'
                                            : 'w-8 bg-zinc-300'
                                    }`}
                                />
                            ))}
                        </div>

                        {/* Step Content */}
                        <div className={`rounded-xl shadow-2xl overflow-hidden ${isDarkMode ? 'bg-slate-800' : 'bg-white'}`}>
                            <div className={`p-8 border-b ${isDarkMode ? 'border-slate-700 bg-slate-700/50' : 'border-zinc-200 bg-zinc-50'}`}>
                                <div className="text-sm font-semibold text-blue-600 mb-2">
                                    STEP {tutorialStep + 1} OF {tutorialSteps.length}
                                </div>
                                <h2 className={`text-3xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                                    {currentStep.title}
                                </h2>
                                <p className={`text-lg ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                                    {currentStep.subtitle}
                                </p>
                            </div>

                            <div className={`p-8 ${isDarkMode ? 'text-slate-300' : 'text-zinc-700'}`}>
                                {currentStep.content}
                            </div>

                            {/* Navigation */}
                            <div className={`p-6 border-t flex items-center justify-between ${isDarkMode ? 'border-slate-700 bg-slate-900/50' : 'border-zinc-200 bg-zinc-50'}`}>
                                <button
                                    onClick={() => setTutorialStep(Math.max(0, tutorialStep - 1))}
                                    disabled={tutorialStep === 0}
                                    className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                                        tutorialStep === 0
                                            ? 'opacity-50 cursor-not-allowed bg-zinc-300 text-zinc-500'
                                            : isDarkMode
                                            ? 'bg-slate-700 hover:bg-slate-600 text-white'
                                            : 'bg-zinc-200 hover:bg-zinc-300 text-zinc-900'
                                    }`}
                                >
                                    ← Previous
                                </button>

                                {tutorialStep < tutorialSteps.length - 1 ? (
                                    <button
                                        onClick={() => setTutorialStep(tutorialStep + 1)}
                                        className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
                                    >
                                        Next
                                        <ChevronRight className="h-5 w-5" />
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => setShowTutorial(false)}
                                        className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
                                    >
                                        Explore Real Runs
                                        <Play className="h-5 w-5" />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Real Runs Explorer (shown after tutorial) */}
            {!showTutorial && (
                <div className="container mx-auto px-6 py-12">
                    <div className="max-w-4xl mx-auto text-center">
                        <h2 className={`text-2xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-zinc-900'}`}>
                            Run Explorer Coming Soon
                        </h2>
                        <p className={`mb-6 ${isDarkMode ? 'text-slate-400' : 'text-zinc-600'}`}>
                            This is where you'll be able to explore real epistemic agent runs
                        </p>
                        <button
                            onClick={() => {
                                setShowTutorial(true);
                                setTutorialStep(0);
                            }}
                            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors"
                        >
                            Restart Tutorial
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default EpistemicProvenancePage;
