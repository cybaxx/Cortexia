import { useEffect, useMemo, useRef, useState } from 'react';
import Map, { type MapRef } from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { generateAgents, generateArcs, COLORS, type Agent } from '@/lib/agents';
import { AgentPopup } from './AgentPopup';
import { useCortexStore } from '@/store/cortex';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

const FINAL_VIEW = {
  longitude: -118.2437,
  latitude: 34.0522,
  zoom: 10.5,
  pitch: 35,
  bearing: 0,
};

const INITIAL_VIEW = {
  longitude: -118.2437,
  latitude: 34.0522,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
};

export const MapView = () => {
  const [viewState, setViewState] = useState<any>(INITIAL_VIEW);
  const [hover, setHover] = useState<{ agent: Agent; x: number; y: number } | null>(null);
  const mapRef = useRef<MapRef>(null);
  const rejectPhase = useCortexStore((s) => s.injectPhase);
  const hotspots = useCortexStore((s) => s.rejectionHotspots);

  const agents = useMemo(() => generateAgents(110), []);
  const arcs = useMemo(() => generateArcs(agents, 38), [agents]);
  const showStrain = rejectPhase === 'propagating' || rejectPhase === 'report' || rejectPhase === 'complete';

  useEffect(() => {
    const t = setTimeout(() => {
      setViewState({
        ...FINAL_VIEW,
        transitionDuration: 2800,
        transitionInterpolator: undefined,
      });
    }, 250);
    return () => clearTimeout(t);
  }, []);

  const rejectLayer =
    showStrain && hotspots.length > 0
      ? new ScatterplotLayer({
          id: 'rejection-clusters',
          data: hotspots,
          getPosition: (d) => [d.lng, d.lat],
          getRadius: (d) => d.radiusMeters,
          radiusUnits: 'meters',
          getFillColor: [244, 63, 94, 70],
          stroked: false,
          pickable: false,
        })
      : null;

  const layers = [
    new ArcLayer<{ source: [number, number]; target: [number, number] }>({
      id: 'influence-arcs',
      data: arcs,
      getSourcePosition: (d) => d.source,
      getTargetPosition: (d) => d.target,
      getSourceColor: [245, 158, 11, showStrain ? 160 : 100],
      getTargetColor: [59, 130, 246, showStrain ? 150 : 90],
      getWidth: showStrain ? 1.6 : 1.1,
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
      getLineColor: [255, 255, 255, 30],
      lineWidthMinPixels: 0.5,
      onHover: (info) => {
        if (info.object && info.x != null && info.y != null) {
          setHover({ agent: info.object as Agent, x: info.x, y: info.y });
        } else {
          setHover(null);
        }
      },
    }),
  ];

  return (
    <div className="absolute inset-0 bg-bg-deep">
      {!MAPBOX_TOKEN && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="font-mono text-[10px] text-text-secondary bg-bg-surface/90 border border-white/[0.08] px-3 py-2 rounded-sm">
            Set <span className="text-accent-adopt">VITE_MAPBOX_TOKEN</span> in <code className="text-text-primary">frontend/.env</code> to load the LA basemap.
          </div>
        </div>
      )}
      <DeckGL
        viewState={viewState}
        controller
        layers={layers}
        onViewStateChange={(e: any) => setViewState(e.viewState)}
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

      {hover && <AgentPopup agent={hover.agent} x={hover.x} y={hover.y} />}

      {showStrain && (
        <div className="pointer-events-none absolute bottom-20 left-1/2 -translate-x-1/2 z-10 max-w-sm text-center">
          <p className="font-mono text-[9px] text-rose-300/90 bg-bg-deep/80 border border-rose-500/20 rounded-sm px-2 py-1">
            Red wash = modelled rejection clusters (defensive posture & strain). Arc intensity follows signal phase.
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
