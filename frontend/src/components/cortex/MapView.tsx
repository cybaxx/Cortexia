import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, { type MapRef } from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { getCityById } from '@/data/cities';
import { generateAgentsForRegion, generateArcs, COLORS, type Agent } from '@/lib/agents';
import { AgentPopup } from './AgentPopup';
import { useCortexStore } from '@/store/cortex';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

function mergeAgent(base: Agent, o?: Partial<Agent>): Agent {
  if (!o) return base;
  return { ...base, ...o, position: base.position };
}

const INITIAL_ZOOM = 2.5;

export const MapView = () => {
  const cityId = useCortexStore((s) => s.cityId);
  const overrides = useCortexStore((s) => s.agentOverrides);
  const rejectPhase = useCortexStore((s) => s.injectPhase);
  const hotspots = useCortexStore((s) => s.rejectionHotspots);

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

  const agents = useMemo(
    () => baseAgents.map((a) => mergeAgent(a, overrides[a.id])),
    [baseAgents, overrides],
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
          getFillColor: [232, 140, 125, 75],
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
      getSourceColor: [232, 180, 140, showStrain ? 170 : 100],
      getTargetColor: [160, 190, 235, showStrain ? 165 : 95],
      getWidth: showStrain ? 1.5 : 1.1,
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

  const mergedPopupAgent = useMemo(() => {
    if (!pinned) return null;
    return mergeAgent(
      baseAgents.find((a) => a.id === pinned.agent.id) || pinned.agent,
      overrides[pinned.agent.id],
    );
  }, [pinned, baseAgents, overrides]);

  return (
    <div className="absolute inset-0 bg-bg-deep">
      {!MAPBOX_TOKEN && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="font-mono text-[10px] text-text-secondary bg-bg-surface/90 border border-white/[0.08] px-3 py-2 rounded-sm">
            Set <span className="text-accent-adopt">VITE_MAPBOX_TOKEN</span> in <code className="text-text-primary">frontend/.env</code> to load the basemap.
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
        <AgentPopup
          agent={mergedPopupAgent}
          x={pinned.x}
          y={pinned.y}
          onClose={() => setPinned(null)}
        />
      )}

      {showStrain && (
        <div className="pointer-events-none absolute bottom-10 left-1/2 -translate-x-1/2 z-10 max-w-sm text-center">
          <p className="font-mono text-[9px] text-rose-200/80 bg-bg-deep/85 border border-rose-500/15 rounded-sm px-2 py-1">
            Red regions: modelled resistance clusters. Click an agent to tune parameters and view the brain sim.
          </p>
        </div>
      )}

      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at center, transparent 55%, rgba(11,15,25,0.55) 100%)',
        }}
      />
    </div>
  );
};
