import React, { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Sparkles,
  Scissors,
  FlaskConical,
  Microscope,
  Sigma,
  Target,
  RefreshCw,
  Pause,
  Play,
} from "lucide-react";

/**
 * Cell Autonomous Science Loop (React)
 *
 * Visual intent:
 * - a ratchet, not a carousel
 * - memoryful world model that deforms over time
 * - constrained imagination (branches collapse)
 * - gritty, irreversible execution (noise, loss)
 * - measurement as projection/compression
 * - reconciliation + belief update
 * - reward as subtle persistent glow
 */

type StageKey =
  | "world"
  | "question"
  | "proposal"
  | "execute"
  | "measure"
  | "update"
  | "reward";

const STAGES: Array<{
  key: StageKey;
  title: string;
  subtitle: string;
  Icon: React.ComponentType<any>;
}> = [
  {
    key: "world",
    title: "World model",
    subtitle: "Belief state + uncertainty",
    Icon: Brain,
  },
  {
    key: "question",
    title: "Question selection",
    subtitle: "Where is ignorance most valuable?",
    Icon: Target,
  },
  {
    key: "proposal",
    title: "Constrained proposal",
    subtitle: "Imagination under constraints",
    Icon: Scissors,
  },
  {
    key: "execute",
    title: "Execution",
    subtitle: "Irreversibility, loss, time",
    Icon: FlaskConical,
  },
  {
    key: "measure",
    title: "Measurement",
    subtitle: "Projection of state",
    Icon: Microscope,
  },
  {
    key: "update",
    title: "Reconciliation",
    subtitle: "Deform beliefs, detect failure",
    Icon: Sigma,
  },
  {
    key: "reward",
    title: "Reward",
    subtitle: "Epistemic gain (quiet glow)",
    Icon: Sparkles,
  },
];

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-700 shadow-sm">
      {children}
    </span>
  );
}

function SoftToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!value)}
      className="group inline-flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm shadow-sm transition hover:shadow"
      type="button"
    >
      <span className="h-5 w-9 rounded-full bg-zinc-200 p-[2px]">
        <motion.span
          className="block h-4 w-4 rounded-full bg-white shadow"
          animate={{ x: value ? 16 : 0 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </span>
      <span className="text-zinc-700 group-hover:text-zinc-900">{label}</span>
    </button>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-700">{label}</span>
        <span className="text-sm tabular-nums text-zinc-900">{value.toFixed(2)}×</span>
      </div>
      <input
        className="mt-2 w-full"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function NodeCard({
  title,
  subtitle,
  Icon,
}: {
  title: string;
  subtitle: string;
  Icon: React.ComponentType<any>;
}) {
  return (
    <div className="w-full rounded-3xl border border-zinc-200 bg-white/90 p-5 shadow-sm backdrop-blur">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-2xl border border-zinc-200 bg-white p-2 shadow-sm">
          <Icon className="h-5 w-5 text-zinc-800" />
        </div>
        <div className="min-w-0">
          <div className="text-base font-semibold text-zinc-900">{title}</div>
          <div className="mt-0.5 text-sm text-zinc-600">{subtitle}</div>
        </div>
      </div>
    </div>
  );
}

function blobPath(cx: number, cy: number, r: number, wobble: number, phase: number) {
  const pts = 9;
  const a0 = -Math.PI / 2;
  const coords: Array<{ x: number; y: number }> = [];
  for (let i = 0; i < pts; i++) {
    const a = a0 + (i / pts) * Math.PI * 2;
    const rr = r * (1 + wobble * Math.sin(i * 1.6 + phase));
    coords.push({ x: cx + rr * Math.cos(a), y: cy + rr * Math.sin(a) });
  }
  let d = `M ${coords[0].x} ${coords[0].y}`;
  for (let i = 0; i < pts; i++) {
    const p1 = coords[(i + 1) % pts];
    const p2 = coords[(i + 2) % pts];
    const cx1 = (p1.x + p2.x) / 2;
    const cy1 = (p1.y + p2.y) / 2;
    d += ` Q ${p1.x} ${p1.y} ${cx1} ${cy1}`;
  }
  d += " Z";
  return d;
}

function useTimings(speed: number) {
  // Per-stage base duration (seconds). Scale by 1/speed.
  const base: Record<StageKey, number> = {
    world: 2.4,
    question: 1.7,
    proposal: 2.0,
    execute: 2.2,
    measure: 2.0,
    update: 2.4,
    reward: 1.6,
  };

  const durations = STAGES.map((s) => base[s.key] / speed);
  const total = durations.reduce((a, b) => a + b, 0);
  const cum = durations.reduce<number[]>((acc, d) => {
    const last = acc.length ? acc[acc.length - 1] : 0;
    acc.push(last + d);
    return acc;
  }, []);

  return { durations, total, cum };
}

function stageIndexAt(t: number, cum: number[]) {
  const idx = cum.findIndex((c) => t <= c);
  return Math.max(0, idx === -1 ? cum.length - 1 : idx);
}

export default function CellAutonomousScienceLoop() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [speed, setSpeed] = useState(1.0);
  const [showScars, setShowScars] = useState(true);
  const [showConstraints, setShowConstraints] = useState(true);

  const { total } = useTimings(speed);

  const [epoch, setEpoch] = useState(0);

  const size = 520;
  const cx = size / 2;
  const cy = size / 2;
  const ringR = 168;

  const scars = useMemo(() => {
    const n = Math.min(12, epoch);
    return Array.from({ length: n }).map((_, i) => {
      const a = (i / Math.max(1, n)) * Math.PI * 2 - Math.PI / 2;
      const r = ringR + 18 + (i % 2) * 6;
      return {
        x: cx + r * Math.cos(a),
        y: cy + r * Math.sin(a),
        i,
      };
    });
  }, [epoch, cx, cy, ringR]);

  return (
    <div className="w-full">
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-2xl font-semibold text-zinc-950">
              Cell autonomous science loop
            </div>
            <div className="mt-1 max-w-2xl text-sm text-zinc-600">
              Not a circle. A ratchet. Memory persists, proposals prune, execution is lossy,
              measurement compresses, and learning leaves scars.
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge>belief state</Badge>
              <Badge>uncertainty</Badge>
              <Badge>constraints</Badge>
              <Badge>irreversibility</Badge>
              <Badge>projection</Badge>
              <Badge>epistemic gain</Badge>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setIsPlaying((v) => !v)}
              className="inline-flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm shadow-sm transition hover:shadow"
            >
              {isPlaying ? (
                <>
                  <Pause className="h-4 w-4" /> Pause
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" /> Play
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setEpoch((e) => e + 1)}
              className="inline-flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm shadow-sm transition hover:shadow"
              title="Simulate accumulation of scars across loops"
            >
              <RefreshCw className="h-4 w-4" /> Next epoch
            </button>

            <Slider
              label="Speed"
              value={speed}
              min={0.6}
              max={1.8}
              step={0.05}
              onChange={setSpeed}
            />

            <SoftToggle label="Scars" value={showScars} onChange={setShowScars} />
            <SoftToggle
              label="Constraints"
              value={showConstraints}
              onChange={setShowConstraints}
            />
          </div>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <div className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-gradient-to-b from-white to-zinc-50 p-4 shadow-sm">
              <LoopViz
                size={size}
                cx={cx}
                cy={cy}
                ringR={ringR}
                total={total}
                isPlaying={isPlaying}
                showScars={showScars}
                scars={scars}
                showConstraints={showConstraints}
              />
            </div>
          </div>

          <div className="lg:col-span-5">
            <StagePanel total={total} isPlaying={isPlaying} speed={speed} />
          </div>
        </div>
      </div>
    </div>
  );
}

function LoopViz(props: {
  size: number;
  cx: number;
  cy: number;
  ringR: number;
  total: number;
  isPlaying: boolean;
  showScars: boolean;
  scars: Array<{ x: number; y: number; i: number }>;
  showConstraints: boolean;
}) {
  const { size, cx, cy, ringR, total, isPlaying, showScars, scars, showConstraints } = props;

  return (
    <div className="relative">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="block">
        <defs>
          <filter id="soft" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feColorMatrix
              in="blur"
              type="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.65 0"
              result="soft"
            />
            <feMerge>
              <feMergeNode in="soft" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="centerFade" cx="50%" cy="50%" r="55%">
            <stop offset="0%" stopColor="rgba(0,0,0,0.04)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0)" />
          </radialGradient>
        </defs>

        <circle cx={cx} cy={cy} r={ringR} fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth={2} />
        <circle cx={cx} cy={cy} r={ringR - 68} fill="url(#centerFade)" />

        {STAGES.map((s, i) => {
          const a0 = -Math.PI / 2 + (i / STAGES.length) * Math.PI * 2;
          const a1 = -Math.PI / 2 + ((i + 1) / STAGES.length) * Math.PI * 2;
          const p0 = { x: cx + ringR * Math.cos(a0), y: cy + ringR * Math.sin(a0) };
          const p1 = { x: cx + ringR * Math.cos(a1), y: cy + ringR * Math.sin(a1) };
          const large = a1 - a0 > Math.PI ? 1 : 0;
          const d = `M ${p0.x} ${p0.y} A ${ringR} ${ringR} 0 ${large} 1 ${p1.x} ${p1.y}`;
          return (
            <path
              key={s.key}
              d={d}
              fill="none"
              stroke="rgba(0,0,0,0.06)"
              strokeWidth={10}
              strokeLinecap="round"
            />
          );
        })}

        {showScars &&
          scars.map((m) => (
            <g key={m.i} opacity={0.7}>
              <circle cx={m.x} cy={m.y} r={2.5} fill="rgba(0,0,0,0.18)" />
              <path
                d={`M ${m.x - 10} ${m.y} L ${m.x + 10} ${m.y}`}
                stroke="rgba(0,0,0,0.12)"
                strokeWidth={1.4}
                strokeLinecap="round"
              />
            </g>
          ))}

        {showConstraints && (
          <g opacity={0.6}>
            {Array.from({ length: 6 }).map((_, i) => {
              const a = -Math.PI / 2 + (i / 6) * Math.PI * 2;
              const r0 = ringR - 110;
              const r1 = ringR - 48;
              const x0 = cx + r0 * Math.cos(a);
              const y0 = cy + r0 * Math.sin(a);
              const x1 = cx + r1 * Math.cos(a);
              const y1 = cy + r1 * Math.sin(a);
              return (
                <path
                  key={i}
                  d={`M ${x0} ${y0} L ${x1} ${y1}`}
                  stroke="rgba(0,0,0,0.06)"
                  strokeWidth={1}
                />
              );
            })}
            <circle cx={cx} cy={cy} r={ringR - 92} fill="none" stroke="rgba(0,0,0,0.06)" />
          </g>
        )}

        {/* World model deformation */}
        <motion.path
          d={blobPath(cx, cy, ringR - 86, 0.12, 0.0)}
          fill="rgba(0,0,0,0.05)"
          animate={{
            d: [
              blobPath(cx, cy, ringR - 86, 0.10, 0.0),
              blobPath(cx, cy, ringR - 86, 0.22, 1.2),
              blobPath(cx, cy, ringR - 86, 0.14, 2.4),
            ],
          }}
          transition={{ duration: total * 0.6, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* Proposal pruning branches */}
        <AnimatePresence>
          <motion.g
            key="prune"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {Array.from({ length: 9 }).map((_, k) => {
              const a = -Math.PI / 2 + (k / 9) * Math.PI * 2;
              const r0 = ringR - 56;
              const r1 = ringR - 120 - (k % 3) * 10;
              const x0 = cx + r0 * Math.cos(a);
              const y0 = cy + r0 * Math.sin(a);
              const x1 = cx + r1 * Math.cos(a);
              const y1 = cy + r1 * Math.sin(a);
              return (
                <motion.path
                  key={k}
                  d={`M ${x0} ${y0} L ${x1} ${y1}`}
                  stroke="rgba(0,0,0,0.08)"
                  strokeWidth={1.2}
                  strokeLinecap="round"
                  initial={{ pathLength: 0.1, opacity: 0 }}
                  animate={{ pathLength: [0.15, 1, 0.35], opacity: [0, 1, 0.15] }}
                  transition={{
                    duration: 2.2,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: k * 0.05,
                  }}
                />
              );
            })}
          </motion.g>
        </AnimatePresence>

        {/* Execution grit */}
        <motion.g
          animate={{ opacity: [0.0, 0.35, 0.05] }}
          transition={{ duration: total * 0.22, repeat: Infinity, ease: "easeInOut" }}
        >
          {Array.from({ length: 70 }).map((_, i) => {
            const a = (i / 70) * Math.PI * 2;
            const r = ringR - 40 - (i % 7) * 6;
            const x = cx + r * Math.cos(a);
            const y = cy + r * Math.sin(a);
            return <circle key={i} cx={x} cy={y} r={0.8} fill="rgba(0,0,0,0.12)" />;
          })}
        </motion.g>

        {/* Measurement compression */}
        <motion.g
          animate={{ opacity: [0.0, 0.55, 0.0] }}
          transition={{ duration: total * 0.26, repeat: Infinity, ease: "easeInOut" }}
        >
          {Array.from({ length: 10 }).map((_, i) => {
            const a = -Math.PI / 2 + (i / 10) * Math.PI * 2;
            const x0 = cx + (ringR - 64) * Math.cos(a);
            const y0 = cy + (ringR - 64) * Math.sin(a);
            const x1 = cx + (ringR - 160) * Math.cos(a);
            const y1 = cy + (ringR - 160) * Math.sin(a);
            return (
              <path
                key={i}
                d={`M ${x0} ${y0} Q ${cx} ${cy} ${x1} ${y1}`}
                stroke="rgba(0,0,0,0.07)"
                strokeWidth={1.1}
                fill="none"
              />
            );
          })}
        </motion.g>

        {/* Reward glow */}
        <motion.circle
          cx={cx}
          cy={cy}
          r={ringR - 78}
          fill="none"
          stroke="rgba(0,0,0,0.08)"
          strokeWidth={14}
          filter="url(#soft)"
          animate={{ opacity: [0.12, 0.38, 0.16] }}
          transition={{ duration: total * 0.4, repeat: Infinity, ease: "easeInOut" }}
        />

        {/* Cursor */}
        <motion.g
          animate={isPlaying ? { rotate: 360 } : { rotate: 0 }}
          transition={isPlaying ? { duration: total, ease: "linear", repeat: Infinity } : undefined}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        >
          <g transform={`translate(${cx}, ${cy - ringR})`}>
            <circle r={10} fill="rgba(0,0,0,0.10)" filter="url(#soft)" />
            <circle r={7} fill="rgba(255,255,255,0.95)" />
            <circle r={3.6} fill="rgba(0,0,0,0.65)" />
          </g>
        </motion.g>

        <circle cx={cx} cy={cy} r={3.2} fill="rgba(0,0,0,0.35)" />
      </svg>

      <div className="pointer-events-none absolute inset-x-6 bottom-6">
        <div className="rounded-3xl border border-zinc-200 bg-white/80 p-4 shadow-sm backdrop-blur">
          <div className="text-sm text-zinc-700">
            Tap <span className="font-medium text-zinc-900">Next epoch</span> a few times.
            If this starts to feel more constrained and more scarred, we’re on the right track.
          </div>
        </div>
      </div>
    </div>
  );
}

function StagePanel({ total, isPlaying, speed }: { total: number; isPlaying: boolean; speed: number }) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-zinc-900">Loop state</div>
        <div className="text-xs text-zinc-600">
          {isPlaying ? "Running" : "Paused"} · {speed.toFixed(2)}×
        </div>
      </div>

      <div className="mt-4">
        <StageCardCycle total={total} />
      </div>

      <div className="mt-5 grid gap-3">
        {STAGES.map((s) => (
          <div
            key={s.key}
            className="flex items-start gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2"
          >
            <div className="mt-0.5 rounded-xl border border-zinc-200 bg-white p-1.5">
              <s.Icon className="h-4 w-4 text-zinc-800" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-zinc-900">{s.title}</div>
              <div className="text-xs text-zinc-600">{s.subtitle}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-zinc-200 bg-white p-3">
        <div className="text-xs text-zinc-600">Refinement knobs:</div>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-zinc-700">
          <li>Rename stages to match your stack (planner, scheduler, assay library, etc.)</li>
          <li>Make scars data-driven (failed runs, cost overruns, model breaks)</li>
          <li>Make pruning explicit (candidate experiments collapsing under constraints)</li>
          <li>Replace blobs with manifolds if you want it to feel more “model-y”</li>
        </ul>
      </div>
    </div>
  );
}

function StageCardCycle({ total }: { total: number }) {
  return (
    <div className="relative h-[118px]">
      {STAGES.map((s, i) => (
        <motion.div
          key={s.key}
          className="absolute inset-0"
          initial={{ opacity: i === 0 ? 1 : 0, y: 0 }}
          animate={{ opacity: [0, 1, 0], y: [6, 0, -4] }}
          transition={{
            duration: total,
            times: [
              Math.max(0, (i - 0.15) / STAGES.length),
              i / STAGES.length,
              Math.min(1, (i + 0.75) / STAGES.length),
            ],
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <NodeCard title={s.title} subtitle={s.subtitle} Icon={s.Icon} />
        </motion.div>
      ))}
    </div>
  );
}
