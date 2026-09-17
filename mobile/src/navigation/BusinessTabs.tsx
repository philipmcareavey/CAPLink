import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import { MessagesStack } from '../navigation/MessagesStack';
import { ContractsStack } from '../navigation/ContractsStack';

const Tab = createBottomTabNavigator();

// Mirrors static/app/js/business.js's BUSINESS_TABS (My Projects,
// Contracts, Messages).
export function BusinessTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Projects" children={() => <PlaceholderScreen title="My Projects" />} />
      <Tab.Screen name="Contracts" component={ContractsStack} options={{ headerShown: false }} />
      <Tab.Screen name="Messages" component={MessagesStack} options={{ headerShown: false }} />
    </Tab.Navigator>
  );
}
