import React from 'react';
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { MatchExplanationOut } from '../api/types';

export function MatchExplanationModal({
  visible,
  explanation,
  onClose,
}: {
  visible: boolean;
  explanation: MatchExplanationOut | null;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Why this match?</Text>
          {explanation ? (
            <ScrollView>
              <Text style={styles.overall}>{Math.round(explanation.score * 100)}% overall</Text>
              {explanation.breakdown.map((factor) => (
                <View key={factor.name} style={styles.factorRow}>
                  <Text style={styles.factorName}>{factor.name.replace(/_/g, ' ')}</Text>
                  <Text style={styles.factorDetail}>{factor.detail}</Text>
                </View>
              ))}
            </ScrollView>
          ) : null}
          <TouchableOpacity style={styles.closeButton} onPress={onClose} testID="close-explanation">
            <Text style={styles.closeButtonText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(27,42,69,0.4)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFFDF8', borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 20, maxHeight: '70%' },
  title: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  overall: { fontSize: 20, fontWeight: '700', color: '#A87C2A', marginBottom: 14 },
  factorRow: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingVertical: 10 },
  factorName: { fontSize: 13, fontWeight: '700', color: '#1B2A45', textTransform: 'capitalize' },
  factorDetail: { fontSize: 12, color: '#3C4B68', marginTop: 2 },
  closeButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 16 },
  closeButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
