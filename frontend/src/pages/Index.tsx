import { MapView } from '@/components/cortex/MapView';
import { TopBar } from '@/components/cortex/TopBar';
import { ScenarioInjector } from '@/components/cortex/ScenarioInjector';
import { PropagationReportPanel } from '@/components/cortex/PropagationReportPanel';
import { UseCaseSelector } from '@/components/cortex/UseCaseSelector';
import { useCortexStore } from '@/store/cortex';

const SimulationLayout = () => {
  return (
    <div className="relative h-screen w-screen overflow-hidden bg-bg-deep text-text-primary">
      <h1 className="sr-only">Cortexia — cognitive impact simulation</h1>
      <MapView />
      <TopBar />
      <ScenarioInjector />
      <PropagationReportPanel />
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
