import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ChatScreen } from '../ChatScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const MESSAGES = [
  { id: 'm-1', thread_id: 't-1', sender_user_id: 'me', content: 'Hi!', is_flagged: false, is_read: true, created_at: '2026-09-17T10:00:00Z' },
  { id: 'm-2', thread_id: 't-1', sender_user_id: 'other', content: 'Just call me on 07911 123456', is_flagged: true, is_read: false, created_at: '2026-09-17T10:01:00Z' },
];

function routeWith(threadId: string) {
  return { params: { threadId } } as any;
}

test('renders messages, flags the flagged one, and sends a new one', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/messages/threads/t-1' && !opts) return MESSAGES;
    if (path === '/messages' && opts?.method === 'POST') {
      return { id: 'm-3', thread_id: 't-1', sender_user_id: 'me', content: opts.body.content, is_flagged: false, is_read: true, created_at: '2026-09-17T10:02:00Z' };
    }
    throw new Error(`unexpected call: ${path} ${JSON.stringify(opts)}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi, state: { status: 'signedIn', claims: { sub: 'me' } } });

  await render(<ChatScreen route={routeWith('t-1')} />);
  await waitFor(() => expect(screen.getByText('Hi!')).toBeTruthy());
  expect(screen.getByText(/07911 123456/)).toBeTruthy();
  expect(screen.getByTestId('flag-m-2')).toBeTruthy();

  await fireEvent.changeText(screen.getByTestId('chat-input'), 'Sounds good');
  await fireEvent.press(screen.getByTestId('chat-send'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/messages', { method: 'POST', body: { thread_id: 't-1', content: 'Sounds good' } }));
});
