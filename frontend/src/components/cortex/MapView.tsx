import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import ReactMap, { Layer, type MapRef } from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { IconLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import { getCityById } from '@/data/cities';
import { COLORS, beliefToAgentState, type Agent } from '@/lib/agents';
import { useCortexStore } from '@/store/cortex';
import type { AgentSimulationPayload } from '@/types/simulation';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
const INITIAL_ZOOM = 2.5;
const MAP_STYLE = 'mapbox://styles/mapbox/dark-v11';

const BUILDINGS_LAYER = {
  id: '3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  filter: ['==', 'extrude', 'true'],
  type: 'fill-extrusion',
  minzoom: 13,
  paint: {
    'fill-extrusion-color': '#18212e',
    'fill-extrusion-height': ['coalesce', ['get', 'height'], 0],
    'fill-extrusion-base': ['coalesce', ['get', 'min_height'], 0],
    'fill-extrusion-opacity': 0.72,
  },
} as const;

type Point = [number, number];

function mergeAgent(base: Agent, override?: Partial<Agent>): Agent {
  if (!override) return base;
  return { ...base, ...override, position: base.position };
}

function buildAgentFromPayload(payload: AgentSimulationPayload, override?: Partial<Agent>): Agent {
  return mergeAgent(
    {
      id: payload.id,
      name: payload.name,
      role: payload.role,
      position: [payload.longitude, payload.latitude],
      state: beliefToAgentState(payload.belief_state),
      cognitiveLoad: payload.tribe_neurological_metrics.cognitive_load,
      emotionalAgitation: payload.tribe_neurological_metrics.emotional_friction,
      defensivePosture: payload.tribe_neurological_metrics.defensive_activation,
      confidence: payload.k2_decision_confidence,
      dominantSignal: payload.dominant_signal,
    },
    override,
  );
}

function confidenceRadius(agent: Agent) {
  const confidence = agent.confidence ?? 0.5;
  return 80 + confidence * 70;
}

function glowRadius(agent: Agent) {
  return confidenceRadius(agent) * (1.15 + agent.cognitiveLoad * 0.2);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function markerSize(zoom: number, cityZoom: number) {
  return clamp(34 + (zoom - cityZoom) * 3.4, 30, 52);
}

function svgToDataUrl(svg: string) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function personIconSvg(fill: string) {
  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 96">
      <ellipse cx="32" cy="87" rx="18" ry="6" fill="rgba(0,0,0,0.28)" />
      <circle cx="32" cy="16" r="10" fill="${fill}" />
      <rect x="24" y="28" width="16" height="26" rx="8" fill="${fill}" />
      <rect x="18" y="32" width="8" height="24" rx="4" fill="${fill}" />
      <rect x="38" y="32" width="8" height="24" rx="4" fill="${fill}" />
      <rect x="24" y="52" width="7" height="28" rx="3.5" fill="${fill}" />
      <rect x="33" y="52" width="7" height="28" rx="3.5" fill="${fill}" />
    </svg>
  `;
}

const PERSON_ICONS = {
  adopt: {
    url: svgToDataUrl(personIconSvg('#4A9EFF')),
    width: 64,
    height: 96,
    anchorY: 88,
  },
  strain: {
    url: svgToDataUrl(personIconSvg('#E8856A')),
    width: 64,
    height: 96,
    anchorY: 88,
  },
  neutral: {
    url: svgToDataUrl(personIconSvg('#C0B8B0')),
    width: 64,
    height: 96,
    anchorY: 88,
  },
} as const;

function clusterFill(state?: 'adopted' | 'rejected' | 'neutral') {
  if (state === 'adopted') return [74, 158, 255, 38] as [number, number, number, number];
  if (state === 'rejected') return [232, 133, 106, 38] as [number, number, number, number];
  return [192, 184, 176, 30] as [number, number, number, number];
}

function createLegendPerson(color: string) {
  return (
    <svg viewBox="0 0 24 32" className="h-5 w-4" aria-hidden="true">
      <ellipse cx="12" cy="29" rx="6" ry="2.2" fill="rgba(0,0,0,0.28)" />
      <circle cx="12" cy="6" r="3.5" fill={color} />
      <rect x="9" y="10" width="6" height="9" rx="3" fill={color} />
      <rect x="6.5" y="12" width="3" height="8" rx="1.5" fill={color} />
      <rect x="14.5" y="12" width="3" height="8" rx="1.5" fill={color} />
      <rect x="9.2" y="18" width="2.6" height="9" rx="1.3" fill={color} />
      <rect x="12.2" y="18" width="2.6" height="9" rx="1.3" fill={color} />
    </svg>
  );
}

function interpolatePoint(start: Point, end: Point, t: number): Point {
  return [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t];
}

export const MapView = () => {
  const cityId = useCortexStore((s) => s.cityId);
  const overrides = useCortexStore((s) => s.agentOverrides);
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const agentSimulationById = useCortexStore((s) => s.agentSimulationById);
  const latestResponse = useCortexStore((s) => s.latestResponse);
  const selectedAgentId = useCortexStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useCortexStore((s) => s.setSelectedAgentId);

  const city = getCityById(cityId);
  const c = city.center;
  const hotspots = spreadModel?.hotspots ?? [];
  const swarmRounds = latestResponse?.swarm_dynamics?.rounds ?? [];
  const latestRound = swarmRounds.length ? swarmRounds[swarmRounds.length - 1] : undefined;

  const [viewState, setViewState] = useState({
    longitude: c.longitude,
    latitude: c.latitude,
    zoom: INITIAL_ZOOM,
    pitch: 42,
    bearing: -18,
  });
  const [pinned, setPinned] = useState<{ agent: Agent; x: number; y: number } | null>(null);
  const [flowTick, setFlowTick] = useState(0);
  const mapRef = useRef<MapRef>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const agents = useMemo(
    () =>
      Object.values(agentSimulationById)
        .sort((a, b) => a.id - b.id)
        .map((payload) => buildAgentFromPayload(payload, overrides[payload.id])),
    [agentSimulationById, overrides],
  );

  const networkEdges = useMemo(() => {
    const raw = (latestResponse?.swarm_dynamics?.network_edges ?? []).filter(
      (edge) =>
        Number.isFinite(edge.source_lng) &&
        Number.isFinite(edge.source_lat) &&
        Number.isFinite(edge.target_lng) &&
        Number.isFinite(edge.target_lat),
    );
    const ranked = [...raw].sort(
      (a, b) => ((b.weight ?? 0.5) * (b.compatibility ?? 0.5)) - ((a.weight ?? 0.5) * (a.compatibility ?? 0.5)),
    );
    if (!pinned) return ranked.filter((edge, index) => (edge.weight ?? 0.5) >= 0.64 || index < 160);
    return ranked.filter(
      (edge, index) =>
        edge.source_id === pinned.agent.id ||
        edge.target_id === pinned.agent.id ||
        (edge.weight ?? 0.5) >= 0.72 ||
        index < 120,
    );
  }, [latestResponse, pinned]);

  const networkPaths = useMemo(
    () =>
      networkEdges.map((edge, index) => ({
        id: `network-${edge.source_id}-${edge.target_id}-${index}`,
        path: [
          [edge.source_lng, edge.source_lat],
          [edge.target_lng, edge.target_lat],
        ] as Point[],
        width: 1 + (edge.weight ?? 0.5) * 0.6 + (edge.compatibility ?? 0.5) * 0.25,
        alpha: Math.round(64 + (edge.weight ?? 0.5) * 26 + (edge.compatibility ?? 0.5) * 18),
      })),
    [networkEdges],
  );

  const activeInteractionPaths = useMemo(() => {
    if (!latestRound) return [];
    const byId = new globalThis.Map<number, AgentSimulationPayload>(
      Object.values(agentSimulationById).map((payload) => [payload.id, payload]),
    );
    return latestRound.posts
      .filter((post) => post.action_type === 'talk_to_agent' && post.target_agent_id != null)
      .map((post, index) => {
        const source = byId.get(post.agent_id);
        const target = byId.get(post.target_agent_id ?? -1);
        if (!source || !target) return null;
        return {
          id: `active-${post.agent_id}-${post.target_agent_id}-${index}`,
          sourcePosition: [source.longitude, source.latitude] as Point,
          targetPosition: [target.longitude, target.latitude] as Point,
          path: [
            [source.longitude, source.latitude],
            [target.longitude, target.latitude],
          ] as Point[],
          beliefState: post.belief_state,
          strength: Math.max(post.weighted_support ?? 0, post.weighted_pushback ?? 0, 0.18),
          confidence: post.confidence,
        };
      })
      .filter(
        (
          item,
        ): item is {
          id: string;
          sourcePosition: Point;
          targetPosition: Point;
          path: Point[];
          beliefState: AgentSimulationPayload['belief_state'];
          strength: number;
          confidence: number;
        } => Boolean(item),
      );
  }, [agentSimulationById, latestRound]);

  const activeFlowMarkers = useMemo(
    () =>
      activeInteractionPaths.map((path, index) => {
        const t = (flowTick * 0.22 + index * 0.13) % 1;
        return {
          ...path,
          position: interpolatePoint(path.sourcePosition, path.targetPosition, t),
        };
      }),
    [activeInteractionPaths, flowTick],
  );

  const hotspotLabels = useMemo(
    () =>
      hotspots.slice(0, 3).map((spot) => ({
        ...spot,
        position: [spot.lng, spot.lat] as Point,
        label: `${spot.area} ${Math.round(spot.share * 100)}%`,
      })),
    [hotspots],
  );

  useEffect(() => {
    setPinned(null);
    setViewState((vs) => ({
      ...vs,
      longitude: c.longitude,
      latitude: c.latitude,
      zoom: INITIAL_ZOOM,
      pitch: 42,
      bearing: -18,
    }));
  }, [cityId, c.latitude, c.longitude]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setViewState((vs) => ({
        ...vs,
        longitude: c.longitude,
        latitude: c.latitude,
        zoom: c.zoom,
        pitch: 58,
        bearing: -22,
        transitionDuration: 1800,
      }));
    }, 180);
    return () => clearTimeout(timeout);
  }, [c.latitude, c.longitude, c.zoom]);

  useEffect(() => {
    let frame = 0;
    let last = 0;
    const animate = (timestamp: number) => {
      if (timestamp - last > 60) {
        setFlowTick(timestamp / 1000);
        last = timestamp;
      }
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, []);

  const handleDeckClick = useCallback((info: { object?: unknown; x?: number; y?: number }) => {
    const object = info.object as Agent | undefined;
    if (object) {
      const rect = containerRef.current?.getBoundingClientRect();
      const centerX = rect ? rect.width / 2 : info.x ?? 0;
      const centerY = rect ? rect.height / 2 : info.y ?? 0;

      setViewState((vs) => ({
        ...vs,
        longitude: object.position[0],
        latitude: object.position[1],
        zoom: Math.max(vs.zoom, c.zoom + 0.25),
        transitionDuration: 900,
      }));

      setPinned({ agent: object, x: centerX, y: centerY });
      setSelectedAgentId(object.id);
    } else {
      setPinned(null);
      setSelectedAgentId(null);
    }
  }, [c.zoom, setSelectedAgentId]);

  const mergedPopupAgent = useMemo(() => {
    if (!pinned) return null;
    const payload = agentSimulationById[pinned.agent.id];
    if (!payload) return mergeAgent(pinned.agent, overrides[pinned.agent.id]);
    return buildAgentFromPayload(payload, overrides[payload.id]);
  }, [agentSimulationById, overrides, pinned]);

  useEffect(() => {
    if (selectedAgentId == null) {
      setPinned(null);
      return;
    }
    const payload = agentSimulationById[selectedAgentId];
    if (!payload) return;
    setPinned((current) => {
      if (current?.agent.id === selectedAgentId) return current;
      const nextAgent = buildAgentFromPayload(payload, overrides[payload.id]);
      const rect = containerRef.current?.getBoundingClientRect();
      return {
        agent: nextAgent,
        x: rect ? rect.width / 2 : 0,
        y: rect ? rect.height / 2 : 0,
      };
    });
  }, [agentSimulationById, overrides, selectedAgentId]);

  const layers = [
    ...(networkPaths.length
      ? [
          new PathLayer({
            id: 'network-lines',
            data: networkPaths,
            pickable: false,
            getPath: (d) => d.path,
            getColor: (d) => [255, 255, 255, Math.round(d.alpha * 0.82)] as [number, number, number, number],
            getWidth: (d) => d.width,
            widthMinPixels: 1,
            widthMaxPixels: 1.8,
            jointRounded: true,
            capRounded: true,
            parameters: { depthTest: false },
          }),
        ]
      : []),
    ...(activeInteractionPaths.length
      ? [
          new PathLayer({
            id: 'active-influence-lines',
            data: activeInteractionPaths,
            pickable: false,
            getPath: (d) => d.path,
            getColor: () => [255, 255, 255, 88] as [number, number, number, number],
            getWidth: (d) => 1 + d.strength * 0.75,
            widthMinPixels: 1,
            widthMaxPixels: 2,
            jointRounded: true,
            capRounded: true,
            getDashArray: () => [4, 3] as [number, number],
            extensions: [new PathStyleExtension({ dash: true, highPrecisionDash: true })],
            dashJustified: false,
            parameters: { depthTest: false },
          }),
        ]
      : []),
    ...(activeFlowMarkers.length
      ? [
          new ScatterplotLayer({
            id: 'active-flow-markers',
            data: activeFlowMarkers,
            pickable: false,
            stroked: false,
            filled: true,
            radiusUnits: 'pixels',
            getPosition: (d) => d.position,
            getRadius: (d) => 2.5 + d.strength * 2.2,
            radiusMinPixels: 2.5,
            radiusMaxPixels: 6,
            getFillColor: (d) =>
              d.beliefState === 'adopted'
                ? [74, 158, 255, 220]
                : d.beliefState === 'rejected'
                  ? [232, 133, 106, 220]
                  : [192, 184, 176, 210],
            parameters: { depthTest: false },
          }),
        ]
      : []),
    ...(hotspots.length
      ? [
          new ScatterplotLayer({
            id: 'cluster-zones-glow',
            data: hotspots,
            getPosition: (d) => [d.lng, d.lat],
            getRadius: (d) => d.radiusMeters * 1.12,
            radiusUnits: 'meters',
            getFillColor: (d) => {
              const [r, g, b] = clusterFill(d.state);
              return [r, g, b, 18] as [number, number, number, number];
            },
            stroked: false,
            pickable: false,
          }),
          new ScatterplotLayer({
            id: 'cluster-zones',
            data: hotspots,
            getPosition: (d) => [d.lng, d.lat],
            getRadius: (d) => d.radiusMeters,
            radiusUnits: 'meters',
            getFillColor: (d) => clusterFill(d.state),
            stroked: false,
            pickable: false,
          }),
          new TextLayer({
            id: 'cluster-badges',
            data: hotspotLabels,
            pickable: false,
            background: true,
            getBackgroundColor: [12, 12, 15, 214],
            getBorderColor: [255, 255, 255, 38],
            backgroundPadding: [10, 5],
            getPosition: (d) => d.position,
            getText: (d) => d.label,
            getSize: 11,
            sizeUnits: 'pixels',
            getColor: [240, 237, 232, 235],
            getTextAnchor: 'middle',
            getAlignmentBaseline: 'center',
            getPixelOffset: [0, -2],
            fontFamily: 'IBM Plex Sans, system-ui, sans-serif',
          }),
        ]
      : []),
    new ScatterplotLayer<Agent>({
      id: 'agent-ground-glow',
      data: agents,
      pickable: false,
      stroked: false,
      filled: true,
      opacity: 0.65,
      radiusUnits: 'pixels',
      getPosition: (a) => a.position,
      getRadius: (a) => 12 + (a.confidence ?? 0.5) * 7,
      radiusMinPixels: 12,
      radiusMaxPixels: 22,
      getFillColor: (a) => {
        const [r, g, b] = COLORS[a.state];
        return [r, g, b, 34 + Math.round((a.confidence ?? 0.5) * 24)] as [number, number, number, number];
      },
      parameters: { depthTest: false },
    }),
    new ScatterplotLayer<Agent>({
      id: 'agent-hit-area',
      data: agents,
      pickable: true,
      stroked: false,
      filled: true,
      opacity: 0.01,
      radiusUnits: 'pixels',
      getPosition: (a) => a.position,
      getRadius: () => markerSize(viewState.zoom, c.zoom) * 0.72,
      radiusMinPixels: 18,
      radiusMaxPixels: 30,
      getFillColor: () => [255, 255, 255, 2] as [number, number, number, number],
      parameters: { depthTest: false },
    }),
    new IconLayer<Agent>({
      id: 'people',
      data: agents,
      pickable: true,
      billboard: true,
      sizeUnits: 'pixels',
      sizeScale: 1,
      alphaCutoff: 0.01,
      getPosition: (a) => a.position,
      getIcon: (a) => PERSON_ICONS[a.state],
      getSize: () => markerSize(viewState.zoom, c.zoom),
      parameters: { depthTest: false },
    }),
    ...(pinned
      ? [
          new ScatterplotLayer<Agent>({
            id: 'person-selected-ring',
            data: [mergedPopupAgent ?? pinned.agent],
            pickable: false,
            stroked: true,
            filled: false,
            radiusUnits: 'pixels',
            getPosition: (a) => a.position,
            getRadius: () => markerSize(viewState.zoom, c.zoom) * 0.92,
            radiusMinPixels: 22,
            radiusMaxPixels: 38,
            getLineColor: [240, 237, 232, 220],
            lineWidthMinPixels: 2.4,
            parameters: { depthTest: false },
          }),
        ]
      : []),
  ];

  return (
    <div ref={containerRef} className="relative h-full min-h-[420px] bg-bg-deep">
      {!MAPBOX_TOKEN && (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-4 text-center">
          <div className="rounded-[20px] border border-white/[0.08] bg-bg-surface/90 px-4 py-3 font-mono text-[10px] text-text-secondary">
            Set <span className="text-pastel-2/90">VITE_MAPBOX_TOKEN</span> in <code className="text-text-primary">frontend/.env</code> to load the basemap.
          </div>
        </div>
      )}

      <DeckGL
        viewState={viewState}
        controller
        layers={layers}
        onViewStateChange={(event: { viewState: typeof viewState }) => setViewState(event.viewState)}
        onClick={handleDeckClick}
        style={{ position: 'absolute', inset: 0 }}
      >
        {MAPBOX_TOKEN && (
          <ReactMap
            ref={mapRef}
            mapboxAccessToken={MAPBOX_TOKEN}
            mapStyle={MAP_STYLE}
            reuseMaps
            maxPitch={85}
          >
            <Layer {...BUILDINGS_LAYER} />
          </ReactMap>
        )}
      </DeckGL>

      <div className="pointer-events-none absolute bottom-4 left-4 z-10 w-[220px] rounded-[12px] border border-white/[0.12] bg-[rgba(12,12,15,0.86)] p-3 shadow-[0_12px_30px_rgba(0,0,0,0.28)] backdrop-blur-sm">
        <div className="space-y-2">
          <LegendRow icon={createLegendPerson('#4A9EFF')} label="Adoption" />
          <LegendRow icon={createLegendPerson('#E8856A')} label="Rejection" />
          <LegendRow icon={createLegendPerson('#C0B8B0')} label="Neutral / Uncommitted" />
          <div className="mt-3 flex items-center gap-3">
            <div className="relative h-3 w-12">
              <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-white/25" />
              <div className="absolute left-0 right-0 top-1/2 h-[1.5px] -translate-y-1/2 bg-white/40" />
            </div>
            <span className="text-xs text-text-secondary">Connection strength</span>
          </div>
        </div>
      </div>

      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(circle at 50% 45%, rgba(255,255,255,0.02) 0%, rgba(9,14,22,0.05) 40%, rgba(7,11,18,0.52) 100%)',
        }}
      />
    </div>
  );
};

function LegendRow({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-6 w-5 items-center justify-center">{icon}</div>
      <span className="text-xs text-text-secondary">{label}</span>
    </div>
  );
}
