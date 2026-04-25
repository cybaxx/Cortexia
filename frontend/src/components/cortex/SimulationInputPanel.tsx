import { useCortexStore } from '@/store/cortex';
import { getUseCase, USE_CASES, type UseCaseId } from '@/data/useCases';
import { Loader2, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CatalystInput } from './CatalystInput';
import { CitySelector } from './CitySelector';

const PHASE_COPY: Record<string, string> = {
  initializing: 'Calling Modal TRIBE and K2 Think…',
  propagating: 'Projecting results onto the map…',
  report: 'Building propagation report…',
};

/**
 * Left rail: domain, target city, catalyst text/URL, simulation modifiers, and inject action.
 */
export const SimulationInputPanel = () => {
  const useCase = useCortexStore((s) => s.useCase);
  const setUseCase = useCortexStore((s) => s.setUseCase);
  const cityId = useCortexStore((s) => s.cityId);
  const setCityId = useCortexStore((s) => s.setCityId);
  const catalystText = useCortexStore((s) => s.catalystText);
  const setCatalystText = useCortexStore((s) => s.setCatalystText);
  const sourceUrl = useCortexStore((s) => s.sourceUrl);
  const setSourceUrl = useCortexStore((s) => s.setSourceUrl);
  const messageComplexity = useCortexStore((s) => s.messageComplexity);
  const setMessageComplexity = useCortexStore((s) => s.setMessageComplexity);

  const def = getUseCase(useCase);
  const runSimulation = useCortexStore((s) => s.runSimulation);
  const resetSandbox = useCortexStore((s) => s.resetSandbox);
  const setScreen = useCortexStore((s) => s.setScreen);
  const status = useCortexStore((s) => s.status);
  const apiError = useCortexStore((s) => s.apiError);
  const phase = useCortexStore((s) => s.injectPhase);

  const running = phase === 'initializing' || phase === 'propagating' || phase === 'report';
  const canRun =
    useCase && (phase === 'idle' || phase === 'complete') && !running && catalystText.trim().length >= 12;

  return (
    <aside className="absolute bottom-4 left-4 top-16 z-20 flex w-[min(100%-1rem,22rem)] flex-col overflow-hidden rounded-[34px] border border-white/[0.12] bg-bg-surface/92 shadow-[0_26px_100px_rgba(8,12,20,0.42)]">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-white/[0.08] px-5 py-4">
        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">Input</h2>
          <p className="font-mono text-[9px] text-text-muted mt-1">
            {def ? <span className="text-pastel-2/90">{def.label}</span> : 'Select a domain from home'}
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
        <div className="cortex-scroll min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
          <div className="space-y-1.5">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Domain</Label>
            <Select
              value={useCase ?? undefined}
              onValueChange={(v) => setUseCase(v as UseCaseId)}
              disabled={running}
            >
              <SelectTrigger className="h-11 rounded-[20px] bg-bg-elevated border-white/[0.08] text-[12px] text-text-primary">
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

          <CitySelector value={cityId} onChange={setCityId} disabled={running} />

          <div className="space-y-1.5">
            <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Signal Complexity</Label>
            <Select
              value={messageComplexity === 0 ? "Simple" : messageComplexity === 0.5 ? "Realistic" : "Stress Test"}
              onValueChange={(v) => {
                  if (v === "Simple") setMessageComplexity(0);
                  else if (v === "Realistic") setMessageComplexity(0.5);
                  else if (v === "Stress Test") setMessageComplexity(1);
              }}
              disabled={running}
            >
              <SelectTrigger className="h-11 rounded-[20px] bg-bg-elevated border-white/[0.08] text-[12px] text-text-primary">
                <SelectValue placeholder="Select preset" />
              </SelectTrigger>
              <SelectContent className="bg-bg-surface border-white/[0.1]">
                <SelectItem value="Simple" className="text-[12px]">Simple</SelectItem>
                <SelectItem value="Realistic" className="text-[12px]">Realistic</SelectItem>
                <SelectItem value="Stress Test" className="text-[12px]">Stress Test</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <CatalystInput
            text={catalystText}
            onTextChange={setCatalystText}
            sourceUrl={sourceUrl}
            onSourceUrlChange={setSourceUrl}
            disabled={running}
            label="Your Message"
          />
        </div>
      )}

      <div className="shrink-0 border-t border-white/[0.08] px-5 py-4">
        {apiError && (
          <p className="mb-3 rounded-[18px] border border-pastel-3/20 bg-bg-deep/50 px-3 py-2 font-mono text-[9px] leading-relaxed text-pastel-3/90">
            Simulation request failed. {apiError}
          </p>
        )}
        <motion.button
          type="button"
          onClick={() => void runSimulation()}
          disabled={!canRun}
          className="relative w-full overflow-hidden rounded-[24px] border border-pastel-2/25 px-3 py-4 font-mono text-[12px] font-semibold uppercase tracking-[0.12em] text-text-primary shadow-lg transition-shadow disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            background: 'linear-gradient(135deg, hsl(var(--pastel-2) / 0.42) 0%, hsl(var(--pastel-1) / 0.32) 50%, hsl(var(--pastel-3) / 0.28) 100%)',
            boxShadow: '0 12px 32px hsl(var(--pastel-2) / 0.12)',
          }}
          whileHover={canRun ? { scale: 1.01 } : {}}
          whileTap={canRun ? { scale: 0.99 } : {}}
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
                  {PHASE_COPY[phase] ?? 'Running…'}
                </motion.span>
              ) : (
                <motion.span
                  key="go"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Send className="h-4 w-4" />
                  Analyze Message
                </motion.span>
              )}
            </AnimatePresence>
          </span>
        </motion.button>

        <p className="mt-2 font-mono text-[8px] text-text-muted text-center min-h-[2.25em]">
          {running ? (
            <span className="text-pastel-2/90">TRIBE (Modal) and K2 Think run on the server; the map and inspection panel consume the returned JSON.</span>
          ) : (
            <>
              {catalystText.trim().length}/12+ characters required · Engine{' '}
              <span className="text-text-secondary">{status}</span>
            </>
          )}
        </p>

        <button
          type="button"
          onClick={() => resetSandbox()}
          disabled={running}
          className="mt-2 w-full rounded-[18px] border border-white/[0.06] bg-bg-elevated py-2.5 font-mono text-[10px] uppercase tracking-[0.1em] text-text-secondary transition-colors hover:border-white/[0.14] disabled:opacity-40"
        >
          Reset sandbox
        </button>
      </div>
    </aside>
  );
};
