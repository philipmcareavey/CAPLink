import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';

export function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>CAPLink</Text>
      <Text style={styles.subtitle}>Sign in</Text>

      <TextInput
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        testID="login-email"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        testID="login-password"
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity style={styles.button} onPress={onSubmit} disabled={submitting} testID="login-submit">
        {submitting ? <ActivityIndicator color="#FFFDF8" /> : <Text style={styles.buttonText}>Log in</Text>}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#F6F3EC' },
  title: { fontSize: 32, fontWeight: '700', color: '#1B2A45', textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#3C4B68', textAlign: 'center', marginBottom: 28 },
  input: {
    backgroundColor: '#FFFDF8',
    borderWidth: 1,
    borderColor: '#DDD6C7',
    borderRadius: 6,
    padding: 12,
    marginBottom: 12,
    fontSize: 15,
  },
  button: { backgroundColor: '#1B2A45', borderRadius: 6, padding: 14, alignItems: 'center', marginTop: 8 },
  buttonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 15 },
  error: { color: '#A6452F', marginBottom: 8, textAlign: 'center' },
});
