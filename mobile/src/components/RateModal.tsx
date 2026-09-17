import React, { useState } from 'react';
import { Modal, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

export function RateModal({
  visible,
  counterpartName,
  onCancel,
  onSubmit,
}: {
  visible: boolean;
  counterpartName: string;
  onCancel: () => void;
  onSubmit: (overallScore: number) => void;
}) {
  const [score, setScore] = useState('5');

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Rate {counterpartName}</Text>
          <Text style={styles.label}>Overall score (1-5)</Text>
          <TextInput
            style={styles.input}
            value={score}
            onChangeText={setScore}
            keyboardType="numeric"
            testID="rate-score-input"
          />
          <View style={styles.row}>
            <TouchableOpacity style={styles.ghostButton} onPress={onCancel} testID="rate-cancel">
              <Text style={styles.ghostText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => onSubmit(Number(score))}
              testID="rate-submit"
            >
              <Text style={styles.primaryText}>Submit rating</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(27,42,69,0.4)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFFDF8', borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 20 },
  title: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 14 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 16 },
  row: { flexDirection: 'row', gap: 10 },
  ghostButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, borderWidth: 1, borderColor: '#1B2A45' },
  ghostText: { color: '#1B2A45', fontWeight: '600' },
  primaryButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, backgroundColor: '#1B2A45' },
  primaryText: { color: '#FFFDF8', fontWeight: '600' },
});
