import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, { type MapRef } from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { getCityById } from '@/data/cities';
import { generateAgentsForRegion, generateArcs, COLORS, beliefToAgentState, type Agent } from '@/lib/agents';
import { AgentInspectionModal } from './AgentInspectionModal';
import { useCortexStore } from '@/store/cortex';
import type { AgentSimulationPayload } from '@/types/simulation';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

function mergeAgent(base: Agent, o?: Partial<Agent>): Agent {
  if (!o) return base;
  return { ...base, ...o, position: base.position };
}

function applyPayload(base: Agent, p: AgentSimulationPayload | undefined, o?: Partial<Agent>): Agent {
  const m = p?.tribe_neurological_metrics;
  const pos: [number, number] = p
    ? [p.longitude, p.latitude]
    : base.position;
  const st = p ? beliefToAgentState(p.belief_state) : base.state;
  return mergeAgent(
    {
      ...base,
      position: pos,
      state: st,
      cognitiveLoad: m ? m.cognitive_load : base.cognitiveLoad,
      emotionalAgitation: m ? m.emotional_friction : base.emotionalAgitation,
      defensivePosture: m ? m.defensive_activation : base.defensivePosture,
    },
    o,
  );
}

const INITIAL_ZOOM = 2.5;

export const MapView = () => {
  const cityId = useCortexStore((s) => s.cityId);
  const overrides = useCortexStore((s) => s.agentOverrides);
  const rejectPhase = useCortexStore((s) => s.injectPhase);
  const hotspots = useCortexStore((s) => s.rejectionHotspots);
  const agentSimulationById = useCortexStore((s) => s.agentSimulationById);

  const city = getCityById(cityId);
  const c = city.center;

  const [viewState, setViewState] = useState({
    longitude: c.longitude,
    latitude: c.latitude,
    zoom: INITIAL_ZOOM,
    pitch: 0,
    bearing: 0,
  });
  const [pinned, setPinned] = useState<{ agent: Agent; x: number; y: number } | null>(null);
  const mapRef = useRef<MapRef>(null);

  const baseAgents = useMemo(
    () => generateAgentsForRegion(c.longitude, c.latitude, city.span, 110),
    [c.latitude, c.longitude, city.span],
  );

  const hasServerAgents = Object.keys(agentSimulationById).length > 0;

  const agents = useMemo(
    () =>
      baseAgents.map((a) => {
        const p = agentSimulationById[a.id];
        return applyPayload(a, p, overrides[a.id]);
      }),
    [baseAgents, agentSimulationById, overrides],
  );

  const arcs = useMemo(() => generateArcs(agents, 40), [agents]);

  useEffect(() => {
    setPinned(null);
    setViewState((vs) => ({
      ...vs,
      longitude: c.longitude,
      latitude: c.latitude,
      zoom: INITIAL_ZOOM,
      pitch: 0,
    }));
  }, [cityId, c.latitude, c.longitude]);

  useEffect(() => {
    const t = setTimeout(() => {
      setViewState((vs) => ({
        ...vs,
        longitude: c.longitude,
        latitude: c.latitude,
        zoom: c.zoom,
        pitch: 35,
        transitionDuration: 2400,
      }));
    }, 200);
    return () => clearTimeout(t);
  }, [c.latitude, c.longitude, c.zoom]);

  const showStrain = rejectPhase === 'propagating' || rejectPhase === 'report' || rejectPhase === 'complete';

  const handleDeckClick = useCallback((info: { object?: unknown; x?: number; y?: number }) => {
    const o = info.object as Agent | undefined;
    if (o && typeof o.id === 'number' && o.position && info.x != null && info.y != null) {
      setPinned({ agent: o, x: info.x, y: info.y });
    } else {
      setPinned(null);
    }
  }, []);

  const rejectLayer =
    showStrain && hotspots.length > 0
      ? new ScatterplotLayer({
          id: 'rejection-clusters',
          data: hotspots,
          getPosition: (d) => [d.lng, d.lat],
          getRadius: (d) => d.radiusMeters,
          radiusUnits: 'meters',
          getFillColor: [255, 191, 166, 88],
          stroked: false,
          pickable: false,
        })
      : null;

  const layers = [
    new ArcLayer({
      id: 'influence-arcs',
      data: arcs,
      getSourcePosition: (d) => d.source,
      getTargetPosition: (d) => d.target,
      getSourceColor: [188, 231, 219, hasServerAgents && showStrain ? 46 : 18],
      getTargetColor: [160, 214, 255, hasServerAgents && showStrain ? 46 : 18],
      getWidth: showStrain && hasServerAgents ? 0.8 : 0.4,
      greatCircle: false,
    }),
    ...(rejectLayer ? [rejectLayer] : []),
    new ScatterplotLayer<Agent>({
      id: 'agents',
      data: agents,
      pickable: true,
      stroked: true,
      filled: true,
      getPosition: (a) => a.position,
      getRadius: 90,
      radiusMinPixels: 2.5,
      radiusMaxPixels: 7,
      getFillColor: (a) => COLORS[a.state],
      getLineColor: [255, 255, 255, 32],
      lineWidthMinPixels: 0.5,
    }),
  ];

  const payloadForPin = useMemo(
    () => (pinned ? agentSimulationById[pinned.agent.id] : undefined),
    [pinned, agentSimulationById],
  );

  const mergedPopupAgent = useMemo(() => {
    if (!pinned) return null;
    const p = agentSimulationById[pinned.agent.id];
    const base = baseAgents.find((a) => a.id === pinned.agent.id) || pinned.agent;
    return applyPayload(base, p, overrides[pinned.agent.id]);
  }, [pinned, baseAgents, agentSimulationById, overrides]);

  return (
    <div className="absolute inset-0 bg-bg-deep">
      {!MAPBOX_TOKEN && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="rounded-[20px] border border-white/[0.08] bg-bg-surface/90 px-3 py-2 font-mono text-[10px] text-text-secondary">
            Set <span className="text-pastel-2/90">VITE_MAPBOX_TOKEN</span> in <code className="text-text-primary">frontend/.env</code> to load the basemap.
          </div>
        </div>
      )}
      <DeckGL
        viewState={viewState}
        controller
        layers={layers}
        onViewStateChange={(e: any) => setViewState(e.viewState)}
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
        />
      )}

      {hasServerAgents && showStrain && (
        <div className="pointer-events-none absolute bottom-10 left-1/2 -translate-x-1/2 z-10 max-w-sm text-center">
          <p className="rounded-full border border-pastel-3/20 bg-bg-deep/[0.85] px-3 py-1.5 font-mono text-[9px] text-pastel-3/90 shadow-lg">
            Node color reflects modelled belief state. Click a node to inspect K2 and TRIBE fields.
          </p>
        </div>
      )}

      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(circle at 50% 45%, rgba(255,255,255,0.02) 0%, rgba(9,14,22,0.06) 42%, rgba(7,11,18,0.58) 100%)',
        }}
      />
    </div>
  );
};
