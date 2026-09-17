import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ContractWithCounterpart } from '../../api/types';

export function ContractsListScreen({ navigation }: { navigation: { navigate: (screen: string, params: { contract: ContractWithCounterpart }) => void } }) {
  const { authedApi, state } = useAuth();
  const role = state.status === 'signedIn' ? state.claims.role : null;
  const [contracts, setContracts] = useState<ContractWithCounterpart[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setContracts(await authedApi<ContractWithCounterpart[]>('/contracts/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your contracts.');
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
        data={contracts ?? []}
        keyExtractor={(c) => c.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <Text style={styles.emptyText}>
            No contracts yet.{role === 'business' ? ' Create one from an applicant on one of your projects.' : ' These appear once a business hires you.'}
          </Text>
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Detail', { contract: item })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{item.project_title}</Text>
              <Text style={styles.muted}>With {item.counterpart_name}</Text>
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
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  title: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#E9D9B8', borderRadius: 100, paddingVertical: 4, paddingHorizontal: 10, marginLeft: 10 },
  badgeText: { fontSize: 11, fontWeight: '700', color: '#A87C2A' },
});
