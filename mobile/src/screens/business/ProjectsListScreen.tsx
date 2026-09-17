import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ProjectOut } from '../../api/types';

export function ProjectsListScreen({ navigation }: { navigation: { navigate: (screen: string, params?: { project: ProjectOut }) => void } }) {
  const { authedApi } = useAuth();
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProjects(await authedApi<ProjectOut[]>('/projects/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your projects.');
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
      <TouchableOpacity style={styles.postButton} onPress={() => navigation.navigate('PostProject')} testID="post-project-button">
        <Text style={styles.postButtonText}>+ Post a project</Text>
      </TouchableOpacity>
      <FlatList
        data={projects ?? []}
        keyExtractor={(p) => p.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={<Text style={styles.emptyText}>No projects yet — post your first one above.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Detail', { project: item })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{item.title}</Text>
              <Text style={styles.muted}>{item.category.replace(/_/g, ' ')} · £{item.hourly_rate_gbp}/hr</Text>
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{item.status}</Text>
            </View>
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
  postButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', margin: 12 },
  postButtonText: { color: '#FFFDF8', fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  title: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#E9D9B8', borderRadius: 100, paddingVertical: 4, paddingHorizontal: 10, marginLeft: 10 },
  badgeText: { fontSize: 11, fontWeight: '700', color: '#A87C2A' },
});
