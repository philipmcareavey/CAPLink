import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

// A simpler stand-in for the web app's SVG match dial — same information
// (a 0-1 match score as a percentage), no react-native-svg dependency
// pulled in just for this. Can be upgraded to a real ring later without
// changing any caller.
export function MatchBadge({ score }: { score: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  return (
    <View style={styles.badge}>
      <Text style={styles.text}>{pct}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#E9D9B8',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { fontSize: 13, fontWeight: '700', color: '#A87C2A' },
});
