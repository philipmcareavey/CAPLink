import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';

const Tab = createBottomTabNavigator();

// Mirrors static/app/js/business.js's BUSINESS_TABS (My Projects,
// Contracts, Messages).
export function BusinessTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Projects" children={() => <PlaceholderScreen title="My Projects" />} />
      <Tab.Screen name="Contracts" children={() => <PlaceholderScreen title="Contracts" />} />
      <Tab.Screen name="Messages" children={() => <PlaceholderScreen title="Messages" />} />
    </Tab.Navigator>
  );
}
