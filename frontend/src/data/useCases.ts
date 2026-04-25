export type UseCaseId = 'political' | 'public_health' | 'urban' | 'corporate';

export interface UseCaseDefinition {
  id: UseCaseId;
  label: string;
  description: string;
  icon: string;
  /** Benchmark for “good” belief adoption (%) for this domain */
  adoptionBenchmark: number;
  /** Label for the benchmark line in the UI */
  benchmarkLabel: string;
  memoA: { title: string; subtitle: string; preview: string };
  memoB: { title: string; subtitle: string; preview: string };
}

export const USE_CASES: UseCaseDefinition[] = [
  {
    id: 'political',
    label: 'Political Campaign',
    description: 'Turnout, persuasion, and trust framing across voter segments in LA County.',
    icon: '🗳',
    adoptionBenchmark: 32,
    benchmarkLabel: '32% is typical for competitive persuasion in swing districts',
    memoA: {
      title: 'Memo A — Community uplift frame',
      subtitle: 'Jobs-first, inclusive growth, no attack lines.',
      preview:
        'We’re building shared prosperity: local hiring pledges, small-business tax credits, and neighborhood safety investments paid for by closing corporate loopholes.',
    },
    memoB: {
      title: 'Memo B — Crisis + opponent contrast',
      subtitle: 'Urgency, loss aversion, sharp contrast on failures.',
      preview:
        'Our city is sliding backward while insiders stall. If we do not act now, your schools and streets pay the price. The other side let violent crime fester in Valley corridors.',
    },
  },
  {
    id: 'public_health',
    label: 'Public Health',
    description: 'Vaccine uptake, harm reduction, and behavioral nudges for dense urban populations.',
    icon: '⛑',
    adoptionBenchmark: 45,
    benchmarkLabel: '45% is the public-health target for high-trust messaging in metro areas',
    memoA: {
      title: 'Memo A — Care + access narrative',
      subtitle: 'Clinic hours, free transit to care, no blame.',
      preview:
        'Your health system is adding evening clinics and home visits for seniors. No appointments needed for the updated booster at mobile units — we protect each other by showing up together.',
    },
    memoB: {
      title: 'Memo B — Mandate + penalty framing',
      subtitle: 'Compliance, deadlines, consequences for non-participation.',
      preview:
        'Mandatory compliance windows are now in effect. Employers who fail to document workforce coverage will face escalating fines. Non-compliance is not an option in healthcare facilities.',
    },
  },
  {
    id: 'urban',
    label: 'Urban Planning',
    description: 'Zoning, housing density, and mobility projects with neighborhood buy-in.',
    icon: '🏙',
    adoptionBenchmark: 40,
    benchmarkLabel: '40% is the civic benchmark for upzoning and transit ballot alignment',
    memoA: {
      title: 'Memo A — Co-benefit housing plan',
      subtitle: 'Affordable set-aside, first-mile transit, tree canopy.',
      preview:
        'The corridor plan dedicates 30% affordable units, funds a BRT line, and adds pocket parks. Homeowners get design review seats and a dedicated traffic-calming fund.',
    },
    memoB: {
      title: 'Memo B — Density shock narrative',
      subtitle: 'Urgent capacity, state preemption, minimal mitigation.',
      preview:
        'The housing emergency overrides local delays. State maps show we must add 12,000 units in three years. Appeals that stall pipeline projects will be fast-tracked over local objections.',
    },
  },
  {
    id: 'corporate',
    label: 'Corporate Comms',
    description: 'Change management, RTO, and policy rollouts to distributed teams.',
    icon: '💼',
    adoptionBenchmark: 38,
    benchmarkLabel: '38% is the change-management target for opt-in program adoption at scale',
    memoA: {
      title: 'Memo A — Autonomy + pilot window',
      subtitle: 'Choice architecture, 90-day review, team-level flexibility.',
      preview:
        'We’re piloting flexible hybrid: teams choose 2–3 anchor days with budget for coworking. We’ll review sentiment and metrics quarterly before any permanent policy — your manager owns the team norm.',
    },
    memoB: {
      title: 'Memo B — Mandatory RTO push',
      subtitle: 'Leadership edict, compliance tracking, site badges.',
      preview:
        'Starting Monday, 5-day on-site is mandatory for all revenue teams. Badging data will be audited weekly; non-compliance will affect performance review bands and bonus eligibility.',
    },
  },
];

export function getUseCase(id: UseCaseId | null): UseCaseDefinition | null {
  if (!id) return null;
  return USE_CASES.find((u) => u.id === id) ?? null;
}
