# A Case for Autonomous Science at insitro

## Executive Summary

Autonomous science is not a replacement for scientists. It is a way to compound their judgment.

At insitro, we already operate at the intersection of biology, automation, and machine learning. The next step is not more throughput or more models in isolation. It is a closed loop where experimental design, execution, quality control, and learning are integrated into a single system that can reason about uncertainty, cost, and value.

This document makes the case that autonomous science is not speculative or distant. It is a pragmatic extension of how we already work. Done correctly, it improves rigor, accelerates learning, and reduces wasted effort. Done poorly, it creates noise at scale. The difference is intent and design.

## What We Mean by Autonomous Science

Autonomous science is a closed-loop experimental system that:

- Proposes experiments based on explicit objectives
- Executes them through reliable lab automation
- Measures outcomes with calibrated, variance-aware assays
- Updates beliefs using principled statistical or machine-learning models
- Chooses what to do next based on expected information gain, cost, and risk

Autonomy here is bounded and honest. Humans set goals, constraints, and values. The system handles repetition, bookkeeping, and optimization under uncertainty.

This is not a single algorithm or robot. It is an operating model.

## Why This Matters Now

insitro already has the ingredients:

- Automated and semi-automated wet labs
- Rich, high-dimensional phenotyping
- Strong machine learning and data infrastructure
- Scientists who think in systems, not single assays

What is missing is unification. Today, experiments are often optimized locally within projects. Decisions about what to run next are made implicitly, sometimes intuitively, and rarely with a shared accounting of uncertainty or opportunity cost.

Autonomous science forces those decisions into the open. It makes tradeoffs explicit and learnable.

## The Cost of the Status Quo

Without a closed loop:

- Noise is discovered late, after scale-up
- Assay drift and batch effects are corrected manually, if at all
- Similar experiments are repeated across teams with slight variations
- Learning does not compound across programs

This is not a criticism of people. It is a structural limitation of human-scale coordination.

## A Practical Definition of Success

Autonomous science should earn its place by delivering concrete outcomes:

- Faster convergence on viable hypotheses
- Earlier detection of uninformative or unstable assays
- Reproducible decision-making across time and teams
- A measurable increase in information gained per dollar and per week

If these do not materialize, the system should be questioned or shut down.

## Where to Start: Bounded Autonomy

The right starting point is not full end-to-end autonomy. It is bounded loops with clear contracts.

Examples include:

- Automated dose and time-course selection for phenotyping assays
- Adaptive allocation of replicates based on observed variance
- Early stopping rules for screens that are not behaving
- Systematic exploration of assay parameter space before scaling

Each loop should have:

- A clear objective
- A defined reward or success metric
- Known failure modes
- Human override by design

## The Role of Humans

Humans remain responsible for:

- Defining what matters biologically and clinically
- Setting ethical and strategic boundaries
- Interpreting results in context
- Deciding when to trust or distrust the system

Autonomy should remove busywork, not agency.

## Risks and How to Mitigate Them

Real risks exist:

- Automating flawed assays
- Optimizing for the wrong objective
- Creating opaque systems no one trusts

Mitigations are straightforward but non-negotiable:

- Start small and falsifiable
- Instrument variance and drift explicitly
- Make uncertainty visible, not hidden
- Treat autonomy as an experiment itself

## Why insitro Is Uniquely Positioned

insitro has a rare combination of biological ambition and technical depth. More importantly, it has lived through the pain of scaling assays and data the hard way.

Autonomous science is not a leap of faith here. It is a disciplined response to lessons already learned.

## Closing

Autonomous science is not about removing humans from discovery. It is about building systems that remember what we learned, notice when something is wrong, and help us choose better next steps.

If we do this carefully, learning compounds. If we do not, complexity wins.

The choice is design, not destiny.
