import type { UseCaseId } from '@/data/useCases';
import { getUseCase } from '@/data/useCases';

export interface RejectionHotspot {
  id: string;
  label: string;
  /** Approximate area description */
  area: string;
  /** 0..1 share of modelled rejections */
  share: number;
  lng: number;
  lat: number;
  radiusMeters: number;
}

export interface PropagationReport {
  reachPct: number;
  adoptionRate: number;
  benchmark: number;
  benchmarkComparison: 'above' | 'below' | 'at';
  rejectionHotspots: RejectionHotspot[];
  whyResistance: string;
  recommendations: string[];
  predictedOutcome: string;
}

const LA_HOTSPOTS: { label: string; area: string; lng: number; lat: number }[] = [
  { label: 'SF Valley corridor', area: 'Northridge–Van Nuys', lng: -118.48, lat: 34.28 },
  { label: 'Westside', area: 'Santa Monica–Culver', lng: -118.4, lat: 34.02 },
  { label: 'Gateway cities', area: 'Southeast industrial belt', lng: -118.18, lat: 33.95 },
  { label: 'South LA', area: 'Watts–Compton margin', lng: -118.24, lat: 33.95 },
  { label: 'Eastside', area: 'Boyle Heights–Elysian', lng: -118.21, lat: 34.07 },
];

function hashSeed(useCase: UseCaseId, memo: 'A' | 'B', salt: string) {
  const s = `${useCase}${memo}${salt}`;
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h) / 2147483647;
}

/**
 * Build a stakeholder-ready report from the selected use case and memo variant.
 * Numbers are deterministic for the same (useCase, memo) so A/B comparisons are stable in-session.
 */
export function buildPropagationReport(
  useCase: UseCaseId,
  memo: 'A' | 'B',
): PropagationReport {
  const def = getUseCase(useCase)!;
  const b = def.adoptionBenchmark;
  const r = (i: number) => hashSeed(useCase, memo, `m${i}`);

  // Memo A is slightly “friendlier” for adoption in our toy model, except for health where B can spike fear adoption in segments — keep simple: A = higher base adoption
  const baseAdopt = memo === 'A' ? 0.22 + r(1) * 0.28 : 0.12 + r(2) * 0.22;
  const adoptionPct = Math.round(baseAdopt * 100);
  const reachPct = Math.min(98, 55 + Math.round((r(3) * 0.35 + (memo === 'A' ? 0.1 : 0.05)) * 100));
  const diff = adoptionPct - b;
  let benchmarkComparison: 'above' | 'below' | 'at' = 'at';
  if (diff > 2) benchmarkComparison = 'above';
  if (diff < -2) benchmarkComparison = 'below';

  // Pick 3 hotspot centers with sizes
  const hs: RejectionHotspot[] = [0, 1, 2].map((idx) => {
    const loc = LA_HOTSPOTS[(idx + Math.floor(r(10) * 3)) % LA_HOTSPOTS.length];
    return {
      id: `h-${idx}`,
      label: loc.label,
      area: loc.area,
      share: 0.12 + r(20 + idx) * 0.2,
      lng: loc.lng + (r(30 + idx) - 0.5) * 0.04,
      lat: loc.lat + (r(40 + idx) - 0.5) * 0.04,
      radiusMeters: 1800 + Math.round(r(50 + idx) * 4000),
    };
  });

  const whyByCase: Record<UseCaseId, { a: string; b: string }> = {
    political: {
      a: 'Civic audiences in homeowner-heavy clusters show the lowest uptake where messages emphasize “shared prosperity” without concrete neighborhood ROI — cognitive load rises when abstractions outnumber local landmarks.',
      b: 'Defensive posture spikes in the Valley and Gateway cities when the memo pairs crisis framing with implied blame; homeowners interpret this as status threat, triggering resistance even among persuadable independents.',
    },
    public_health: {
      a: 'Uptake is strongest when care access is the hero and stigma is absent; resistance concentrates where prior outreach felt extractive to shift workers and night-economy employees.',
      b: 'Mandate language elevates identity threat in tight-knit neighborhoods; the model shows rejection clusters where compliance cues imply punishment rather than shared protection.',
    },
    urban: {
      a: 'Rejection is localized where homeowners perceive a mismatch between “affordable set-aside” and parking/traffic assurances; strain is geographic, not random.',
      b: 'Preemption and urgency without mitigation funds activate defensive coalitions; South LA and Eastside segments reject top-down “shock” narratives unless infrastructure dollars are front-loaded in copy.',
    },
    corporate: {
      a: 'Autonomy framing lowers strain for knowledge workers, but line-level roles show skepticism if pilots lack on-site support budgets — a clarity gap, not a values gap.',
      b: 'Mandatory RTO and badge surveillance spike defensive responses in commutes from outer ZIP codes; loss-frame around bonuses reads as coercive control, not leadership alignment.',
    },
  };

  const recByCase: Record<UseCaseId, { a: string[]; b: string[] }> = {
    political: {
      a: [
        'Add one sentence of concrete neighborhood impact per city council district named in the memo.',
        'Swap crisis openers for “shared timeline” language and pair any contrast line with a verifiable data citation.',
        'A/B test a 6-second audio hook that front-loads local jobs numbers before value statements.',
      ],
      b: [
        'Soften loss-frame in homeowner ZIPs: replace “sliding backward” with “stalled progress” and add a single repair pledge.',
        'Move opponent contrast to the last third of the message; open with a voter benefit hook to lower initial defensive posture.',
        'Add a “trusted neighbor” social proof line sourced from a non-partisan community board.',
      ],
    },
    public_health: {
      a: [
        'Mention no-cost time windows before any schedule constraints; lead with how to access, not what is required.',
        'Add bilingual micro-copy at the top of SMS variants for 900xx ZIP clusters.',
        'Co-brand with a community clinic in each rejection hotspot in the next revision.',
      ],
      b: [
        'Replace “mandatory” in headlines with “required for site entry” only where law demands; lead with support resources.',
        'Add a 48-hour question hotline and surface it before penalty language.',
        'Use opt-out framing for workers on night shifts: “choose your site day” to reduce identity threat.',
      ],
    },
    urban: {
      a: [
        'Publish a one-page traffic study summary per sub-area and link it from the first paragraph of outreach.',
        'Pair density numbers with a mitigation dollar amount that maps to the reader’s subregion.',
        'Add design-review guarantees as bullet points, not an appendix footnote.',
      ],
      b: [
        'Front-load a mitigation fund number before any preemption phrasing; treat funds as the headline, timeline second.',
        'Add “local appeals pathway” phrasing to reduce felt loss of control among homeowner associations.',
        'Replace “emergency” with “planned capacity” in titles to lower startle response.',
      ],
    },
    corporate: {
      a: [
        'State pilot success metrics in one sentence before describing flexibility; managers mirror leadership.',
        'Offer one paid WFH day bank for roles with long commutes to shrink Valley/Westside strain pockets.',
        'Add an anonymous pulse survey link in the first screen of the rollout deck.',
      ],
      b: [
        'Re-sequence: announce support budgets and childcare stipends before badge audits.',
        "Rename “mandatory” to “team anchor schedule” in internal chat; lead with the customer outcome, not the rule.",
        'Tie any compliance metric to a rotating recognition program instead of only punitive review language.',
      ],
    },
  };

  const why = memo === 'A' ? whyByCase[useCase].a : whyByCase[useCase].b;
  const recs = memo === 'A' ? recByCase[useCase].a : recByCase[useCase].b;

  const lift = Math.round(4 + r(60) * 9);
  const predicted =
    benchmarkComparison === 'below'
      ? `With the top two language fixes and localized hooks for the highlighted clusters, the model predicts adoption toward ~${Math.min(95, adoptionPct + lift)}% in the next message iteration — on par with the ${b}% ${def.label.toLowerCase()} reference band.`
      : `Maintaining the current framing and adding narrow testing in the lowest-performing hotspot could push reach above ${Math.min(99, reachPct + 2)}% without large copy changes.`;

  return {
    reachPct,
    adoptionRate: adoptionPct,
    benchmark: b,
    benchmarkComparison,
    rejectionHotspots: hs,
    whyResistance: why,
    recommendations: recs,
    predictedOutcome: predicted,
  };
}

