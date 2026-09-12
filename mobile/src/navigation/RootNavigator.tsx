import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { useAuth } from '../context/AuthContext';
import { LoginScreen } from '../screens/LoginScreen';
import { StudentTabs } from './StudentTabs';
import { BusinessTabs } from './BusinessTabs';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';

export function RootNavigator() {
  const { state } = useAuth();

  if (state.status === 'loading') {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' }}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {state.status === 'signedOut' && <LoginScreen />}
      {state.status === 'signedIn' && state.claims.role === 'student' && <StudentTabs />}
      {state.status === 'signedIn' && state.claims.role === 'business' && <BusinessTabs />}
      {state.status === 'signedIn' &&
        state.claims.role !== 'student' &&
        state.claims.role !== 'business' && (
          // University admin / platform admin: genuinely out of scope for
          // this mobile app (an office workflow, not a mobile one — see
          // the roadmap decision in caplink/CLAUDE.md) — a clear message
          // instead of a confusing blank screen or a crash.
          <PlaceholderScreen title="This role isn't supported in the mobile app yet" />
        )}
    </NavigationContainer>
  );
}
