import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { FeedScreen } from '../screens/student/FeedScreen';
import { ProfileScreen } from '../screens/student/ProfileScreen';
import { MessagesStack } from '../navigation/MessagesStack';
import { ContractsStack } from '../navigation/ContractsStack';
import { RatingsScreen } from '../screens/student/RatingsScreen';
import { LocalSearchMapScreen } from '../screens/student/LocalSearchMapScreen';
import { SettingsScreen } from '../screens/shared/SettingsScreen';

const Tab = createBottomTabNavigator();

// Mirrors static/app/js/student.js's STUDENT_TABS (Feed, Contracts,
// Messages, Local Search, My Ratings) — same tab set, same order, just a
// native shell around it instead of a web one.
export function StudentTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Feed" component={FeedScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
      <Tab.Screen name="Contracts" component={ContractsStack} options={{ headerShown: false }} />
      <Tab.Screen name="Messages" component={MessagesStack} options={{ headerShown: false }} />
      <Tab.Screen name="Local" component={LocalSearchMapScreen} />
      <Tab.Screen name="Ratings" component={RatingsScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
