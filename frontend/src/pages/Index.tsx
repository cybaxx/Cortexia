import { ProductLanding } from '@/components/cortex/ProductLanding';
import { SimulationDashboard } from '@/components/cortex/SimulationDashboard';
import { useCortexStore } from '@/store/cortex';

const Index = () => {
  const screen = useCortexStore((s) => s.screen);
  const setScreen = useCortexStore((s) => s.setScreen);

  if (screen === 'dashboard' || screen === 'workspace') {
    return <SimulationDashboard onBack={() => setScreen('landing')} />;
  }

  return <ProductLanding onEnter={() => setScreen('dashboard')} />;
};

export default Index;
