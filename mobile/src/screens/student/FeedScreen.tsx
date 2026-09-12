import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ConnectStatus, EmployerSuggestion, ProjectWithMatch, StudentProfile } from '../../api/types';
import { Chip } from '../../components/Chip';
import { MatchBadge } from '../../components/MatchBadge';
import { ApplyModal } from '../../components/ApplyModal';

// Mirrors static/app/js/student.js's renderFeed(): profile card, suggested
// projects (matched, with apply), employer suggestions. Same three real
// backend calls, same Stripe Connect onboarding auto-check.
export function FeedScreen() {
  const { authedApi } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [projects, setProjects] = useState<ProjectWithMatch[] | null>(null);
  const [suggestions, setSuggestions] = useState<EmployerSuggestion[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applyTarget, setApplyTarget] = useState<ProjectWithMatch | null>(null);
  const [applying, setApplying] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [profileData, connectStatus] = await Promise.all([
        authedApi<StudentProfile>('/students/me'),
        authedApi<ConnectStatus>('/payments/connect/status').catch(() => ({ onboarded: true })),
      ]);
      setProfile(profileData);

      if (!connectStatus.onboarded) {
        await authedApi('/payments/connect/onboarding-link', { method: 'POST' }).catch(() => undefined);
      }

      const [feedData, suggestionsData] = await Promise.all([
        authedApi<ProjectWithMatch[]>('/projects/feed?page=1&page_size=20'),
        authedApi<EmployerSuggestion[]>('/recommendations/employer-suggestions').catch(() => []),
      ]);
      setProjects(feedData);
      setSuggestions(suggestionsData);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your feed.');
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

  const submitApplication = async (coverNote: string) => {
    if (!applyTarget) return;
    setApplying(true);
    try {
      const application = await authedApi<{ match_score_at_application: number | null }>('/applications', {
        method: 'POST',
        body: { project_id: applyTarget.id, cover_note: coverNote || undefined },
      });
      const pct = application.match_score_at_application != null ? Math.round(application.match_score_at_application * 100) : null;
      setToast(pct != null ? `Applied! Match score ${pct}%.` : 'Applied!');
    } catch (e) {
      setToast(e instanceof ApiError ? `Application failed: ${e.message}` : 'Application failed.');
    } finally {
      setApplying(false);
      setApplyTarget(null);
      setTimeout(() => setToast(null), 3000);
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
    <View style={styles.container}>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        {error ? (
          <View style={styles.card}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {profile ? (
          <View style={styles.card}>
            <Text style={styles.eyebrow}>Your profile</Text>
            <Text style={styles.h1}>{profile.degree_title}</Text>
            <Text style={styles.muted}>
              {profile.band.replace(/_/g, ' ')} · ★ {profile.average_rating.toFixed(1)} ({profile.completed_projects_count}{' '}
              completed) · on-time {Math.round(profile.on_time_rate * 100)}%
            </Text>
            <View style={styles.chipsRow}>
              {profile.skills.map((skill) => (
                <Chip key={skill} label={skill} />
              ))}
            </View>
            <Text style={styles.muted}>
              Rate expectation: {profile.hourly_rate_expectation_gbp != null ? `£${profile.hourly_rate_expectation_gbp}` : '—'}/hr ·{' '}
              {profile.weekly_hours_available ?? '—'}h/week available
            </Text>
          </View>
        ) : null}

        <View style={styles.card}>
          <Text style={styles.h2}>Suggested projects</Text>
          {projects && projects.length === 0 ? (
            <Text style={styles.muted}>No open projects visible to you right now — check your university/band with an admin.</Text>
          ) : null}
          {(projects ?? []).map((project) => (
            <View key={project.id} style={styles.projectCard}>
              <View style={styles.projectHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.projectTitle}>{project.title}</Text>
                  <Text style={styles.muted}>
                    {project.category.replace(/_/g, ' ')} · £{project.hourly_rate_gbp}/hr · {project.duration_label}
                  </Text>
                </View>
                <MatchBadge score={project.match_score} />
              </View>
              <Text style={styles.description}>{project.description}</Text>
              <View style={styles.chipsRow}>
                {project.match_reasons.map((reason) => (
                  <Chip key={reason} label={reason} tone="reason" />
                ))}
              </View>
              <TouchableOpacity
                style={styles.applyButton}
                onPress={() => setApplyTarget(project)}
                testID={`apply-${project.id}`}
              >
                <Text style={styles.applyButtonText}>Apply</Text>
              </TouchableOpacity>
            </View>
          ))}
        </View>

        <View style={styles.card}>
          <Text style={styles.h2}>Career suggestions</Text>
          {suggestions && suggestions.length === 0 ? (
            <Text style={styles.muted}>No suggestions yet — add more skills to your profile.</Text>
          ) : null}
          {(suggestions ?? []).map((suggestion) => (
            <View key={suggestion.employer_type} style={styles.suggestionRow}>
              <Chip label={suggestion.employer_type} tone="reason" />
              <Text style={styles.mutedInline}>{suggestion.reason}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      <ApplyModal
        visible={!!applyTarget}
        projectTitle={applyTarget?.title ?? ''}
        onCancel={() => setApplyTarget(null)}
        onSubmit={submitApplication}
      />

      {applying ? (
        <View style={[StyleSheet.absoluteFill, styles.overlay]}>
          <ActivityIndicator size="large" color="#FFFDF8" />
        </View>
      ) : null}

      {toast ? (
        <View style={styles.toast}>
          <Text style={styles.toastText}>{toast}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12, marginBottom: 0 },
  eyebrow: { fontSize: 11, textTransform: 'uppercase', color: '#3C4B68', fontWeight: '700', marginBottom: 4 },
  h1: { fontSize: 20, fontWeight: '700', color: '#1B2A45', marginBottom: 4 },
  h2: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 4 },
  mutedInline: { fontSize: 13, color: '#3C4B68' },
  errorText: { color: '#A6452F' },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  projectCard: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 12, marginTop: 12 },
  projectHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  projectTitle: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  description: { fontSize: 13, color: '#1B2A45', marginTop: 8 },
  applyButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 8, alignItems: 'center', marginTop: 12, alignSelf: 'flex-start', paddingHorizontal: 18 },
  applyButtonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 13 },
  suggestionRow: { marginBottom: 12 },
  overlay: { backgroundColor: 'rgba(27,42,69,0.5)', alignItems: 'center', justifyContent: 'center' },
  toast: { position: 'absolute', bottom: 24, left: 24, right: 24, backgroundColor: '#1B2A45', borderRadius: 6, padding: 14, alignItems: 'center' },
  toastText: { color: '#FFFDF8', fontWeight: '600' },
});
