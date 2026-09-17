import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { LocalBusinessResult, LocalSearchMeta } from '../../api/types';

function regionFor(meta: LocalSearchMeta, radiusMiles: number) {
  const delta = Math.max(0.05, (radiusMiles / 69) * 2);
  return {
    latitude: meta.campus_latitude,
    longitude: meta.campus_longitude,
    latitudeDelta: delta,
    longitudeDelta: delta,
  };
}

export function LocalSearchMapScreen() {
  const { authedApi, state } = useAuth();
  const universityId = state.status === 'signedIn' ? state.claims.university_id : null;
  const [meta, setMeta] = useState<LocalSearchMeta | null>(null);
  const [results, setResults] = useState<LocalBusinessResult[]>([]);
  const [radius, setRadius] = useState('10');
  const [minRelevance, setMinRelevance] = useState('0');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The 400 case is the one error with genuinely nothing else to show — no
  // radius makes a campus-less search work — so it keeps the full-screen
  // treatment; every other error renders as a card above usable controls.
  const [campusUnset, setCampusUnset] = useState(false);
  const mapRef = useRef<MapView>(null);

  const search = useCallback(async () => {
    if (!universityId) return;
    setError(null);
    try {
      const [metaData, resultsData] = await Promise.all([
        authedApi<LocalSearchMeta>(`/universities/${universityId}/local-businesses/meta?radius_miles=${radius}`),
        authedApi<LocalBusinessResult[]>(`/universities/${universityId}/local-businesses?radius_miles=${radius}&min_degree_relevance=${minRelevance}`),
      ]);
      setMeta(metaData);
      setResults(resultsData);
      setCampusUnset(false);
      // initialRegion only applies at mount, and this map effectively never
      // remounts — without this, a wider radius fetches markers that render
      // outside the visible viewport and the control looks broken.
      mapRef.current?.animateToRegion(regionFor(metaData, Number(radius)));
    } catch (e) {
      const isCampusUnset = e instanceof ApiError && e.status === 400;
      setCampusUnset(isCampusUnset);
      setError(
        isCampusUnset
          ? "Your university's campus location hasn't been set yet — ask a university admin to add a campus postcode."
          : e instanceof ApiError
            ? e.message
            : 'Search failed.',
      );
    }
  }, [authedApi, universityId, radius, minRelevance]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await search();
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  if (campusUnset) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {meta ? (
        <MapView
          ref={mapRef}
          style={styles.map}
          initialRegion={regionFor(meta, Number(radius))}
        >
          {results.map((r) => (
            <Marker
              key={r.business_id}
              title={r.company_name}
              description={`${r.degree_relevance_label} · ${r.distance_miles} mi · ★ ${r.average_rating.toFixed(1)}`}
              coordinate={{ latitude: r.latitude, longitude: r.longitude }}
            />
          ))}
        </MapView>
      ) : null}

      <View style={styles.controls}>
        <Text style={styles.label}>Radius (mi)</Text>
        <TextInput style={styles.input} value={radius} onChangeText={setRadius} keyboardType="numeric" testID="radius-input" />
        <Text style={styles.label}>Min relevance</Text>
        <TextInput style={styles.input} value={minRelevance} onChangeText={setMinRelevance} keyboardType="numeric" testID="relevance-input" />
        <TouchableOpacity style={styles.searchButton} onPress={search} testID="run-search">
          <Text style={styles.searchButtonText}>Search</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC', padding: 24 },
  errorText: { color: '#A6452F', textAlign: 'center' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  map: { flex: 1 },
  controls: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderTopWidth: 1, borderTopColor: '#DDD6C7', padding: 10, gap: 8 },
  label: { fontSize: 11, color: '#3C4B68' },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 6, width: 50, textAlign: 'center' },
  searchButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 8, paddingHorizontal: 14, marginLeft: 'auto' },
  searchButtonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 12 },
});
