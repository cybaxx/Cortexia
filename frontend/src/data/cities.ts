export interface CityPreset {
  id: string;
  label: string;
  center: { longitude: number; latitude: number; zoom: number };
  /** Degrees half-span for synthetic agent scatter */
  span: number;
}

export const CITY_PRESETS: CityPreset[] = [
  {
    id: 'la',
    label: 'Los Angeles, CA',
    center: { longitude: -118.2437, latitude: 34.0522, zoom: 10.5 },
    span: 0.22,
  },
  {
    id: 'sf',
    label: 'San Francisco, CA',
    center: { longitude: -122.4194, latitude: 37.7749, zoom: 11 },
    span: 0.12,
  },
  {
    id: 'sd',
    label: 'San Diego, CA',
    center: { longitude: -117.1611, latitude: 32.7157, zoom: 10.5 },
    span: 0.18,
  },
  {
    id: 'sj',
    label: 'San Jose, CA',
    center: { longitude: -121.8863, latitude: 37.3382, zoom: 10.5 },
    span: 0.15,
  },
  {
    id: 'sac',
    label: 'Sacramento, CA',
    center: { longitude: -121.4944, latitude: 38.5816, zoom: 10 },
    span: 0.14,
  },
];

export function getCityById(id: string): CityPreset {
  return CITY_PRESETS.find((c) => c.id === id) ?? CITY_PRESETS[0];
}
