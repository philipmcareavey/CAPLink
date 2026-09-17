import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import { RatingsScreen } from '../RatingsScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const RATINGS = [
  { id: 'r-1', contract_id: 'c-1', counterpart_user_id: 'u-2', direction: 'given', is_released: true, overall_score: 5, sub_scores: { communication: 5 }, visibility: 'public' },
  { id: 'r-2', contract_id: 'c-1', counterpart_user_id: 'u-2', direction: 'received', is_released: false, overall_score: null, sub_scores: null, visibility: 'public' },
];

test('splits ratings into Given and Received sections, hiding an unreleased received score', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => RATINGS) });
  await render(<RatingsScreen />);
  await waitFor(() => expect(screen.getByText('Given')).toBeTruthy());
  expect(screen.getByText('Received')).toBeTruthy();
  expect(screen.getByText('5.0')).toBeTruthy();
  expect(screen.getByText('Hidden until both sides rate')).toBeTruthy();
});

test('shows a rating you gave even before it is released — the server only blinds RECEIVED ones', async () => {
  const givenUnreleased = [
    { id: 'r-3', contract_id: 'c-2', counterpart_user_id: 'u-3', direction: 'given', is_released: false, overall_score: 4, sub_scores: null, visibility: 'public' },
  ];
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => givenUnreleased) });
  await render(<RatingsScreen />);
  await waitFor(() => expect(screen.getByText('4.0')).toBeTruthy());
  expect(screen.queryByText('Hidden until both sides rate')).toBeNull();
});
