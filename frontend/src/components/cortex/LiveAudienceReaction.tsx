import { motion, AnimatePresence } from 'framer-motion';
import { useCortexStore } from '@/store/cortex';

export const LiveAudienceReaction = () => {
  const phase = useCortexStore((s) => s.injectPhase);
  const macroResult = useCortexStore((s) => s.macroResult);
  const catalystText = useCortexStore((s) => s.catalystText);

  // Show during initializing/propagating, wait a bit for tension
  const isVisible = phase === 'initializing' || phase === 'propagating';

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-bg-deep/80 backdrop-blur-sm pointer-events-none"
        >
          {/* Center Message */}
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="z-20 max-w-2xl rounded-[36px] border border-white/[0.12] bg-bg-surface/90 p-7 text-center shadow-[0_30px_100px_rgba(8,12,20,0.45)]"
        >
            <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Your message</p>
            <h2 className="text-xl font-medium leading-relaxed text-text-primary">{catalystText}</h2>
          </motion.div>

          {/* Floating Thoughts */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            {phase === 'propagating' &&
              macroResult?.synthetic_thoughts.map((thought, i) => {
                const angle = (i * (360 / macroResult.synthetic_thoughts.length)) * (Math.PI / 180);
                const radius = 200 + Math.random() * 150;
                const tx = Math.cos(angle) * radius;
                const ty = Math.sin(angle) * radius;

                // Color mappings
                const colorClass =
                  thought.sentiment === 'negative'
                    ? 'text-pastel-3 border-pastel-3/25 bg-[hsl(var(--pastel-3)/0.08)]'
                    : thought.sentiment === 'positive'
                    ? 'text-pastel-2 border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.08)]'
                    : 'text-pastel-1 border-pastel-1/25 bg-[hsl(var(--pastel-1)/0.08)]';

                return (
                  <motion.div
                    key={`${thought.agent_id}-${i}`}
                    initial={{ opacity: 0, x: tx * 0.5, y: ty * 0.5, scale: 0.8 }}
                    animate={{ opacity: 1, x: tx, y: ty, scale: 1 }}
                    transition={{
                      delay: i * 0.1 + 0.2, // Sequentially fade in
                      duration: 0.6,
                      ease: 'easeOut',
                    }}
                    className={`absolute left-1/2 top-1/2 -ml-24 -mt-6 w-52 rounded-[24px] border p-3 text-center text-[13px] font-medium shadow-lg backdrop-blur-md ${colorClass}`}
                  >
                    "{thought.text}"
                  </motion.div>
                );
              })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
