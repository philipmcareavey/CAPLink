import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { AgreementWithUniversityOut } from '../../api/types';

export function PostProjectScreen({ navigation }: { navigation: { goBack: () => void } }) {
  const { authedApi } = useAuth();
  const [agreements, setAgreements] = useState<AgreementWithUniversityOut[] | null>(null);
  const [selectedAgreement, setSelectedAgreement] = useState<AgreementWithUniversityOut | null>(null);
  const [selectedBands, setSelectedBands] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [requiredSkills, setRequiredSkills] = useState('');
  const [durationLabel, setDurationLabel] = useState('1-2 weeks');
  const [rate, setRate] = useState('20');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await authedApi<AgreementWithUniversityOut[]>('/businesses/me/agreements');
      setAgreements(data.filter((a) => a.status === 'approved'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your approved universities.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const toggleBand = (band: string) => {
    setSelectedBands((prev) => (prev.includes(band) ? prev.filter((b) => b !== band) : [...prev, band]));
  };

  const submit = async () => {
    if (!selectedAgreement) {
      setError('Choose a target university first.');
      return;
    }
    if (!selectedCategory) {
      setError('Choose a project category first.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await authedApi('/projects', {
        method: 'POST',
        body: {
          title,
          description,
          category: selectedCategory,
          required_skills: requiredSkills.split(',').map((s) => s.trim()).filter(Boolean),
          duration_label: durationLabel,
          hourly_rate_gbp: Number(rate),
          target_university_ids: [selectedAgreement.university_id],
          target_bands: selectedBands,
        },
      });
      navigation.goBack();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not post that project.');
    } finally {
      setSubmitting(false);
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
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.label}>Title</Text>
        <TextInput style={styles.input} value={title} onChangeText={setTitle} testID="post-title" />

        <Text style={styles.label}>Description</Text>
        <TextInput style={[styles.input, styles.multiline]} value={description} onChangeText={setDescription} multiline testID="post-description" />

        <Text style={styles.label}>Required skills (comma separated)</Text>
        <TextInput style={styles.input} value={requiredSkills} onChangeText={setRequiredSkills} testID="post-skills" />

        <Text style={styles.label}>Duration</Text>
        <TextInput style={styles.input} value={durationLabel} onChangeText={setDurationLabel} testID="post-duration" />

        <Text style={styles.label}>Hourly rate (£)</Text>
        <TextInput style={styles.input} value={rate} onChangeText={setRate} keyboardType="numeric" testID="post-rate" />

        <Text style={styles.label}>Target university</Text>
        {(agreements ?? []).length === 0 ? (
          <Text style={styles.muted}>No approved university partnerships yet.</Text>
        ) : (
          (agreements ?? []).map((a) => (
            <TouchableOpacity
              key={a.id}
              style={[styles.optionRow, selectedAgreement?.id === a.id && styles.optionRowSelected]}
              onPress={() => {
                setSelectedAgreement(a);
                setSelectedBands([]);
                // Default-select when there's only one choice; otherwise make
                // the business pick, rather than silently posting the first.
                setSelectedCategory(a.allowed_categories.length === 1 ? a.allowed_categories[0] : null);
              }}
            >
              <Text style={styles.optionText}>{a.university_name}</Text>
            </TouchableOpacity>
          ))
        )}

        {selectedAgreement ? (
          <>
            <Text style={styles.label}>Category</Text>
            {selectedAgreement.allowed_categories.map((category) => (
              <TouchableOpacity
                key={category}
                style={[styles.optionRow, selectedCategory === category && styles.optionRowSelected]}
                onPress={() => setSelectedCategory(category)}
                testID={`category-${category}`}
              >
                <Text style={styles.optionText}>{category}</Text>
              </TouchableOpacity>
            ))}

            <Text style={styles.label}>Target bands</Text>
            {selectedAgreement.allowed_bands.map((band) => (
              <TouchableOpacity
                key={band}
                style={[styles.optionRow, selectedBands.includes(band) && styles.optionRowSelected]}
                onPress={() => toggleBand(band)}
              >
                <Text style={styles.optionText}>{band}</Text>
              </TouchableOpacity>
            ))}
          </>
        ) : null}

        <TouchableOpacity style={styles.submitButton} onPress={submit} disabled={submitting} testID="post-submit">
          <Text style={styles.submitButtonText}>{submitting ? 'Posting…' : 'Post project'}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  muted: { fontSize: 13, color: '#3C4B68' },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginTop: 14, marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10 },
  multiline: { minHeight: 70, textAlignVertical: 'top' },
  optionRow: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 6 },
  optionRowSelected: { borderColor: '#1B2A45', backgroundColor: '#E9D9B8' },
  optionText: { fontSize: 13, color: '#1B2A45' },
  submitButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 20 },
  submitButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
