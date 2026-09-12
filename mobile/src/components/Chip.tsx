import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

export function Chip({ label, tone = 'default' }: { label: string; tone?: 'default' | 'reason' }) {
  return (
    <View style={[styles.chip, tone === 'reason' && styles.reasonChip]}>
      <Text style={[styles.text, tone === 'reason' && styles.reasonText]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    backgroundColor: '#F6F3EC',
    borderWidth: 1,
    borderColor: '#DDD6C7',
    borderRadius: 100,
    paddingVertical: 5,
    paddingHorizontal: 11,
    marginRight: 6,
    marginBottom: 6,
  },
  text: { fontSize: 12, color: '#3C4B68' },
  reasonChip: { backgroundColor: '#DCE6DD', borderColor: '#DCE6DD' },
  reasonText: { color: '#4C6B54', fontWeight: '600' },
});
