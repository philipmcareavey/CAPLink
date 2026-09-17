import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProjectDetailScreen } from '../ProjectDetailScreen';
import { useAuth } from '../../../context/AuthContext';
import { ApiError } from '../../../api/client';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROJECT = {
  id: 'p-1', business_id: 'b-1', title: 'Build a customer analytics dashboard',
  description: 'A dashboard.', category: 'data_analytics', required_skills: ['Python'],
  duration_label: '2-3 weeks', estimated_hours: 20, hourly_rate_gbp: 22,
  is_remote: true, location_label: null, status: 'open',
};

const APPLICANT = {
  application_id: 'app-1', student_id: 's-1', student_user_id: 'u-1', full_name: 'Priya Anand',
  degree_title: 'BSc Data Science', status: 'submitted', cover_note: 'Happy to help.',
  proposed_rate_gbp: 22, match_score_at_application: 0.86,
};

const SHORTLIST_ENTRY = {
  student_id: 's-1', full_name: 'Priya Anand', degree_title: 'BSc Data Science',
  university_name: 'University of Manchester', average_rating: 4.8, completed_projects_count: 3,
  match_score: 0.86, match_reasons: ['Matched skills: python, sql'],
};

function routeWith(project: typeof PROJECT) {
  return { params: { project } } as any;
}

test('shows applicants by default, toggles to shortlist, and can advance an application status', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/projects/p-1/applications') return [APPLICANT];
    if (path === '/projects/p-1/shortlist') return [SHORTLIST_ENTRY];
    if (path === '/applications/app-1' && opts?.method === 'PATCH') return { ...APPLICANT, status: opts.body.status };
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });

  await render(<ProjectDetailScreen route={routeWith(PROJECT)} navigation={{ navigate: jest.fn() } as any} />);
  await waitFor(() => expect(screen.getByText('Priya Anand')).toBeTruthy());
  expect(screen.getByText('Happy to help.')).toBeTruthy();

  await fireEvent.press(screen.getByText('Shortlist'));
  await waitFor(() => expect(screen.getByText('University of Manchester', { exact: false })).toBeTruthy());

  await fireEvent.press(screen.getByText('Applicants'));
  await waitFor(() => screen.getByTestId('advance-app-1'));
  await fireEvent.press(screen.getByTestId('advance-app-1'));
  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/applications/app-1', { method: 'PATCH', body: { status: 'shortlisted' } }));
});

test('shows empty states on both lists when the project has no applicants or shortlist', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => []) });
  await render(<ProjectDetailScreen route={routeWith(PROJECT)} navigation={{ navigate: jest.fn() } as any} />);
  await waitFor(() => expect(screen.getByText('No applicants yet.', { exact: false })).toBeTruthy());
  await fireEvent.press(screen.getByText('Shortlist'));
  await waitFor(() => expect(screen.getByText('No shortlisted candidates yet.')).toBeTruthy());
});

// Representative error-path test for the DETAIL screen family.
test('renders the error card when the load fails', async () => {
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async () => {
      throw new ApiError('You do not have access to this project.', 403);
    }),
  });
  await render(<ProjectDetailScreen route={routeWith(PROJECT)} navigation={{ navigate: jest.fn() } as any} />);
  await waitFor(() => expect(screen.getByText('You do not have access to this project.')).toBeTruthy());
  // The toggle is still there — the error doesn't replace the whole screen.
  expect(screen.getByText('Applicants')).toBeTruthy();
});
