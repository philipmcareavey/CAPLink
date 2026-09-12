import React, { useState } from 'react';
import { Modal, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

// The web app uses window.prompt() for the cover note — React Native has
// no such thing, so this is a small real modal instead. Same purpose:
// optional free-text cover note before applying.
export function ApplyModal({
  visible,
  projectTitle,
  onCancel,
  onSubmit,
}: {
  visible: boolean;
  projectTitle: string;
  onCancel: () => void;
  onSubmit: (coverNote: string) => void;
}) {
  const [coverNote, setCoverNote] = useState('Happy to get started right away.');

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Apply to "{projectTitle}"</Text>
          <Text style={styles.label}>Cover note (optional)</Text>
          <TextInput
            style={styles.input}
            value={coverNote}
            onChangeText={setCoverNote}
            multiline
            numberOfLines={3}
            testID="apply-cover-note"
          />
          <View style={styles.row}>
            <TouchableOpacity style={styles.ghostButton} onPress={onCancel} testID="apply-cancel">
              <Text style={styles.ghostText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => onSubmit(coverNote)}
              testID="apply-submit"
            >
              <Text style={styles.primaryText}>Apply</Text>
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
  input: {
    borderWidth: 1,
    borderColor: '#DDD6C7',
    borderRadius: 6,
    padding: 10,
    minHeight: 70,
    textAlignVertical: 'top',
    marginBottom: 16,
  },
  row: { flexDirection: 'row', gap: 10 },
  ghostButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, borderWidth: 1, borderColor: '#1B2A45' },
  ghostText: { color: '#1B2A45', fontWeight: '600' },
  primaryButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, backgroundColor: '#1B2A45' },
  primaryText: { color: '#FFFDF8', fontWeight: '600' },
});
