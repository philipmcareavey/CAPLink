import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ApplicantOut, ApplicationStatus, MatchExplanationOut, ProjectOut, StudentShortlistEntry } from '../../api/types';
import { MatchBadge } from '../../components/MatchBadge';
import { MatchExplanationModal } from '../../components/MatchExplanationModal';

const NEXT_STATUS: Partial<Record<ApplicationStatus, ApplicationStatus>> = {
  submitted: 'shortlisted',
  shortlisted: 'interviewing',
  interviewing: 'offered',
};

export function ProjectDetailScreen({
  route,
  navigation,
}: {
  route: { params: { project: ProjectOut } };
  navigation: { navigate: (screen: string, params?: Record<string, unknown>) => void };
}) {
  const { authedApi } = useAuth();
  const { project } = route.params;
  const [view, setView] = useState<'applicants' | 'shortlist'>('applicants');
  const [applicants, setApplicants] = useState<ApplicantOut[] | null>(null);
  const [shortlist, setShortlist] = useState<StudentShortlistEntry[] | null>(null);
  const [explanation, setExplanation] = useState<MatchExplanationOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [applicantsData, shortlistData] = await Promise.all([
        authedApi<ApplicantOut[]>(`/projects/${project.id}/applications`),
        authedApi<StudentShortlistEntry[]>(`/projects/${project.id}/shortlist`),
      ]);
      setApplicants(applicantsData);
      setShortlist(shortlistData);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading this project.');
    }
  }, [authedApi, project.id]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const advance = async (applicant: ApplicantOut) => {
    const next = NEXT_STATUS[applicant.status];
    if (!next) return;
    try {
      const updated = await authedApi<ApplicantOut>(`/applications/${applicant.application_id}`, { method: 'PATCH', body: { status: next } });
      setApplicants((prev) => (prev ?? []).map((a) => (a.application_id === updated.application_id ? updated : a)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not update that application.');
    }
  };

  const messageApplicant = async (studentUserId: string) => {
    try {
      const thread = await authedApi<{ thread_id: string }>('/messages/threads', {
        method: 'POST',
        body: { project_id: project.id, other_user_id: studentUserId },
      });
      navigation.navigate('Messages', { screen: 'Chat', params: { threadId: thread.thread_id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a conversation.');
    }
  };

  const showExplanation = async (studentId: string) => {
    try {
      setExplanation(await authedApi<MatchExplanationOut>(`/projects/${project.id}/shortlist/${studentId}/explanation`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load the match breakdown.');
    }
  };

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

      <View style={styles.toggleRow}>
        <TouchableOpacity style={[styles.toggle, view === 'applicants' && styles.toggleActive]} onPress={() => setView('applicants')}>
          <Text style={[styles.toggleText, view === 'applicants' && styles.toggleTextActive]}>Applicants</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.toggle, view === 'shortlist' && styles.toggleActive]} onPress={() => setView('shortlist')}>
          <Text style={[styles.toggleText, view === 'shortlist' && styles.toggleTextActive]}>Shortlist</Text>
        </TouchableOpacity>
      </View>

      {view === 'applicants' ? (
        <FlatList
          data={applicants ?? []}
          keyExtractor={(a) => a.application_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={<Text style={styles.emptyText}>No applicants yet. Students who apply to this project appear here.</Text>}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.full_name}</Text>
                <Text style={styles.muted}>{item.degree_title} · {item.status}</Text>
                {item.cover_note ? <Text style={styles.coverNote}>{item.cover_note}</Text> : null}
              </View>
              <View style={styles.actionsCol}>
                {NEXT_STATUS[item.status] ? (
                  <TouchableOpacity style={styles.smallButton} onPress={() => advance(item)} testID={`advance-${item.application_id}`}>
                    <Text style={styles.smallButtonText}>Advance</Text>
                  </TouchableOpacity>
                ) : null}
                <TouchableOpacity style={styles.ghostButton} onPress={() => messageApplicant(item.student_user_id)}>
                  <Text style={styles.ghostButtonText}>Message</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.ghostButton}
                  onPress={() => navigation.navigate('ContractForm', { applicationId: item.application_id, projectId: project.id })}
                >
                  <Text style={styles.ghostButtonText}>Create contract</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      ) : (
        <FlatList
          data={shortlist ?? []}
          keyExtractor={(s) => s.student_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={<Text style={styles.emptyText}>No shortlisted candidates yet.</Text>}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.full_name}</Text>
                <Text style={styles.muted}>{item.degree_title} · {item.university_name}</Text>
                <TouchableOpacity onPress={() => showExplanation(item.student_id)}>
                  <Text style={styles.whyLink}>Why this match?</Text>
                </TouchableOpacity>
              </View>
              <MatchBadge score={item.match_score} />
            </View>
          )}
        />
      )}

      <MatchExplanationModal visible={!!explanation} explanation={explanation} onClose={() => setExplanation(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  emptyText: { color: '#3C4B68', textAlign: 'center', margin: 24, fontSize: 13 },
  toggleRow: { flexDirection: 'row', margin: 12, backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7' },
  toggle: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  toggleActive: { backgroundColor: '#1B2A45', borderRadius: 5 },
  toggleText: { color: '#1B2A45', fontWeight: '600', fontSize: 13 },
  toggleTextActive: { color: '#FFFDF8' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  name: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  coverNote: { fontSize: 12, color: '#1B2A45', marginTop: 6, fontStyle: 'italic' },
  actionsCol: { gap: 6, alignItems: 'flex-end' },
  smallButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  smallButtonText: { color: '#FFFDF8', fontSize: 12, fontWeight: '600' },
  ghostButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  ghostButtonText: { color: '#1B2A45', fontSize: 12, fontWeight: '600' },
  whyLink: { color: '#A87C2A', fontSize: 12, fontWeight: '600', marginTop: 6 },
});