export interface MemoDiffSummary {
  winner: 'A' | 'B' | 'tie';
  marginPp: number;
  languageDriver: string;
  detail: string;
}

export function buildMemoDiff(
  useCase: UseCaseId,
  aAdopt: number,
  bAdopt: number,
): MemoDiffSummary {
  const d = aAdopt - bAdopt;
  let winner: 'A' | 'B' | 'tie' = 'tie';
  if (d > 1) winner = 'A';
  if (d < -1) winner = 'B';
  const marginPp = Math.abs(Math.round(d));

  const drivers: Record<UseCaseId, { line: string; detail: string }> = {
    political: {
      line: 'Gain vs loss framing in the lede and contrast block',
      detail:
        'Memo A’s community uplift lede held defensive posture under the 0.7 threshold in Westside and Valley segments, while Memo B’s crisis + contrast block spiked rejections in the same geos. The delta is concentrated in homeowner-heavy tiles.',
    },
    public_health: {
      line: 'Autonomy and access language vs mandate-first sequencing',
      detail:
        'Where Memo A led with clinic access, adoption followed evening-shift cohorts. Memo B’s penalty language created identity-threat clustering in the Gateway cities and South LA that did not appear in the A run.',
    },
    urban: {
      line: 'Co-benefit and mitigation front-loading vs preemption',
      detail:
        'Memo A’s explicit mitigation dollars and design-review seats reduced strain in low-density R1 zones. Memo B’s preemption phrasing without parallel funding lines drove the rejection hotspots you see in the map overlay.',
    },
    corporate: {
      line: 'Autonomy and pilot review vs compliance surveillance framing',
      detail:
        'Memo A’s choice architecture and quarterly review cut defensive posture in outer-commute segments. Memo B’s badge-audit emphasis concentrated rejection along I-405 corridor commutes, matching loss-aversion stress in the fMRI route.',
    },
  };

  return {
    winner,
    marginPp,
    languageDriver: drivers[useCase].line,
    detail: drivers[useCase].detail,
  };
}
