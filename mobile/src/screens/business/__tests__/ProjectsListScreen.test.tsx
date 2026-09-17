import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProjectsListScreen } from '../ProjectsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROJECT = {
  id: 'p-1', business_id: 'b-1', title: 'Build a customer analytics dashboard',
  description: 'A dashboard.', category: 'data_analytics', required_skills: ['Python'],
  duration_label: '2-3 weeks', estimated_hours: 20, hourly_rate_gbp: 22,
  is_remote: true, location_label: null, status: 'open',
};

test('lists the business\'s own projects and navigates to Detail on tap', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => [PROJECT]) });
  const navigate = jest.fn();
  await render(<ProjectsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Build a customer analytics dashboard')).toBeTruthy());
  await fireEvent.press(screen.getByText('Build a customer analytics dashboard'));
  expect(navigate).toHaveBeenCalledWith('Detail', { project: PROJECT });
});

test('the "post a project" button navigates to PostProject', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => []) });
  const navigate = jest.fn();
  await render(<ProjectsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => screen.getByTestId('post-project-button'));
  await fireEvent.press(screen.getByTestId('post-project-button'));
  expect(navigate).toHaveBeenCalledWith('PostProject');
});
