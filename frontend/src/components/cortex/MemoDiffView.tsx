import { motion } from 'framer-motion';
import { useCortexStore } from '@/store/cortex';
import { Trophy, Scale } from 'lucide-react';

export const MemoDiffView = () => {
  const memoA = useCortexStore((s) => s.memoAResult);
  const memoB = useCortexStore((s) => s.memoBResult);
  const diff = useCortexStore((s) => s.memoDiff);

  if (!memoA || !memoB || !diff) return null;

  const aWin = diff.winner === 'A';
  const bWin = diff.winner === 'B';
  const tie = diff.winner === 'tie';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="pt-2 border-t border-white/[0.1] space-y-4"
    >
      <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.16em] text-amber-400/90">
        <Scale className="h-3.5 w-3.5" />
        Memo A vs B — post hoc delta
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div
          className={`rounded-md border px-2 py-2 ${
            aWin ? 'border-emerald-500/50 bg-emerald-500/10' : 'border-white/[0.08] bg-bg-elevated/40'
          }`}
        >
          <div className="font-mono text-[8px] text-text-muted uppercase">Memo A</div>
          <div className="text-lg font-semibold text-text-primary">{memoA.report.adoptionRate}%</div>
          <div className="text-[9px] text-text-secondary">adoption</div>
        </div>
        <div
          className={`rounded-md border px-2 py-2 ${
            bWin ? 'border-emerald-500/50 bg-emerald-500/10' : 'border-white/[0.08] bg-bg-elevated/40'
          }`}
        >
          <div className="font-mono text-[8px] text-text-muted uppercase">Memo B</div>
          <div className="text-lg font-semibold text-text-primary">{memoB.report.adoptionRate}%</div>
          <div className="text-[9px] text-text-secondary">adoption</div>
        </div>
      </div>

      <div className="flex items-start gap-2 text-[11px] text-text-primary/95 leading-relaxed">
        {tie ? (
          <span>Within the model margin, both memos perform similarly on adoption — look at reach and hotspot shape for the tie-breaker.</span>
        ) : (
          <>
            <Trophy className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              <strong className="text-text-primary">Memo {aWin ? 'A' : 'B'} wins</strong> by ~{diff.marginPp} points on
              belief adoption. Driver: {diff.languageDriver}. {diff.detail}
            </span>
          </>
        )}
      </div>
    </motion.div>
  );
};
