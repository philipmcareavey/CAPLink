import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import { FeedScreen } from '../screens/student/FeedScreen';
import { ProfileScreen } from '../screens/student/ProfileScreen';
import { MessagesStack } from '../navigation/MessagesStack';

const Tab = createBottomTabNavigator();

// Mirrors static/app/js/student.js's STUDENT_TABS (Feed, Contracts,
// Messages, Local Search, My Ratings) — same tab set, same order, just a
// native shell around it instead of a web one.
export function StudentTabs() {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Feed" component={FeedScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
      <Tab.Screen name="Contracts" children={() => <PlaceholderScreen title="Contracts" />} />
      <Tab.Screen name="Messages" component={MessagesStack} options={{ headerShown: false }} />
      <Tab.Screen name="Local" children={() => <PlaceholderScreen title="Local Search" />} />
      <Tab.Screen name="Ratings" children={() => <PlaceholderScreen title="My Ratings" />} />
    </Tab.Navigator>
  );
}
