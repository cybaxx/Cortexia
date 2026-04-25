export type UseCaseId = 'political' | 'public_health' | 'urban' | 'corporate';

export interface UseCaseDefinition {
  id: UseCaseId;
  label: string;
  description: string;
  /** Benchmark for "good" belief adoption (%) for this domain */
  adoptionBenchmark: number;
  /** Label for the benchmark line in the UI */
  benchmarkLabel: string;
}

export const USE_CASES: UseCaseDefinition[] = [
  {
    id: 'political',
    label: 'Political Campaign',
    description: 'Turnout, persuasion, and trust framing across voter segments.',
    adoptionBenchmark: 32,
    benchmarkLabel: '32% is typical for competitive persuasion in swing districts',
  },
  {
    id: 'public_health',
    label: 'Public Health',
    description: 'Vaccine uptake, harm reduction, and behavioral nudges for dense urban populations.',
    adoptionBenchmark: 45,
    benchmarkLabel: '45% is the public-health target for high-trust messaging in metro areas',
  },
  {
    id: 'urban',
    label: 'Urban Planning',
    description: 'Zoning, housing density, and mobility projects with neighborhood buy-in.',
    adoptionBenchmark: 40,
    benchmarkLabel: '40% is the civic benchmark for upzoning and transit ballot alignment',
  },
  {
    id: 'corporate',
    label: 'Corporate Comms',
    description: 'Change management, RTO, and policy rollouts to distributed teams.',
    adoptionBenchmark: 38,
    benchmarkLabel: '38% is the change-management target for opt-in program adoption at scale',
  },
];

export function getUseCase(id: UseCaseId | null): UseCaseDefinition | null {
  if (!id) return null;
  return USE_CASES.find((u) => u.id === id) ?? null;
}
