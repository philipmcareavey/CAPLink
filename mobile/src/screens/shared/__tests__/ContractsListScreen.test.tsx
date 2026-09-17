import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractsListScreen } from '../ContractsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const CONTRACT = {
  id: 'c-1', project_id: 'p-1', student_id: 's-1', business_id: 'b-1', status: 'active',
  ip_assignment_accepted: true, nda_accepted: true, payment_rail: 'self_employed',
  milestones: [{ id: 'm-1', description: 'Data prototype', due_date: null, payment_amount_gbp: 200, status: 'pending', stripe_payment_intent_status: null, captured_at: null }],
  project_title: 'Build a customer analytics dashboard', counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics',
};

test('lists contracts and navigates to detail on tap', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => [CONTRACT]), state: { status: 'signedIn', claims: { role: 'student' } } });
  const navigate = jest.fn();
  await render(<ContractsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Build a customer analytics dashboard')).toBeTruthy());
  await fireEvent.press(screen.getByText('Build a customer analytics dashboard'));
  expect(navigate).toHaveBeenCalledWith('Detail', { contract: CONTRACT });
});
