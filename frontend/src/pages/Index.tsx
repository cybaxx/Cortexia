import { MapView } from '@/components/cortex/MapView';
import { TopBar } from '@/components/cortex/TopBar';
import { ScenarioInjector } from '@/components/cortex/ScenarioInjector';
import { ReasoningFeed } from '@/components/cortex/ReasoningFeed';
import { BottomBar } from '@/components/cortex/BottomBar';

const Index = () => {
  return (
    <main className="relative h-screen w-screen overflow-hidden bg-bg-deep text-text-primary">
      <h1 className="sr-only">Cortexia — Cognitive Impact Sandbox · Los Angeles</h1>
      <MapView />
      <TopBar />
      <ScenarioInjector />
      <ReasoningFeed />
      <BottomBar />
    </main>
  );
};

export default Index;
