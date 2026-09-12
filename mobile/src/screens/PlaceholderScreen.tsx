import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../context/AuthContext';

// Shell milestone: every real tab exists and is reachable, but the screen
// content itself is a placeholder until its feature area is built for
// real (student feed next). Logout lives here temporarily so the whole
// auth round-trip (login -> tabs -> logout -> login again) is provable
// today, not just login.
export function PlaceholderScreen({ title }: { title: string }) {
  const { logout, state } = useAuth();
  const role = state.status === 'signedIn' ? state.claims.role : null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>Not built yet — coming soon.</Text>
      {role ? <Text style={styles.role}>Signed in as: {role}</Text> : null}
      <TouchableOpacity style={styles.button} onPress={logout} testID="logout-button">
        <Text style={styles.buttonText}>Log out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#F6F3EC' },
  title: { fontSize: 22, fontWeight: '700', color: '#1B2A45', marginBottom: 8 },
  body: { fontSize: 14, color: '#3C4B68', marginBottom: 16 },
  role: { fontSize: 12, color: '#6B7280', marginBottom: 24 },
  button: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, paddingHorizontal: 20 },
  buttonText: { color: '#FFFDF8', fontWeight: '600' },
});
