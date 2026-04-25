import { Suspense, lazy } from 'react';
import { useCortexStore } from '@/store/cortex';
import { UseCaseSelector } from '@/components/cortex/UseCaseSelector';

const CaseWorkspace = lazy(() =>
  import('@/components/cortex/CaseWorkspace').then((module) => ({ default: module.CaseWorkspace })),
);

const Index = () => {
  const screen = useCortexStore((s) => s.screen);

  if (screen === 'useCases') {
    return <UseCaseSelector />;
  }

  return (
    <Suspense fallback={<div className="min-h-screen bg-bg-deep" />}>
      <CaseWorkspace />
    </Suspense>
  );
};

export default Index;
