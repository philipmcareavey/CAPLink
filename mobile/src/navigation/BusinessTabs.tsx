import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MessagesStack } from '../navigation/MessagesStack';
import { ContractsStack } from '../navigation/ContractsStack';
import { ProjectsStack } from '../navigation/ProjectsStack';
import { SettingsScreen } from '../screens/shared/SettingsScreen';

const Tab = createBottomTabNavigator();

// Mirrors static/app/js/business.js's BUSINESS_TABS (My Projects,
// Contracts, Messages).
export function BusinessTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Projects" component={ProjectsStack} options={{ headerShown: false }} />
      <Tab.Screen name="Contracts" component={ContractsStack} options={{ headerShown: false }} />
      <Tab.Screen name="Messages" component={MessagesStack} options={{ headerShown: false }} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
