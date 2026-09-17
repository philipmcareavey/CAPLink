import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ThreadsListScreen } from '../screens/shared/ThreadsListScreen';
import { ChatScreen } from '../screens/shared/ChatScreen';

export type MessagesStackParamList = {
  Threads: undefined;
  Chat: { threadId: string };
};

const Stack = createNativeStackNavigator<MessagesStackParamList>();

export function MessagesStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Threads" component={ThreadsListScreen} options={{ title: 'Messages' }} />
      <Stack.Screen name="Chat" component={ChatScreen} options={{ title: 'Conversation' }} />
    </Stack.Navigator>
  );
}
