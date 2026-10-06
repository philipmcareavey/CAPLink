import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { NotificationPreferenceItem, NotificationPreferencesOut } from '../../api/types';

export function SettingsScreen() {
  const { authedApi, logout } = useAuth();
  const [preferences, setPreferences] = useState<NotificationPreferenceItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState('');

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await authedApi<NotificationPreferencesOut>('/mobile/notification-preferences');
      setPreferences(data.preferences);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your notification preferences.');
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

  const toggle = async (templateKey: string) => {
    if (!preferences) return;
    const optedOut = preferences
      .map((p) => (p.template_key === templateKey ? { ...p, enabled: !p.enabled } : p))
      .filter((p) => !p.enabled)
      .map((p) => p.template_key);
    try {
      const data = await authedApi<NotificationPreferencesOut>('/mobile/notification-preferences', {
        method: 'PATCH',
        body: { opted_out: optedOut },
      });
      setPreferences(data.preferences);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not update that preference.');
    }
  };

  // App Store guideline 5.1.1(v) / Google Play's account-deletion policy:
  // users must be able to delete their account from inside the app. Same
  // DELETE /privacy/account endpoint (and password reauth) as the web app.
  const deleteAccount = async () => {
    setError(null);
    try {
      await authedApi('/privacy/account', { method: 'DELETE', body: { current_password: password } });
      await logout();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not delete your account.');
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>Notifications</Text>
      <View style={styles.card}>
        {(preferences ?? []).map((item) => (
          <View key={item.template_key} style={styles.row}>
            <Text style={styles.rowLabel}>{item.label}</Text>
            <Switch
              value={item.enabled}
              onValueChange={() => toggle(item.template_key)}
              testID={`toggle-${item.template_key}`}
            />
          </View>
        ))}
      </View>

      <Text style={styles.sectionTitle}>Account</Text>
      <View style={styles.card}>
        <TouchableOpacity style={styles.logoutButton} onPress={logout} testID="logout-button">
          <Text style={styles.logoutButtonText}>Log out</Text>
        </TouchableOpacity>
        {deleting ? (
          <View style={styles.deleteBox}>
            <Text style={styles.rowLabel}>
              This permanently deletes your account and anonymises your personal data. Enter your password to confirm.
            </Text>
            <TextInput
              style={styles.input}
              secureTextEntry
              placeholder="Current password"
              value={password}
              onChangeText={setPassword}
              testID="delete-password"
            />
            <TouchableOpacity
              style={styles.logoutButton}
              onPress={deleteAccount}
              disabled={!password}
              testID="delete-confirm"
            >
              <Text style={styles.logoutButtonText}>Permanently delete account</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity style={styles.logoutButton} onPress={() => setDeleting(true)} testID="delete-account-button">
            <Text style={styles.logoutButtonText}>Delete account</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', margin: 12, marginTop: 0 },
  errorText: { color: '#A6452F', padding: 16 },
  sectionTitle: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginTop: 20, marginLeft: 16, marginBottom: 6 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#DDD6C7',
  },
  rowLabel: { fontSize: 14, color: '#1B2A45', flex: 1, marginRight: 12 },
  logoutButton: { padding: 16, alignItems: 'center' },
  logoutButtonText: { color: '#A6452F', fontWeight: '700', fontSize: 15 },
  deleteBox: { padding: 16, borderTopWidth: 1, borderTopColor: '#DDD6C7' },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginTop: 12, color: '#1B2A45' },
});
