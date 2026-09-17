import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ProjectsListScreen } from '../screens/business/ProjectsListScreen';
import { PostProjectScreen } from '../screens/business/PostProjectScreen';
import { ProjectDetailScreen } from '../screens/business/ProjectDetailScreen';
import { ContractFormScreen } from '../screens/business/ContractFormScreen';
import { ProjectOut } from '../api/types';

export type ProjectsStackParamList = {
  List: undefined;
  PostProject: undefined;
  Detail: { project: ProjectOut };
  ContractForm: { applicationId: string; projectId: string };
};

const Stack = createNativeStackNavigator<ProjectsStackParamList>();

export function ProjectsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="List" component={ProjectsListScreen} options={{ title: 'My Projects' }} />
      <Stack.Screen name="PostProject" component={PostProjectScreen} options={{ title: 'Post a Project', presentation: 'modal' }} />
      <Stack.Screen name="Detail" component={ProjectDetailScreen} options={{ title: 'Project' }} />
      <Stack.Screen name="ContractForm" component={ContractFormScreen} options={{ title: 'Create Contract' }} />
    </Stack.Navigator>
  );
}
