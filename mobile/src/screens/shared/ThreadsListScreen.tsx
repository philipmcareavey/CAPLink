import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ThreadSummaryOut } from '../../api/types';

// Web is one page swapping a thread list and a chat panel via JS — mobile
// is two real screens (this one, pushing ChatScreen). Shared between both
// roles: a business's threads look identical in shape to a student's.
export function ThreadsListScreen({ navigation }: { navigation: { navigate: (screen: string, params: { threadId: string }) => void } }) {
  const { authedApi } = useAuth();
  const [threads, setThreads] = useState<ThreadSummaryOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setThreads(await authedApi<ThreadSummaryOut[]>('/messages/threads'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your messages.');
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

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={threads ?? []}
        keyExtractor={(t) => t.thread_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={<Text style={styles.emptyText}>No conversations yet — start one from an applicant or a contract card.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Chat', { threadId: item.thread_id })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.counterpart_name}</Text>
              <Text style={styles.preview} numberOfLines={1}>{item.last_message_preview ?? 'No messages yet'}</Text>
            </View>
            {item.unread_count > 0 ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{item.unread_count}</Text>
              </View>
            ) : null}
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  emptyText: { color: '#3C4B68', textAlign: 'center', margin: 24, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  name: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  preview: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#A87C2A', borderRadius: 10, minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5, marginLeft: 10 },
  badgeText: { color: '#FFFDF8', fontSize: 11, fontWeight: '700' },
});
