/**
 * Real-world places (parks, schools, hospitals, landmarks) for each target city.
 * Static GeoJSON — no API required. Data sourced from OpenStreetMap.
 */

export interface CityPlace {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
  properties: {
    name: string;
    kind: 'park' | 'school' | 'hospital' | 'landmark' | 'government' | 'community_center';
    city_id: string;
    address?: string;
  };
}

export type CityPlaces = CityPlace[];

// ---- Los Angeles ----
const LA_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2851, 34.0224] }, properties: { name: 'Exposition Park', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.4731, 34.0740] }, properties: { name: 'Will Rogers State Park', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.3392, 33.9868] }, properties: { name: 'Kenneth Hahn Park', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2551, 33.9844] }, properties: { name: 'South Park Recreation Center', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2853, 33.9601] }, properties: { name: 'Chesterfield Square Park', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.3267, 33.9416] }, properties: { name: 'Darby Park', kind: 'park', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2437, 34.0522] }, properties: { name: 'Los Angeles City Hall', kind: 'government', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2437, 34.0579] }, properties: { name: 'LA County USC Medical Center', kind: 'hospital', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2892, 34.0639] }, properties: { name: 'Kaiser Permanente LA', kind: 'hospital', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2603, 34.0339] }, properties: { name: 'Orthopaedic Hospital', kind: 'hospital', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2878, 34.0207] }, properties: { name: 'USC', kind: 'school', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2869, 33.9425] }, properties: { name: 'LA Southwest College', kind: 'school', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2439, 34.0697] }, properties: { name: 'Dodger Stadium', kind: 'landmark', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2673, 34.0431] }, properties: { name: 'Staples Center', kind: 'landmark', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.4345, 33.9845] }, properties: { name: 'Venice Beach', kind: 'landmark', city_id: 'los-angeles-ca' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.2851, 33.9889] }, properties: { name: 'Vermont Square Library', kind: 'community_center', city_id: 'los-angeles-ca' } },
];

// ---- New York City ----
const NYC_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9712, 40.7831] }, properties: { name: 'Central Park', kind: 'park', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9222, 40.8270] }, properties: { name: 'Yankee Stadium', kind: 'landmark', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9680, 40.7590] }, properties: { name: 'Central Park Zoo', kind: 'park', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9967, 40.7262] }, properties: { name: 'Washington Square Park', kind: 'park', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9857, 40.7484] }, properties: { name: 'Bryant Park', kind: 'park', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-74.0023, 40.7143] }, properties: { name: 'City Hall', kind: 'government', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9554, 40.7876] }, properties: { name: 'Mount Sinai Hospital', kind: 'hospital', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9538, 40.7642] }, properties: { name: 'Weill Cornell Medical', kind: 'hospital', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9626, 40.8075] }, properties: { name: 'Columbia University', kind: 'school', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9965, 40.7293] }, properties: { name: 'NYU', kind: 'school', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9856, 40.7587] }, properties: { name: 'Times Square', kind: 'landmark', city_id: 'new-york-ny' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-74.0134, 40.7017] }, properties: { name: 'The Battery', kind: 'park', city_id: 'new-york-ny' } },
];

// ---- Chicago ----
const CHICAGO_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6553, 41.8819] }, properties: { name: 'Union Park', kind: 'park', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6183, 41.8671] }, properties: { name: 'Grant Park', kind: 'park', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6354, 41.9260] }, properties: { name: 'Lincoln Park', kind: 'park', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6313, 41.8837] }, properties: { name: 'City Hall', kind: 'government', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6278, 41.8781] }, properties: { name: 'Willis Tower', kind: 'landmark', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6074, 41.7894] }, properties: { name: 'University of Chicago', kind: 'school', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6634, 41.8940] }, properties: { name: 'Rush University Medical', kind: 'hospital', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6744, 41.8819] }, properties: { name: 'Cook County Hospital', kind: 'hospital', city_id: 'chicago-il' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-87.6244, 41.8827] }, properties: { name: 'Millennium Park', kind: 'park', city_id: 'chicago-il' } },
];

// ---- Miami ----
const MIAMI_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.1866, 25.7934] }, properties: { name: 'Bayfront Park', kind: 'park', city_id: 'miami-fl' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.1990, 25.7825] }, properties: { name: 'Miami City Hall', kind: 'government', city_id: 'miami-fl' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.2115, 25.7907] }, properties: { name: 'Jackson Memorial Hospital', kind: 'hospital', city_id: 'miami-fl' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.2804, 25.7173] }, properties: { name: 'University of Miami', kind: 'school', city_id: 'miami-fl' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.1320, 25.7842] }, properties: { name: 'South Beach', kind: 'landmark', city_id: 'miami-fl' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-80.1957, 25.7475] }, properties: { name: 'Vizcaya Gardens', kind: 'park', city_id: 'miami-fl' } },
];

// ---- Phoenix ----
const PHOENIX_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-112.0740, 33.4484] }, properties: { name: 'Phoenix City Hall', kind: 'government', city_id: 'phoenix-az' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-112.0159, 33.4655] }, properties: { name: 'Papago Park', kind: 'park', city_id: 'phoenix-az' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-112.0660, 33.4791] }, properties: { name: 'Banner University Medical', kind: 'hospital', city_id: 'phoenix-az' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-111.9312, 33.4214] }, properties: { name: 'ASU Tempe', kind: 'school', city_id: 'phoenix-az' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-112.0915, 33.4517] }, properties: { name: 'Camelback Mountain', kind: 'landmark', city_id: 'phoenix-az' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-112.1025, 33.4608] }, properties: { name: 'Encanto Park', kind: 'park', city_id: 'phoenix-az' } },
];

// ---- Houston ----
const HOUSTON_PLACES: CityPlaces = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.3698, 29.7604] }, properties: { name: 'Houston City Hall', kind: 'government', city_id: 'houston-tx' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.3584, 29.7575] }, properties: { name: 'Discovery Green', kind: 'park', city_id: 'houston-tx' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.3889, 29.7164] }, properties: { name: 'Hermann Park', kind: 'park', city_id: 'houston-tx' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.4009, 29.7090] }, properties: { name: 'Texas Medical Center', kind: 'hospital', city_id: 'houston-tx' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.3419, 29.7216] }, properties: { name: 'University of Houston', kind: 'school', city_id: 'houston-tx' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-95.3621, 29.7517] }, properties: { name: 'Minute Maid Park', kind: 'landmark', city_id: 'houston-tx' } },
];

const PLACES_BY_CITY: Record<string, CityPlaces> = {
  'los-angeles-ca': LA_PLACES,
  'new-york-ny': NYC_PLACES,
  'chicago-il': CHICAGO_PLACES,
  'miami-fl': MIAMI_PLACES,
  'phoenix-az': PHOENIX_PLACES,
  'houston-tx': HOUSTON_PLACES,
};

export function loadCityPlaces(cityId: string): CityPlaces {
  return PLACES_BY_CITY[cityId] ?? [];
}
