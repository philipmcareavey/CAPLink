import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ThreadsListScreen } from '../ThreadsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const THREADS = [
  { thread_id: 't-1', project_id: 'p-1', counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics', last_message_preview: 'Looking forward!', last_message_at: '2026-09-17T10:00:00Z', unread_count: 2 },
];

test('renders threads with an unread badge', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => THREADS) });
  const navigate = jest.fn();
  await render(<ThreadsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Northbridge Analytics')).toBeTruthy());
  expect(screen.getByText('2')).toBeTruthy();
});

test('tapping a thread navigates to Chat with its id', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => THREADS) });
  const navigate = jest.fn();
  await render(<ThreadsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => screen.getByText('Northbridge Analytics'));
  await fireEvent.press(screen.getByText('Northbridge Analytics'));
  expect(navigate).toHaveBeenCalledWith('Chat', { threadId: 't-1' });
});
