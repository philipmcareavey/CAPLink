import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';

type MilestoneRow = { description: string; payment_amount_gbp: string };

export function ContractFormScreen({
  route,
  navigation,
}: {
  route: { params: { applicationId: string; projectId: string } };
  navigation: { goBack: () => void };
}) {
  const { authedApi } = useAuth();
  const { applicationId } = route.params;
  const [rows, setRows] = useState<MilestoneRow[]>([{ description: '', payment_amount_gbp: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateRow = (index: number, field: keyof MilestoneRow, value: string) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };

  const addRow = () => setRows((prev) => [...prev, { description: '', payment_amount_gbp: '' }]);
  const removeRow = (index: number) => setRows((prev) => prev.filter((_, i) => i !== index));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await authedApi('/contracts', {
        method: 'POST',
        body: {
          application_id: applicationId,
          milestones: rows.map((r) => ({ description: r.description, payment_amount_gbp: Number(r.payment_amount_gbp) })),
        },
      });
      navigation.goBack();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create that contract.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h2}>Milestones</Text>
        {rows.map((row, index) => (
          <View key={index} style={styles.milestoneBlock}>
            <Text style={styles.label}>Description</Text>
            <TextInput
              style={styles.input}
              value={row.description}
              onChangeText={(v) => updateRow(index, 'description', v)}
              testID={`milestone-description-${index}`}
            />
            <Text style={styles.label}>Amount (£)</Text>
            <TextInput
              style={styles.input}
              value={row.payment_amount_gbp}
              onChangeText={(v) => updateRow(index, 'payment_amount_gbp', v)}
              keyboardType="numeric"
              testID={`milestone-amount-${index}`}
            />
            {rows.length > 1 ? (
              <TouchableOpacity onPress={() => removeRow(index)} testID={`remove-milestone-${index}`}>
                <Text style={styles.removeText}>Remove</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ))}

        <TouchableOpacity style={styles.addButton} onPress={addRow} testID="add-milestone">
          <Text style={styles.addButtonText}>+ Add milestone</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.submitButton} onPress={submit} disabled={submitting} testID="create-contract">
          <Text style={styles.submitButtonText}>{submitting ? 'Creating…' : 'Create contract'}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  h2: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  milestoneBlock: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 12, marginTop: 12 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 10 },
  removeText: { color: '#A6452F', fontSize: 12, fontWeight: '600' },
  addButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', marginTop: 12 },
  addButtonText: { color: '#1B2A45', fontWeight: '600', fontSize: 13 },
  submitButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 16 },
  submitButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
