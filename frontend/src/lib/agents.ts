// Mock LA agents and influence arcs for the Cortexia sandbox
export type AgentState = 'neutral' | 'strain' | 'adopt';

export interface Agent {
  id: number;
  name: string;
  role: string;
  position: [number, number]; // [lng, lat]
  state: AgentState;
  cognitiveLoad: number;      // 0..1
  emotionalAgitation: number; // 0..1
  defensivePosture: number;   // 0..1
}

export interface InfluenceArc {
  source: [number, number];
  target: [number, number];
}

const ROLES = [
  'Civic Analyst', 'Educator', 'Logistics Lead', 'Healthcare Worker',
  'Journalist', 'Engineer', 'Small Biz Owner', 'Policy Aide',
  'Researcher', 'Retiree', 'Student', 'First Responder',
];

const FIRST = ['Ava','Noah','Mia','Liam','Zoe','Eli','Maya','Owen','Iris','Kai','Lena','Theo','Nora','Ezra','Ines','Jude'];
const LAST = ['Ramos','Chen','Patel','Nguyen','Okafor','Silva','Khan','Walsh','Brooks','Tanaka','Mendez','Park','Aoki','Diallo'];

// Bounding box loosely covering LA basin
const LNG_MIN = -118.50, LNG_MAX = -118.05;
const LAT_MIN = 33.85,  LAT_MAX = 34.22;

function seeded(i: number) {
  const x = Math.sin(i * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

export function generateAgents(count = 100): Agent[] {
  const agents: Agent[] = [];
  for (let i = 0; i < count; i++) {
    const r1 = seeded(i + 1);
    const r2 = seeded(i + 1001);
    const r3 = seeded(i + 2001);
    const lng = LNG_MIN + r1 * (LNG_MAX - LNG_MIN);
    const lat = LAT_MIN + r2 * (LAT_MAX - LAT_MIN);
    let state: AgentState = 'neutral';
    if (r3 > 0.78) state = 'strain';
    else if (r3 > 0.58) state = 'adopt';
    agents.push({
      id: i,
      name: `${FIRST[i % FIRST.length]} ${LAST[(i * 3) % LAST.length]}`,
      role: ROLES[i % ROLES.length],
      position: [lng, lat],
      state,
      cognitiveLoad: 0.25 + seeded(i + 5000) * 0.7,
      emotionalAgitation: 0.15 + seeded(i + 6000) * 0.8,
      defensivePosture: 0.2 + seeded(i + 7000) * 0.75,
    });
  }
  return agents;
}

export function generateArcs(agents: Agent[], count = 35): InfluenceArc[] {
  const arcs: InfluenceArc[] = [];
  for (let i = 0; i < count; i++) {
    const a = agents[Math.floor(seeded(i + 11) * agents.length)];
    const b = agents[Math.floor(seeded(i + 99) * agents.length)];
    if (a && b && a.id !== b.id) arcs.push({ source: a.position, target: b.position });
  }
  return arcs;
}

/** Map node colors: strict Indigo/Coral/Gray palette. */
export const COLORS = {
  neutral: [188, 231, 219, 168] as [number, number, number, number], // Mint mist
  strain: [255, 191, 166, 220] as [number, number, number, number],  // Peach reactance
  adopt: [160, 214, 255, 224] as [number, number, number, number],   // Sky adoption
};

export function beliefToAgentState(b: 'adopted' | 'rejected' | 'neutral'): AgentState {
  if (b === 'adopted') return 'adopt';
  if (b === 'rejected') return 'strain';
  return 'neutral';
}

/** Synthetic population around a metro center (not LA-only). */
export function generateAgentsForRegion(
  centerLng: number,
  centerLat: number,
  span: number,
  count = 100,
): Agent[] {
  const half = span / 2;
  const agents: Agent[] = [];
  for (let i = 0; i < count; i++) {
    const r1 = seeded(i + 1);
    const r2 = seeded(i + 1001);
    const r3 = seeded(i + 2001);
    const lng = centerLng - half + r1 * span;
    const lat = centerLat - half * 0.8 + r2 * span * 0.8;
    let state: AgentState = 'neutral';
    if (r3 > 0.78) state = 'strain';
    else if (r3 > 0.58) state = 'adopt';
    agents.push({
      id: i,
      name: `${FIRST[i % FIRST.length]} ${LAST[(i * 3) % LAST.length]}`,
      role: ROLES[i % ROLES.length],
      position: [lng, lat],
      state,
      cognitiveLoad: 0.25 + seeded(i + 5000) * 0.7,
      emotionalAgitation: 0.15 + seeded(i + 6000) * 0.8,
      defensivePosture: 0.2 + seeded(i + 7000) * 0.75,
    });
  }
  return agents;
}

interface LandZone {
  lngMin: number;
  lngMax: number;
  latMin: number;
  latMax: number;
}

/** Place agents only within the provided land zones, distributed proportionally by zone area. */
export function generateAgentsForCity(
  landZones: LandZone[],
  count = 110,
): Agent[] {
  if (landZones.length === 0) return [];

  // Compute total area weight for proportional sampling
  const areas = landZones.map(
    (z) => (z.lngMax - z.lngMin) * (z.latMax - z.latMin),
  );
  const totalArea = areas.reduce((a, b) => a + b, 0);
  const cumulative: number[] = [];
  let cum = 0;
  for (const a of areas) {
    cum += a / totalArea;
    cumulative.push(cum);
  }

  const agents: Agent[] = [];
  for (let i = 0; i < count; i++) {
    // Pick zone by area weight
    const zonePick = seeded(i + 8500);
    const zoneIdx = cumulative.findIndex((c) => zonePick <= c) ?? 0;
    const zone = landZones[Math.max(0, zoneIdx)];

    const r1 = seeded(i + 1);
    const r2 = seeded(i + 1001);
    const r3 = seeded(i + 2001);
    const lng = zone.lngMin + r1 * (zone.lngMax - zone.lngMin);
    const lat = zone.latMin + r2 * (zone.latMax - zone.latMin);

    let state: AgentState = 'neutral';
    if (r3 > 0.78) state = 'strain';
    else if (r3 > 0.58) state = 'adopt';

    agents.push({
      id: i,
      name: `${FIRST[i % FIRST.length]} ${LAST[(i * 3) % LAST.length]}`,
      role: ROLES[i % ROLES.length],
      position: [lng, lat],
      state,
      cognitiveLoad: 0.25 + seeded(i + 5000) * 0.7,
      emotionalAgitation: 0.15 + seeded(i + 6000) * 0.8,
      defensivePosture: 0.2 + seeded(i + 7000) * 0.75,
    });
  }
  return agents;
}
