import React, { useState, useEffect, useCallback } from 'react';
import {
  MapPin,
  Search,
  Navigation,
  Building,
  RefreshCw,
  ExternalLink,
  Compass,
  AlertTriangle,
} from 'lucide-react';
import {
  ExternalStatusResponse,
  GeocodingCandidate,
  NormalizedPlace,
  PlacesResponse,
} from '../types/external';
import {
  fetchExternalStatus,
  fetchNearbyPlaces,
  forwardGeocode,
} from '../services/externalApi';

interface ExternalIntelligencePanelProps {
  initialLocation?: string;
  onSelectForPlanning?: (location: string, places?: NormalizedPlace[]) => void;
  onShowToast?: (msg: string) => void;
}

const PRESET_LOCATIONS = [
  { name: 'Hyderabad (Banjara Hills)', lat: 17.4156, lon: 78.4350, city: 'Hyderabad' },
  { name: 'Hyderabad (Hitec City)', lat: 17.4474, lon: 78.3762, city: 'Hyderabad' },
  { name: 'Bengaluru (Indiranagar)', lat: 12.9784, lon: 77.6408, city: 'Bengaluru' },
  { name: 'Mumbai (Bandra West)', lat: 19.0596, lon: 72.8295, city: 'Mumbai' },
  { name: 'Delhi (Connaught Place)', lat: 28.6315, lon: 77.2167, city: 'New Delhi' },
];

