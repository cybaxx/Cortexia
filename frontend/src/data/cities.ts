export interface LandZone {
  lngMin: number;
  lngMax: number;
  latMin: number;
  latMax: number;
}

export interface CityPreset {
  id: string;
  label: string;
  center: { longitude: number; latitude: number; zoom: number };
  /** Degrees half-span for synthetic agent scatter */
  span: number;
  /** Rectangular land zones — agents only spawn inside these, avoiding water */
  landZones: LandZone[];
}

export const CITY_PRESETS: CityPreset[] = [
  {
    id: 'la',
    label: 'Los Angeles, CA',
    center: { longitude: -118.2437, latitude: 34.0522, zoom: 10.5 },
    span: 0.22,
    landZones: [
      // Central LA / Hollywood / Mid-City
      { lngMin: -118.35, lngMax: -118.14, latMin: 33.98, latMax: 34.14 },
      // East LA / Boyle Heights / Monterey Park
      { lngMin: -118.18, lngMax: -118.01, latMin: 33.97, latMax: 34.08 },
      // South LA / Inglewood (above coast)
      { lngMin: -118.37, lngMax: -118.20, latMin: 33.92, latMax: 33.98 },
    ],
  },
  {
    id: 'sf',
    label: 'San Francisco, CA',
    center: { longitude: -122.4194, latitude: 37.7749, zoom: 11 },
    span: 0.12,
    landZones: [
      // SF peninsula (avoids bay to the east and ocean to far west)
      { lngMin: -122.51, lngMax: -122.38, latMin: 37.71, latMax: 37.81 },
      // Daly City / Outer Sunset southern strip
      { lngMin: -122.46, lngMax: -122.38, latMin: 37.70, latMax: 37.71 },
    ],
  },
  {
    id: 'sd',
    label: 'San Diego, CA',
    center: { longitude: -117.1611, latitude: 32.7157, zoom: 10.5 },
    span: 0.18,
    landZones: [
      // North SD — Mission Hills, North Park, SDSU area, Kearny Mesa
      { lngMin: -117.22, lngMax: -117.05, latMin: 32.73, latMax: 32.80 },
      // Central / Downtown east of bay
      { lngMin: -117.17, lngMax: -117.05, latMin: 32.69, latMax: 32.73 },
      // Southeast / Chula Vista north
      { lngMin: -117.13, lngMax: -117.05, latMin: 32.64, latMax: 32.69 },
    ],
  },
  {
    id: 'sj',
    label: 'San Jose, CA',
    center: { longitude: -121.8863, latitude: 37.3382, zoom: 10.5 },
    span: 0.15,
    landZones: [
      // San Jose urban core
      { lngMin: -121.97, lngMax: -121.82, latMin: 37.27, latMax: 37.41 },
    ],
  },
  {
    id: 'sac',
    label: 'Sacramento, CA',
    center: { longitude: -121.4944, latitude: 38.5816, zoom: 10 },
    span: 0.14,
    landZones: [
      // Sacramento urban core
      { lngMin: -121.57, lngMax: -121.42, latMin: 38.52, latMax: 38.64 },
    ],
  },
];

export function getCityById(id: string): CityPreset {
  return CITY_PRESETS.find((c) => c.id === id) ?? CITY_PRESETS[0];
}
