import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { SettingsScreen } from '../SettingsScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PREFERENCES = [
  { template_key: 'new_match', label: 'New project match', enabled: true },
  { template_key: 'new_message', label: 'New message', enabled: false },
  { template_key: 'milestone_paid', label: 'Payment released', enabled: true },
];

test('lists preferences with correct labels and toggle states', async () => {
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async () => ({ preferences: PREFERENCES })),
    logout: jest.fn(),
  });
  await render(<SettingsScreen />);
  await waitFor(() => expect(screen.getByText('New project match')).toBeTruthy());
  expect(screen.getByText('New message')).toBeTruthy();
  expect(screen.getByText('Payment released')).toBeTruthy();
  expect(screen.getByTestId('toggle-new_match').props.value).toBe(true);
  expect(screen.getByTestId('toggle-new_message').props.value).toBe(false);
  expect(screen.getByTestId('toggle-milestone_paid').props.value).toBe(true);
});

test('toggling a preference off calls authedApi with the correctly computed opted_out array', async () => {
  const authedApi = jest.fn(async (path: string, opts?: { method?: string; body?: unknown }) => {
    if (opts?.method === 'PATCH') {
      return { preferences: PREFERENCES.map((p) => (p.template_key === 'new_match' ? { ...p, enabled: false } : p)) };
    }
    return { preferences: PREFERENCES };
  });
  mockedUseAuth.mockReturnValue({ authedApi, logout: jest.fn() });
  await render(<SettingsScreen />);
  await waitFor(() => expect(screen.getByText('New project match')).toBeTruthy());

  await fireEvent(screen.getByTestId('toggle-new_match'), 'valueChange', false);

  await waitFor(() =>
    expect(authedApi).toHaveBeenCalledWith('/mobile/notification-preferences', {
      method: 'PATCH',
      body: { opted_out: ['new_match', 'new_message'] },
    }),
  );
});

test('pressing the logout button calls logout from useAuth', async () => {
  const logout = jest.fn();
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async () => ({ preferences: PREFERENCES })),
    logout,
  });
  await render(<SettingsScreen />);
  await waitFor(() => expect(screen.getByTestId('logout-button')).toBeTruthy());
  await fireEvent.press(screen.getByTestId('logout-button'));
  expect(logout).toHaveBeenCalledTimes(1);
});

test('deleting the account sends the password to DELETE /privacy/account, then logs out', async () => {
  const authedApi = jest.fn(async (path: string) => (path === '/privacy/account' ? { message: 'ok' } : { preferences: PREFERENCES }));
  const logout = jest.fn();
  mockedUseAuth.mockReturnValue({ authedApi, logout });
  await render(<SettingsScreen />);
  await waitFor(() => expect(screen.getByTestId('delete-account-button')).toBeTruthy());

  await fireEvent.press(screen.getByTestId('delete-account-button'));
  await fireEvent.changeText(screen.getByTestId('delete-password'), 'hunter2');
  await fireEvent.press(screen.getByTestId('delete-confirm'));

  await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
  expect(authedApi).toHaveBeenCalledWith('/privacy/account', { method: 'DELETE', body: { current_password: 'hunter2' } });
});

test('a wrong password shows the error and does not log out', async () => {
  const { ApiError } = jest.requireActual('../../../api/client');
  const authedApi = jest.fn(async (path: string) => {
    if (path === '/privacy/account') throw new ApiError('Current password is incorrect', 400);
    return { preferences: PREFERENCES };
  });
  const logout = jest.fn();
  mockedUseAuth.mockReturnValue({ authedApi, logout });
  await render(<SettingsScreen />);
  await waitFor(() => expect(screen.getByTestId('delete-account-button')).toBeTruthy());

  await fireEvent.press(screen.getByTestId('delete-account-button'));
  await fireEvent.changeText(screen.getByTestId('delete-password'), 'wrong');
  await fireEvent.press(screen.getByTestId('delete-confirm'));

  await waitFor(() => expect(screen.getByText('Current password is incorrect')).toBeTruthy());
  expect(logout).not.toHaveBeenCalled();
});
