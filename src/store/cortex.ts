import { create } from 'zustand';

export interface LogEntry {
  id: number;
  text: string;
  kind: 'info' | 'think' | 'action';
}

interface CortexState {
  status: 'idle' | 'running';
  selectedMemo: 'A' | 'B' | null;
  logs: LogEntry[];
  metrics: {
    populationReached: number;
    avgCognitiveLoad: number;
    beliefAdoptionRate: number;
    spatialTension: 'Low' | 'Moderate' | 'High';
  };
  pushLog: (entry: Omit<LogEntry, 'id'>) => void;
  setStatus: (s: 'idle' | 'running') => void;
  setMemo: (m: 'A' | 'B' | null) => void;
}

let _id = 0;

export const useCortexStore = create<CortexState>((set) => ({
  status: 'idle',
  selectedMemo: null,
  logs: [],
  metrics: {
    populationReached: 45,
    avgCognitiveLoad: 0.68,
    beliefAdoptionRate: 22,
    spatialTension: 'High',
  },
  pushLog: (entry) =>
    set((s) => ({
      logs: [...s.logs.slice(-80), { ...entry, id: ++_id }],
    })),
  setStatus: (status) => set({ status }),
  setMemo: (selectedMemo) => set({ selectedMemo }),
}));
