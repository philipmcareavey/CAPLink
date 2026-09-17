import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ContractWithCounterpart, MilestoneOut } from '../../api/types';
import { RateModal } from '../../components/RateModal';

export function ContractDetailScreen({
  route,
  navigation,
}: {
  route: { params: { contract: ContractWithCounterpart } };
  navigation: { navigate: (screen: string, params?: Record<string, unknown>) => void };
}) {
  const { authedApi, state } = useAuth();
  const role = state.status === 'signedIn' ? state.claims.role : null;
  const [contract, setContract] = useState(route.params.contract);
  const [busyMilestoneId, setBusyMilestoneId] = useState<string | null>(null);
  const [rateModalOpen, setRateModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateMilestone = (updated: MilestoneOut) => {
    setContract((prev) => ({ ...prev, milestones: prev.milestones.map((m) => (m.id === updated.id ? updated : m)) }));
  };

  const submitMilestone = async (milestoneId: string) => {
    setBusyMilestoneId(milestoneId);
    try {
      updateMilestone(await authedApi<MilestoneOut>(`/contracts/milestones/${milestoneId}/submit`, { method: 'POST' }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit that milestone.');
    } finally {
      setBusyMilestoneId(null);
    }
  };

  const approveAndPay = async (milestoneId: string) => {
    setBusyMilestoneId(milestoneId);
    try {
      updateMilestone(await authedApi<MilestoneOut>(`/contracts/milestones/${milestoneId}/approve-and-pay`, { method: 'POST' }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not approve that milestone.');
    } finally {
      setBusyMilestoneId(null);
    }
  };

  const acceptTerms = async () => {
    try {
      const updated = await authedApi<ContractWithCounterpart>(`/contracts/${contract.id}/accept-terms`, { method: 'POST' });
      setContract(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not accept terms.');
    }
  };

  const startMessage = async () => {
    try {
      const thread = await authedApi<{ thread_id: string }>('/messages/threads', {
        method: 'POST',
        body: { project_id: contract.project_id, other_user_id: contract.counterpart_user_id },
      });
      navigation.navigate('Messages', { screen: 'Chat', params: { threadId: thread.thread_id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a conversation.');
    }
  };

  const submitRating = async (overallScore: number) => {
    try {
      await authedApi('/ratings', { method: 'POST', body: { contract_id: contract.id, overall_score: overallScore, sub_scores: {} } });
      setRateModalOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit that rating.');
      setRateModalOpen(false);
    }
  };

  const termsNeeded = !contract.ip_assignment_accepted || !contract.nda_accepted;

  return (
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h1}>{contract.project_title}</Text>
        <Text style={styles.muted}>With {contract.counterpart_name} · {contract.status}</Text>

        {contract.milestones.map((m) => (
          <View key={m.id} style={styles.milestoneRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.milestoneDesc}>{m.description}</Text>
              <Text style={styles.muted}>£{m.payment_amount_gbp} · {m.status}</Text>
            </View>
            {role === 'student' && m.status === 'pending' ? (
              <TouchableOpacity
                style={styles.smallButton}
                onPress={() => submitMilestone(m.id)}
                disabled={busyMilestoneId === m.id}
                testID={`submit-${m.id}`}
              >
                <Text style={styles.smallButtonText}>Submit</Text>
              </TouchableOpacity>
            ) : null}
            {role === 'business' && m.status === 'submitted' ? (
              <TouchableOpacity
                style={styles.smallButton}
                onPress={() => approveAndPay(m.id)}
                disabled={busyMilestoneId === m.id}
                testID={`approve-pay-${m.id}`}
              >
                <Text style={styles.smallButtonText}>Approve & pay</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ))}

        <View style={styles.actionsRow}>
          {termsNeeded ? (
            <TouchableOpacity style={styles.ghostButton} onPress={acceptTerms} testID="accept-terms">
              <Text style={styles.ghostButtonText}>Accept IP/NDA terms</Text>
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity style={styles.ghostButton} onPress={startMessage} testID="message-counterpart">
            <Text style={styles.ghostButtonText}>Message {contract.counterpart_name}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.ghostButton} onPress={() => setRateModalOpen(true)} testID="rate-contract">
            <Text style={styles.ghostButtonText}>Rate this contract</Text>
          </TouchableOpacity>
        </View>
      </View>

      <RateModal
        visible={rateModalOpen}
        counterpartName={contract.counterpart_name}
        onCancel={() => setRateModalOpen(false)}
        onSubmit={submitRating}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  h1: { fontSize: 18, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 4 },
  errorText: { color: '#A6452F' },
  milestoneRow: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 12, marginTop: 12 },
  milestoneDesc: { fontSize: 14, color: '#1B2A45', fontWeight: '600' },
  smallButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  smallButtonText: { color: '#FFFDF8', fontSize: 12, fontWeight: '600' },
  actionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 16 },
  ghostButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 8, paddingHorizontal: 12 },
  ghostButtonText: { color: '#1B2A45', fontSize: 12, fontWeight: '600' },
});
