import { Suspense, lazy } from 'react';
import { useCortexStore } from '@/store/cortex';
import { TopBar } from '@/components/cortex/TopBar';
import { UseCaseSelector } from '@/components/cortex/UseCaseSelector';

const MapView = lazy(() =>
  import('@/components/cortex/MapView').then((module) => ({ default: module.MapView })),
);
const SimulationInputPanel = lazy(() =>
  import('@/components/cortex/SimulationInputPanel').then((module) => ({
    default: module.SimulationInputPanel,
  })),
);
const LiveAudienceReaction = lazy(() =>
  import('@/components/cortex/LiveAudienceReaction').then((module) => ({
    default: module.LiveAudienceReaction,
  })),
);
const PropagationReportPanel = lazy(() =>
  import('@/components/cortex/PropagationReportPanel').then((module) => ({
    default: module.PropagationReportPanel,
  })),
);

const SimulationShellFallback = () => (
  <div className="absolute inset-0 bg-bg-deep">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(160,214,255,0.12),transparent_35%),radial-gradient(circle_at_bottom,rgba(255,191,166,0.08),transparent_30%)]" />
    <div className="absolute left-4 right-4 top-4 h-12 rounded-full border border-white/[0.08] bg-bg-surface/75" />
    <div className="absolute bottom-4 left-4 top-16 w-[min(96vw,22rem)] rounded-[34px] border border-white/[0.08] bg-bg-surface/75" />
  </div>
);

const SimulationLayout = () => {
  return (
    <div className="relative h-screen w-screen overflow-hidden bg-bg-deep text-text-primary">
      <h1 className="sr-only">Cortexia — cognitive impact simulation</h1>
      <Suspense fallback={<SimulationShellFallback />}>
        <MapView />
        <TopBar />
        <SimulationInputPanel />
        <LiveAudienceReaction />
        <PropagationReportPanel />
      </Suspense>
    </div>
  );
};

const Index = () => {
  const screen = useCortexStore((s) => s.screen);

  if (screen === 'useCases') {
    return <UseCaseSelector />;
  }

  return <SimulationLayout />;
};

export default Index;
