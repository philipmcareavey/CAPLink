import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ContractsListScreen } from '../screens/shared/ContractsListScreen';
import { ContractDetailScreen } from '../screens/shared/ContractDetailScreen';
import { ContractWithCounterpart } from '../api/types';

export type ContractsStackParamList = {
  List: undefined;
  Detail: { contract: ContractWithCounterpart };
};

const Stack = createNativeStackNavigator<ContractsStackParamList>();

export function ContractsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="List" component={ContractsListScreen} options={{ title: 'Contracts' }} />
      <Stack.Screen name="Detail" component={ContractDetailScreen} options={{ title: 'Contract' }} />
    </Stack.Navigator>
  );
}
