import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { StudentProfile } from '../../api/types';
import { Chip } from '../../components/Chip';

// Split out of FeedScreen's embedded profile card (per the design spec —
// a dedicated tab reads better on mobile than one long scrolling Feed
// screen with profile+feed+suggestions stacked).
export function ProfileScreen() {
  const { authedApi } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [skillsInput, setSkillsInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await authedApi<StudentProfile>('/students/me');
      setProfile(data);
      setSkillsInput(data.skills.join(', '));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your profile.');
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

  const save = async () => {
    const skills = skillsInput.split(',').map((s) => s.trim()).filter(Boolean);
    setSaving(true);
    try {
      const updated = await authedApi<StudentProfile>('/students/me', { method: 'PATCH', body: { skills } });
      setProfile(updated);
      setSkillsInput(updated.skills.join(', '));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save your profile.');
    } finally {
      setSaving(false);
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

      {profile ? (
        <View style={styles.card}>
          <Text style={styles.h1}>{profile.degree_title}</Text>
          <Text style={styles.muted}>
            {profile.band.replace(/_/g, ' ')} · ★ {profile.average_rating.toFixed(1)} ({profile.completed_projects_count} completed)
          </Text>
          <View style={styles.chipsRow}>
            {profile.skills.map((skill) => (
              <Chip key={skill} label={skill} />
            ))}
          </View>

          <Text style={styles.label}>Skills (comma separated)</Text>
          <TextInput
            style={styles.input}
            value={skillsInput}
            onChangeText={setSkillsInput}
            testID="profile-skills-input"
          />

          <TouchableOpacity style={styles.saveButton} onPress={save} disabled={saving} testID="profile-save">
            <Text style={styles.saveButtonText}>{saving ? 'Saving…' : 'Save'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  h1: { fontSize: 20, fontWeight: '700', color: '#1B2A45', marginBottom: 4 },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 4 },
  errorText: { color: '#A6452F' },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginTop: 16, marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10 },
  saveButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', marginTop: 14 },
  saveButtonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 13 },
});
