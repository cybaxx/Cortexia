import { useCortexStore } from '@/store/cortex';
import { getUseCase, USE_CASES, type UseCaseId } from '@/data/useCases';
import { CITY_PRESETS } from '@/data/cities';
import { Loader2, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const PHASE_COPY: Record<string, string> = {
  initializing: 'Initializing agents…',
  propagating: 'Propagating signal…',
  report: 'Generating report…',
};

const VariantSelect = () => {
  const selected = useCortexStore((s) => s.selectedMemo);
  const setMemo = useCortexStore((s) => s.setMemo);
  const running = useCortexStore(
    (s) => s.injectPhase === 'initializing' || s.injectPhase === 'propagating' || s.injectPhase === 'report',
  );
  return (
    <div>
      <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted mb-1.5">Inject this variant</div>
      <div className="grid grid-cols-2 gap-1.5">
        {(
          [
            { id: 'A' as const, cls: 'border-pastel-1/35 text-pastel-1' },
            { id: 'B' as const, cls: 'border-pastel-3/35 text-pastel-3' },
          ] as const
        ).map(({ id, cls }) => {
          const isSel = selected === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => !running && setMemo(id)}
              disabled={running}
              className={`rounded-sm border bg-bg-elevated px-2 py-2 font-mono text-[11px] font-medium transition-colors ${
                isSel ? `${cls} ring-1 ring-pastel-2/30` : 'border-white/[0.08] text-text-secondary hover:border-white/[0.14]'
              } ${running ? 'opacity-50 pointer-events-none' : ''}`}
            >
              Catalyst {id}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export const ScenarioInjector = () => {
  const useCase = useCortexStore((s) => s.useCase);
  const setUseCase = useCortexStore((s) => s.setUseCase);
  const cityId = useCortexStore((s) => s.cityId);
  const setCityId = useCortexStore((s) => s.setCityId);
  const catalystA = useCortexStore((s) => s.catalystA);
  const catalystB = useCortexStore((s) => s.catalystB);
  const setCatalystA = useCortexStore((s) => s.setCatalystA);
  const setCatalystB = useCortexStore((s) => s.setCatalystB);
  const sourceUrl = useCortexStore((s) => s.sourceUrl);
  const setSourceUrl = useCortexStore((s) => s.setSourceUrl);

  const def = getUseCase(useCase);
  const startInject = useCortexStore((s) => s.startInject);
  const resetSandbox = useCortexStore((s) => s.resetSandbox);
  const setScreen = useCortexStore((s) => s.setScreen);
  const status = useCortexStore((s) => s.status);
  const memo = useCortexStore((s) => s.selectedMemo);
  const phase = useCortexStore((s) => s.injectPhase);

  const running = phase === 'initializing' || phase === 'propagating' || phase === 'report';
  const canClick = memo && (phase === 'idle' || phase === 'complete') && !running;
  const textLen = (memo === 'A' ? catalystA : memo === 'B' ? catalystB : '').trim().length;
  const canRun = canClick && textLen >= 12;

  return (
    <aside className="absolute top-12 left-0 bottom-0 w-[300px] bg-bg-surface border-r border-white/[0.08] z-20 flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.08] flex items-center justify-between gap-2 shrink-0">
        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">Catalyst configuration</h2>
          <p className="font-mono text-[9px] text-text-muted mt-1">
            {def ? <span className="text-pastel-2/90">{def.label}</span> : 'Select a domain on the home screen'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setScreen('useCases');
            resetSandbox();
          }}
          className="shrink-0 font-mono text-[8px] uppercase tracking-wider text-text-muted hover:text-text-secondary"
        >
          Home
        </button>
      </div>

      {def && (
        <div className="px-4 py-3 space-y-3 flex-1 min-h-0 overflow-y-auto">
          <div className="space-y-1.5">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Domain</Label>
            <Select
              value={useCase ?? undefined}
              onValueChange={(v) => setUseCase(v as UseCaseId)}
              disabled={running}
            >
              <SelectTrigger className="h-9 bg-bg-elevated border-white/[0.08] text-[12px] text-text-primary">
                <SelectValue placeholder="Domain" />
              </SelectTrigger>
              <SelectContent className="bg-bg-surface border-white/[0.1] max-h-64">
                {USE_CASES.map((u) => (
                  <SelectItem key={u.id} value={u.id} className="text-[12px]">
                    {u.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Target city</Label>
            <Select value={cityId} onValueChange={setCityId} disabled={running}>
              <SelectTrigger className="h-9 bg-bg-elevated border-white/[0.08] text-[12px] text-text-primary">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-bg-surface border-white/[0.1] max-h-64">
                {CITY_PRESETS.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-[12px]">
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <VariantSelect />

          <div className="space-y-2">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-pastel-1/90">Catalyst A</Label>
            <Textarea
              value={catalystA}
              onChange={(e) => setCatalystA(e.target.value)}
              disabled={running}
              placeholder="Message draft, article excerpt, or internal brief. Minimum 12 characters for the active variant when you inject."
              className="min-h-[96px] text-[12px] leading-relaxed bg-bg-elevated/80 border-white/[0.08] text-text-primary placeholder:text-text-muted/70 resize-y"
            />
            <Label className="font-mono text-[9px] uppercase tracking-wider text-pastel-3/90">Catalyst B</Label>
            <Textarea
              value={catalystB}
              onChange={(e) => setCatalystB(e.target.value)}
              disabled={running}
              placeholder="Alternative framing, counter-message, or stress-test copy for comparison."
              className="min-h-[96px] text-[12px] leading-relaxed bg-bg-elevated/80 border-white/[0.08] text-text-primary placeholder:text-text-muted/70 resize-y"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Source URL (optional)</Label>
            <Input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              disabled={running}
              placeholder="https://…"
              className="h-9 text-[12px] bg-bg-elevated/80 border-white/[0.08] text-text-primary"
            />
          </div>
        </div>
      )}

      <div className="px-4 py-3 border-t border-white/[0.08] shrink-0">
        <motion.button
          type="button"
          onClick={() => startInject()}
          disabled={!canRun || !def}
          className="w-full relative overflow-hidden rounded-md font-mono text-[12px] font-semibold uppercase tracking-[0.12em] py-3.5 px-3 text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-shadow shadow-lg"
          style={{
            background: 'linear-gradient(135deg, hsl(var(--pastel-2) / 0.45) 0%, hsl(var(--pastel-1) / 0.35) 50%, hsl(var(--pastel-3) / 0.3) 100%)',
            boxShadow: '0 12px 32px hsl(var(--pastel-2) / 0.12)',
          }}
          whileHover={canRun && def ? { scale: 1.01 } : {}}
          whileTap={canRun && def ? { scale: 0.99 } : {}}
        >
          <span className="absolute inset-0 bg-gradient-to-t from-white/0 to-white/5 pointer-events-none" />
          <span className="relative flex items-center justify-center gap-2">
            <AnimatePresence mode="wait">
              {running ? (
                <motion.span
                  key="load"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  {PHASE_COPY[phase] ?? 'Working…'}
                </motion.span>
              ) : (
                <motion.span
                  key="go"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  Inject catalyst
                </motion.span>
              )}
            </AnimatePresence>
          </span>
        </motion.button>

        <p className="mt-2 font-mono text-[8px] text-text-muted text-center min-h-[2.5em]">
          {running ? (
            <span className="text-pastel-2/90">
              {phase === 'initializing' && 'Resolving agent graph and BSV baselines for the selected city…'}
              {phase === 'propagating' && 'Routing signal through the synthetic population; map updates in real time…'}
              {phase === 'report' && 'Composing report: resistance hotspots, drivers, and predicted lift…'}
            </span>
          ) : (
            <>
              Selected:{' '}
              <span className="text-text-secondary">Catalyst {memo ?? '—'}</span>
              {memo && (
                <>
                  {' '}
                  · {textLen}/12+ characters
                </>
              )}
            </>
          )}
        </p>

        <button
          type="button"
          onClick={() => resetSandbox()}
          disabled={running}
          className="mt-1 w-full font-mono text-[10px] uppercase tracking-[0.1em] py-2 rounded-sm bg-bg-elevated text-text-secondary border border-white/[0.06] hover:border-white/[0.14] transition-colors disabled:opacity-40"
        >
          Reset sandbox
        </button>
        <div className="mt-2 font-mono text-[8px] text-text-muted text-center">
          Engine: <span className="text-text-secondary">{status}</span>
        </div>
      </div>
    </aside>
  );
};