export const ExternalIntelligencePanel: React.FC<ExternalIntelligencePanelProps> = ({
  initialLocation = 'Hyderabad (Banjara Hills)',
  onSelectForPlanning,
  onShowToast,
}) => {
  // Provider health and status
  const [statusData, setStatusData] = useState<ExternalStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(false);

  // Search and Location Selection
  const [searchQuery, setSearchQuery] = useState<string>(initialLocation);
  const [candidates, setCandidates] = useState<GeocodingCandidate[]>([]);
  const [selectedLocationName, setSelectedLocationName] = useState<string>('Banjara Hills, Hyderabad');
  const [selectedLat, setSelectedLat] = useState<number>(17.4156);
  const [selectedLon, setSelectedLon] = useState<number>(78.4350);
  const [isSearchingGeocode, setIsSearchingGeocode] = useState<boolean>(false);

  // Nearby Places State
  const [placesData, setPlacesData] = useState<PlacesResponse | null>(null);
  const [loadingPlaces, setLoadingPlaces] = useState<boolean>(false);
  const [placesError, setPlacesError] = useState<string | null>(null);
  const [selectedRadius, setSelectedRadius] = useState<number>(3000);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  // Load Status on Mount
  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const data = await fetchExternalStatus();
      setStatusData(data);
    } catch (err: any) {
      console.warn('Could not fetch external status:', err);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Load Nearby Places
  const loadPlacesData = useCallback(
    async (lat: number, lon: number, radius: number, cat: string) => {
      setLoadingPlaces(true);
      setPlacesError(null);
      try {
        const res = await fetchNearbyPlaces(lat, lon, radius, cat, 30);
        setPlacesData(res);
      } catch (err: any) {
        setPlacesError(err.message || 'Failed to load nearby places');
      } finally {
        setLoadingPlaces(false);
      }
    },
    []
  );

  // Trigger places fetch on coordinate or filter changes
  useEffect(() => {
    loadPlacesData(selectedLat, selectedLon, selectedRadius, selectedCategory);
  }, [selectedLat, selectedLon, selectedRadius, selectedCategory, loadPlacesData]);

  // Handle Geocoding Search
  const handleGeocodeSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearchingGeocode(true);
    try {
      const res = await forwardGeocode(searchQuery, 6, 'in');
      setCandidates(res.candidates);
      if (res.candidates.length === 0) {
        if (onShowToast) onShowToast(`No matching locations found for "${searchQuery}".`);
      } else {
        const first = res.candidates[0];
        setSelectedLat(first.latitude);
        setSelectedLon(first.longitude);
        setSelectedLocationName(first.display_name);
      }
    } catch (err: any) {
      if (onShowToast) onShowToast(`Geocoding error: ${err.message}`);
    } finally {
      setIsSearchingGeocode(false);
    }
  };

  const handleSelectCandidate = (candidate: GeocodingCandidate) => {
    setSelectedLat(candidate.latitude);
    setSelectedLon(candidate.longitude);
    setSelectedLocationName(candidate.display_name);
    setCandidates([]);
    if (onShowToast) onShowToast(`Location set to: ${candidate.locality || candidate.city || 'Coordinates'}`);
  };

  const handleSelectPreset = (preset: typeof PRESET_LOCATIONS[0]) => {
    setSearchQuery(preset.name);
    setSelectedLat(preset.lat);
    setSelectedLon(preset.lon);
    setSelectedLocationName(preset.name);
    setCandidates([]);
    if (onShowToast) onShowToast(`Selected preset: ${preset.name}`);
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Provider Health Strip */}
      <div className="bg-white border-2 border-black rounded-3xl p-6 shadow-[5px_5px_0px_0px_#000]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b-2 border-black pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-[#BAE6FD] border border-black rounded-full text-xs font-black uppercase tracking-wider">
                Real-World Data
              </span>
              <span className="text-xs font-bold text-slate-500">Spatial Intelligence</span>
            </div>
            <h2 className="text-2xl font-black text-black font-heading mt-1 flex items-center gap-2">
              <Compass className="w-6 h-6 text-black" />
              Venue Discovery Hub
            </h2>
            <p className="text-xs text-slate-600 font-bold mt-0.5">
              Real-world OpenStreetMap physical venue discovery, reverse geocoding, and spatial amenity mapping across India.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Provider status pills */}
            {statusData && (
              <div className="flex items-center gap-1.5 text-xs font-bold bg-slate-50 border border-slate-300 rounded-xl px-3 py-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>OSM Geocoding: {statusData.providers.nominatim?.operational_status || 'ready'}</span>
                <span className="text-slate-400">|</span>
                <span>Overpass API: {statusData.providers.overpass?.operational_status || 'ready'}</span>
                <span className="text-slate-400">|</span>
                <span className="text-slate-500">Cached: {statusData.cached_entries_count}</span>
              </div>
            )}
            <button
              onClick={loadStatus}
              disabled={loadingStatus}
              aria-label="Refresh external provider status"
              className="p-2 border-2 border-black bg-white rounded-xl shadow-[2px_2px_0px_0px_#000] hover:bg-slate-50 active:translate-x-0.5 active:translate-y-0.5 transition-all text-xs font-black flex items-center gap-1 focus-visible:ring-2 focus-visible:ring-black"
              title="Refresh provider status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingStatus ? 'animate-spin' : ''}`} aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* 2. Interactive Location Search & Controls */}
        <div className="space-y-3">
          <form onSubmit={handleGeocodeSearch} className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <MapPin className="w-4 h-4 text-black" aria-hidden="true" />
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search city, neighborhood, or landmark in India"
                placeholder="Search city, neighborhood, or landmark in India (e.g. Banjara Hills, Hyderabad)"
                className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border-2 border-black rounded-xl text-xs font-bold text-black focus:outline-none focus:bg-white focus-visible:ring-2 focus-visible:ring-black"
              />
            </div>

            <button
              type="submit"
              disabled={isSearchingGeocode}
              aria-label="Search location on OpenStreetMap"
              className="px-5 py-2.5 bg-[#FFE600] hover:bg-[#FACC15] text-black font-black text-xs border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] flex items-center justify-center gap-1.5 transition-all active:translate-x-0.5 active:translate-y-0.5 focus-visible:ring-2 focus-visible:ring-black"
            >
              <Search className="w-4 h-4" aria-hidden="true" />
              <span>{isSearchingGeocode ? 'Searching...' : 'Locate on OSM'}</span>
            </button>
          </form>

          {/* Quick Preset Buttons */}
          <div className="flex items-center gap-2 flex-wrap pt-1">
            <span className="text-[11px] font-black text-slate-600 uppercase tracking-wider">India Demo Presets:</span>
            {PRESET_LOCATIONS.map((preset) => (
              <button
                key={preset.name}
                onClick={() => handleSelectPreset(preset)}
                className="px-2.5 py-1 bg-white hover:bg-slate-100 text-black border border-black rounded-lg text-[11px] font-bold shadow-[1px_1px_0px_0px_#000] transition-all"
              >
                {preset.name}
              </button>
            ))}
          </div>

          {/* Candidates Dropdown / List */}
          {candidates.length > 0 && (
            <div className="bg-slate-50 border-2 border-black rounded-2xl p-3 space-y-2 mt-2">
              <span className="text-[11px] font-black uppercase text-slate-600">Select Geocoding Candidate:</span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                {candidates.map((cand, idx) => (
                  <button
                    key={`${cand.place_id || idx}`}
                    onClick={() => handleSelectCandidate(cand)}
                    className="text-left p-2.5 bg-white border border-slate-300 rounded-xl hover:border-black hover:bg-[#FFE600]/20 transition-all text-xs font-bold space-y-0.5"
                  >
                    <div className="text-black font-black truncate">{cand.display_name}</div>
                    <div className="text-[11px] text-slate-500">
                      Coordinates: ({cand.latitude.toFixed(4)}, {cand.longitude.toFixed(4)})
                      {cand.city ? ` • ${cand.city}` : ''}
                      {cand.state ? `, ${cand.state}` : ''}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Active Location Coordinates Banner */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between bg-slate-100 rounded-xl px-4 py-2 text-xs font-bold border border-slate-300 gap-2">
            <div className="flex items-center gap-2 truncate">
              <Navigation className="w-3.5 h-3.5 text-blue-600 shrink-0" />
              <span className="text-slate-500">Active Coordinates:</span>
              <span className="text-black font-black">
                {selectedLat.toFixed(4)}, {selectedLon.toFixed(4)}
              </span>
              <span className="text-slate-400">|</span>
              <span className="truncate text-slate-700 max-w-sm">{selectedLocationName}</span>
            </div>

            {onSelectForPlanning && (
              <button
                onClick={() =>
                  onSelectForPlanning(
                    selectedLocationName,
                    placesData?.places || undefined
                  )
                }
                className="mt-2 sm:mt-0 px-3 py-1 bg-black text-white hover:bg-slate-800 rounded-lg text-[11px] font-black flex items-center gap-1 transition-all shrink-0"
              >
                <span>Feed into AI Planning Engine</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 3. OpenStreetMap Nearby Venues & Facilities (Full Width) */}
      <div className="bg-white border-2 border-black rounded-3xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-2 border-black pb-3">
          <div className="flex items-center gap-2">
            <Building className="w-5 h-5 text-black" />
            <h3 className="text-lg font-black text-black font-heading">
              OpenStreetMap Nearby Places & Venues
            </h3>
          </div>

          {/* Radius Selector */}
          <div role="group" aria-label="Search Radius" className="flex items-center gap-1.5 text-xs font-bold">
            <span className="text-slate-500">Radius:</span>
            {[1000, 3000, 5000, 10000].map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setSelectedRadius(r)}
                aria-pressed={selectedRadius === r}
                aria-label={`Search within ${r >= 1000 ? `${r / 1000} kilometers` : `${r} meters`}`}
                className={`px-2.5 py-1 rounded-lg border text-xs font-black transition-all focus-visible:ring-2 focus-visible:ring-black ${
                  selectedRadius === r
                    ? 'bg-black text-white border-black'
                    : 'bg-white text-slate-700 border-slate-300 hover:border-black'
                }`}
              >
                {r >= 1000 ? `${r / 1000} km` : `${r}m`}
              </button>
            ))}
          </div>
        </div>

        {/* Category Filter Tabs */}
        <div role="tablist" aria-label="Venue Categories" className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs font-bold">
          {[
            { id: 'all', label: 'All Places' },
            { id: 'banquet_hall', label: 'Banquet Halls' },
            { id: 'event_venue', label: 'Event Spaces' },
            { id: 'hotel', label: 'Hotels & Resorts' },
            { id: 'restaurant', label: 'Restaurants' },
            { id: 'park', label: 'Parks & Lawns' },
            { id: 'community_centre', label: 'Community Halls' },
          ].map((cat) => (
            <button
              key={cat.id}
              role="tab"
              type="button"
              aria-selected={selectedCategory === cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-xl border text-xs font-bold whitespace-nowrap transition-all focus-visible:ring-2 focus-visible:ring-black ${
                selectedCategory === cat.id
                  ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1px_1px_0px_0px_#000]'
                  : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-slate-400'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Place listings */}
        {loadingPlaces ? (
          <div className="py-16 text-center text-slate-500 font-bold text-xs flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-black" />
            <span>Scanning OpenStreetMap via Overpass API within {selectedRadius / 1000} km...</span>
          </div>
        ) : placesError ? (
          <div className="p-4 bg-red-50 border-2 border-red-300 rounded-2xl text-xs font-bold text-red-800 space-y-1">
            <div className="flex items-center gap-1.5 font-black text-red-900">
              <AlertTriangle className="w-4 h-4" />
              <span>Places Discovery Notice</span>
            </div>
            <p>{placesError}</p>
          </div>
        ) : placesData ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs font-bold text-slate-600 pb-1">
              <span>
                Found <strong className="text-black">{placesData.total_found}</strong> real physical landmarks
              </span>
              <span className="text-[11px] text-slate-400">
                Source: {placesData.attribution.split(',')[0]}
              </span>
            </div>

            {placesData.places.length === 0 ? (
              <div className="p-8 text-center bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                <p className="text-xs font-bold text-slate-600">
                  No mapped facilities found for category "{selectedCategory}" within {selectedRadius / 1000} km.
                </p>
                <p className="text-[11px] text-slate-400">
                  Try expanding the search radius or choosing "All Places".
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[520px] overflow-y-auto pr-1">
                {placesData.places.map((place) => (
                  <div
                    key={`${place.osm_type}:${place.osm_id}`}
                    className="p-4 bg-slate-50 hover:bg-white border-2 border-black rounded-2xl shadow-[2px_2px_0px_0px_#000] transition-all space-y-2 flex flex-col justify-between"
                  >
                    <div className="space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-black text-black leading-tight line-clamp-1">
                          {place.name}
                        </span>
                        <span className="px-2 py-0.5 bg-[#BAE6FD] border border-black rounded-lg text-[10px] font-black uppercase shrink-0">
                          {place.category.replace('_', ' ')}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-600 font-bold line-clamp-2">
                        {place.address || place.locality || 'Address in OSM tags'}
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-[11px] font-bold">
                      <span className="text-emerald-700 font-black">
                        {place.distance_meters !== undefined
                          ? place.distance_meters >= 1000
                            ? `${(place.distance_meters / 1000).toFixed(2)} km away`
                            : `${place.distance_meters.toFixed(0)} m away`
                          : '--'}
                      </span>

                      <span className="text-slate-400 text-[10px]">
                        OSM ID: {place.osm_type}/{place.osm_id}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Attribution and Disclaimer */}
            <div className="text-[10px] text-slate-400 font-bold pt-2 border-t border-slate-200 space-y-0.5">
              <div>{placesData.attribution}</div>
              <div>{placesData.disclaimer}</div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
