import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ProjectsListScreen } from '../screens/business/ProjectsListScreen';
import { PostProjectScreen } from '../screens/business/PostProjectScreen';
import { ProjectOut } from '../api/types';

export type ProjectsStackParamList = {
  List: undefined;
  PostProject: undefined;
  Detail: { project: ProjectOut };
};

const Stack = createNativeStackNavigator<ProjectsStackParamList>();

export function ProjectsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="List" component={ProjectsListScreen} options={{ title: 'My Projects' }} />
      <Stack.Screen name="PostProject" component={PostProjectScreen} options={{ title: 'Post a Project', presentation: 'modal' }} />
    </Stack.Navigator>
  );
}
