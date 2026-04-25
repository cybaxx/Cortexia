import { useCortexStore } from '@/store/cortex';
import { motion } from 'framer-motion';

const THINK_LINES = [
  'fMRI tensor extracted for Agent 42. Working memory bandwidth = 0.41.',
  "Agent's defensive posture is 0.82. Acoustic prosody triggered high working memory strain.",
  'Cross-referencing semantic frame against trusted-source prior (n=14).',
  'Spatial neighbors of Agent 17 show coherent skepticism cluster.',
  'Affective valence delta = -0.36 over last 4 exposures.',
  'Belief graph entropy rising in District 4. Routing to K2 reasoning core.',
];
const ACTION_LINES = [
  'Belief Rejected. Broadcasting friction to spatial neighbors.',
  'Belief Adopted with caveat. Propagating attenuated signal.',
  'Memo A re-routed through Educator subgraph.',
  'Cognitive load throttled. Agent paused 320ms.',
  'Influence arc emitted: Agent 12 → Agent 88.',
];
const INFO_LINES = [
  'Routing 1,248 agent ticks/sec.',
  'K2 cognitive router synchronized.',
  'Memo embedding vectorized (d=768).',
];

const pick = <T,>(arr: T[]) => arr[Math.floor(Math.random() * arr.length)];

export const ReasoningFeed = () => {
  const logs = useCortexStore((s) => s.logs);
  const pushLog = useCortexStore((s) => s.pushLog);

  // Seed initial logs + auto-tick
  if (logs.length === 0 && typeof window !== 'undefined') {
    setTimeout(() => {
      pushLog({ kind: 'info', text: 'K2 cognitive router online.' });
      pushLog({ kind: 'info', text: 'Synthetic population loaded: N=10,432 (LA basin).' });
      pushLog({ kind: 'think', text: pick(THINK_LINES) });
      pushLog({ kind: 'action', text: pick(ACTION_LINES) });
    }, 200);
  }

  // Tick interval
  if (typeof window !== 'undefined' && !(window as any).__cortexTick) {
    (window as any).__cortexTick = setInterval(() => {
      const r = Math.random();
      if (r < 0.5) pushLog({ kind: 'think', text: pick(THINK_LINES) });
      else if (r < 0.85) pushLog({ kind: 'action', text: pick(ACTION_LINES) });
      else pushLog({ kind: 'info', text: pick(INFO_LINES) });
    }, 1400);
  }

  return (
    <aside className="absolute top-12 right-0 bottom-16 w-[340px] bg-bg-surface border-l border-white/[0.08] z-20 flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.08]">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          IFM K2 THINK // COGNITIVE ROUTER
        </h2>
        <p className="font-mono text-[9px] text-text-muted mt-1">Sustained reasoning · live</p>
      </div>
      <div className="flex-1 overflow-y-auto cortex-scroll px-4 py-3 space-y-1.5 font-mono text-[10px] leading-relaxed">
        {logs.map((l) => (
          <motion.div
            key={l.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            <span className="text-text-muted mr-1.5">&gt;</span>
            {l.kind === 'think' && (
              <span className="text-text-secondary">
                <span className="text-text-muted">&lt;think&gt;</span> {l.text}{' '}
                <span className="text-text-muted">&lt;/think&gt;</span>
              </span>
            )}
            {l.kind === 'action' && (
              <span className="text-accent-adopt">
                <span className="opacity-70">&lt;action&gt;</span> {l.text}{' '}
                <span className="opacity-70">&lt;/action&gt;</span>
              </span>
            )}
            {l.kind === 'info' && <span className="text-text-secondary/80">{l.text}</span>}
          </motion.div>
        ))}
      </div>
    </aside>
  );
};
