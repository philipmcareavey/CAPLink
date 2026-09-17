import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { RatingHistoryEntry } from '../../api/types';

function RatingRow({ entry }: { entry: RatingHistoryEntry }) {
  return (
    <View style={styles.row}>
      {/* The server has already made the visibility decision (ratings.py:
          `reveal = given or rating.is_released`) — a rating you GAVE always
          carries its real score, released or not. A null score is the only
          thing that actually means hidden. */}
      {entry.overall_score != null ? (
        <Text style={styles.score}>{entry.overall_score.toFixed(1)}</Text>
      ) : (
        <Text style={styles.hidden}>Hidden until both sides rate</Text>
      )}
    </View>
  );
}

export function RatingsScreen() {
  const { authedApi } = useAuth();
  const [ratings, setRatings] = useState<RatingHistoryEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRatings(await authedApi<RatingHistoryEntry[]>('/ratings/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your ratings.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  const given = (ratings ?? []).filter((r) => r.direction === 'given');
  const received = (ratings ?? []).filter((r) => r.direction === 'received');

  return (
    <ScrollView style={styles.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h2}>Given</Text>
        {given.length === 0 ? <Text style={styles.muted}>You haven't rated anyone yet.</Text> : null}
        {given.map((r) => <RatingRow key={r.id} entry={r} />)}
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Received</Text>
        {received.length === 0 ? <Text style={styles.muted}>No ratings received yet.</Text> : null}
        {received.map((r) => <RatingRow key={r.id} entry={r} />)}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12, marginBottom: 0 },
  h2: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  muted: { fontSize: 13, color: '#3C4B68' },
  errorText: { color: '#A6452F' },
  row: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 10, marginTop: 10 },
  score: { fontSize: 18, fontWeight: '700', color: '#A87C2A' },
  hidden: { fontSize: 13, color: '#3C4B68', fontStyle: 'italic' },
});
