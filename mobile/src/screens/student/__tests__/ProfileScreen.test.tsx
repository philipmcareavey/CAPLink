import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProfileScreen } from '../ProfileScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROFILE = {
  id: 'sp-1', degree_title: 'BSc Data Science', band: 'year_3',
  modules: ['Statistics II'], skills: ['Python', 'SQL'], portfolio_urls: [],
  hourly_rate_expectation_gbp: 20, weekly_hours_available: 10, is_id_verified: true,
  average_rating: 4.8, completed_projects_count: 3, on_time_rate: 1.0,
  data_sharing_consent_at: '2026-01-01T00:00:00Z',
};

function mockAuthedApi(impl: (path: string, opts?: any) => Promise<any>) {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(impl) });
}

test('loads and displays the student profile', async () => {
  mockAuthedApi(async (path) => {
    if (path === '/students/me') return PROFILE;
    throw new Error(`unexpected call: ${path}`);
  });
  await render(<ProfileScreen />);
  await waitFor(() => expect(screen.getByText('BSc Data Science')).toBeTruthy());
  expect(screen.getByText('Python')).toBeTruthy();
  expect(screen.getByText('SQL')).toBeTruthy();
});

test('editing skills sends a PATCH and reflects the update', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/students/me' && (!opts || opts.method === undefined)) return PROFILE;
    if (path === '/students/me' && opts?.method === 'PATCH') {
      return { ...PROFILE, skills: ['Python', 'SQL', 'React'] };
    }
    throw new Error(`unexpected call: ${path} ${JSON.stringify(opts)}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });

  await render(<ProfileScreen />);
  await waitFor(() => expect(screen.getByText('BSc Data Science')).toBeTruthy());

  await fireEvent.changeText(screen.getByTestId('profile-skills-input'), 'Python, SQL, React');
  await fireEvent.press(screen.getByTestId('profile-save'));

  await waitFor(() => expect(screen.getByText('React')).toBeTruthy());
  expect(authedApi).toHaveBeenCalledWith('/students/me', {
    method: 'PATCH',
    body: { skills: ['Python', 'SQL', 'React'] },
  });
});
