import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, { type MapRef } from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
import { getCityById } from '@/data/cities';
import { COLORS, beliefToAgentState, type Agent } from '@/lib/agents';
import { useCortexStore } from '@/store/cortex';
import type { AgentSimulationPayload } from '@/types/simulation';
import { AgentInspectionModal } from './AgentInspectionModal';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
const INITIAL_ZOOM = 2.5;

function mergeAgent(base: Agent, override?: Partial<Agent>): Agent {
  if (!override) return base;
  return { ...base, ...override, position: base.position };
}

function applyPayload(base: Agent, payload: AgentSimulationPayload | undefined, override?: Partial<Agent>): Agent {
  const metrics = payload?.tribe_neurological_metrics;
  return mergeAgent(
    {
      ...base,
      position: payload ? [payload.longitude, payload.latitude] : base.position,
      state: payload ? beliefToAgentState(payload.belief_state) : base.state,
      cognitiveLoad: metrics ? metrics.cognitive_load : base.cognitiveLoad,
      emotionalAgitation: metrics ? metrics.emotional_friction : base.emotionalAgitation,
      defensivePosture: metrics ? metrics.defensive_activation : base.defensivePosture,
    },
    override,
  );
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
    },
    override,
  );
}

export const MapView = () => {
  const cityId = useCortexStore((s) => s.cityId);
  const overrides = useCortexStore((s) => s.agentOverrides);
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const agentSimulationById = useCortexStore((s) => s.agentSimulationById);
  const status = useCortexStore((s) => s.status);
  const latestResponse = useCortexStore((s) => s.latestResponse);

  const city = getCityById(cityId);
  const c = city.center;
  const hotspots = spreadModel?.hotspots ?? [];
  const hasServerAgents = Object.keys(agentSimulationById).length > 0;

  const [viewState, setViewState] = useState({
    longitude: c.longitude,
    latitude: c.latitude,
    zoom: INITIAL_ZOOM,
    pitch: 0,
    bearing: 0,
  });
  const [pinned, setPinned] = useState<{ agent: Agent; x: number; y: number } | null>(null);
  const mapRef = useRef<MapRef>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const agents = useMemo(
    () =>
      Object.values(agentSimulationById)
        .sort((a, b) => a.id - b.id)
        .map((payload) => buildAgentFromPayload(payload, overrides[payload.id])),
    [agentSimulationById, overrides],
  );

  useEffect(() => {
    setPinned(null);
    setViewState((vs) => ({
      ...vs,
      longitude: c.longitude,
      latitude: c.latitude,
      zoom: INITIAL_ZOOM,
      pitch: 0,
      bearing: 0,
    }));
  }, [cityId, c.latitude, c.longitude]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setViewState((vs) => ({
        ...vs,
        longitude: c.longitude,
        latitude: c.latitude,
        zoom: c.zoom,
        pitch: 35,
        transitionDuration: 1800,
      }));
    }, 180);
    return () => clearTimeout(timeout);
  }, [c.latitude, c.longitude, c.zoom]);

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
    } else {
      setPinned(null);
    }
  }, [c.zoom]);

  const layers = [
    ...(hotspots.length
      ? [
          new ScatterplotLayer({
            id: 'risk-hotspots',
            data: hotspots,
            getPosition: (d) => [d.lng, d.lat],
            getRadius: (d) => d.radiusMeters,
            radiusUnits: 'meters',
            getFillColor: (d) =>
              d.state === 'adopted'
                ? [160, 214, 255, 86]
                : d.state === 'rejected'
                  ? [255, 191, 166, 96]
                  : [188, 231, 219, 74],
            stroked: false,
            pickable: false,
          }),
        ]
      : []),
    new ScatterplotLayer<Agent>({
      id: 'agents',
      data: agents,
      pickable: true,
      stroked: true,
      filled: true,
      getPosition: (a) => a.position,
      getRadius: 90,
      radiusMinPixels: 3,
      radiusMaxPixels: 8,
      getFillColor: (a) => COLORS[a.state],
      getLineColor: [255, 255, 255, 40],
      lineWidthMinPixels: 0.5,
    }),
  ];

  const payloadForPin = pinned ? agentSimulationById[pinned.agent.id] : undefined;
  const mergedPopupAgent = useMemo(() => {
    if (!pinned) return null;
    const payload = agentSimulationById[pinned.agent.id];
    if (!payload) return applyPayload(pinned.agent, undefined, overrides[pinned.agent.id]);
    return buildAgentFromPayload(payload, overrides[payload.id]);
  }, [agentSimulationById, overrides, pinned]);

  return (
    <div ref={containerRef} className="relative h-full min-h-[420px] bg-bg-deep">
      {!MAPBOX_TOKEN && (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-4 text-center">
          <div className="rounded-[20px] border border-white/[0.08] bg-bg-surface/90 px-4 py-3 font-mono text-[10px] text-text-secondary">
            Set <span className="text-pastel-2/90">VITE_MAPBOX_TOKEN</span> in <code className="text-text-primary">frontend/.env</code> to load the basemap.
          </div>
        </div>
      )}

      {!hasServerAgents && (
        <div className="pointer-events-none absolute inset-x-6 top-6 z-10 flex justify-center">
          <div className="rounded-[20px] border border-white/[0.08] bg-bg-surface/90 px-4 py-3 text-center font-mono text-[10px] text-text-secondary">
            Run a simulation to populate the map with live TRIBE-backed agents.
          </div>
        </div>
      )}

      <DeckGL
        viewState={viewState}
        controller
        layers={layers}
        onViewStateChange={(event: any) => setViewState(event.viewState)}
        onClick={handleDeckClick}
        style={{ position: 'absolute', inset: 0 }}
      >
        {MAPBOX_TOKEN && (
          <Map
            ref={mapRef}
            mapboxAccessToken={MAPBOX_TOKEN}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            reuseMaps
          />
        )}
      </DeckGL>

      {mergedPopupAgent && pinned && (
        <AgentInspectionModal
          agent={mergedPopupAgent}
          x={pinned.x}
          y={pinned.y}
          onClose={() => setPinned(null)}
          payload={payloadForPin}
          runId={latestResponse?.run_id}
        />
      )}

      <div className="pointer-events-none absolute left-4 top-4 z-10 flex flex-wrap gap-2">
        <div className="rounded-full border border-white/[0.08] bg-bg-deep/[0.78] px-3 py-1.5 font-mono text-[9px] text-text-secondary">
          Pastel blue: adoption
        </div>
        <div className="rounded-full border border-white/[0.08] bg-bg-deep/[0.78] px-3 py-1.5 font-mono text-[9px] text-text-secondary">
          Pastel peach: rejection clusters
        </div>
        <div className="rounded-full border border-white/[0.08] bg-bg-deep/[0.78] px-3 py-1.5 font-mono text-[9px] text-text-secondary">
          Mint: neutral / uncommitted
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
