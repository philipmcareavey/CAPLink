import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractDetailScreen } from '../ContractDetailScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PENDING_MILESTONE = { id: 'm-1', description: 'Data prototype', due_date: null, payment_amount_gbp: 200, status: 'pending', stripe_payment_intent_status: null, captured_at: null };
const CONTRACT = {
  id: 'c-1', project_id: 'p-1', student_id: 's-1', business_id: 'b-1', status: 'active',
  ip_assignment_accepted: true, nda_accepted: true, payment_rail: 'self_employed',
  milestones: [PENDING_MILESTONE], project_title: 'Build a customer analytics dashboard',
  counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics',
};

function routeWith(contract: typeof CONTRACT) {
  return { params: { contract } } as any;
}

test('a student sees Submit on a pending milestone and it calls the submit endpoint', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/contracts/milestones/m-1/submit' && opts?.method === 'POST') {
      return { ...PENDING_MILESTONE, status: 'submitted' };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi, state: { status: 'signedIn', claims: { role: 'student' } } });

  await render(<ContractDetailScreen route={routeWith(CONTRACT)} navigation={{ navigate: jest.fn() } as any} />);
  expect(screen.getByText('Data prototype')).toBeTruthy();
  await fireEvent.press(screen.getByTestId('submit-m-1'));
  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/contracts/milestones/m-1/submit', { method: 'POST' }));
});

const SUBMITTED_CONTRACT = { ...CONTRACT, milestones: [{ ...PENDING_MILESTONE, status: 'submitted' }] };

test('a business sees Approve & pay on a submitted milestone', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(), state: { status: 'signedIn', claims: { role: 'business' } } });
  await render(<ContractDetailScreen route={routeWith(SUBMITTED_CONTRACT)} navigation={{ navigate: jest.fn() } as any} />);
  expect(screen.getByTestId('approve-pay-m-1')).toBeTruthy();
});

// The negative half the test above used to only claim in its name: the same
// submitted milestone must NOT offer approve-and-pay to the student.
test('a student does not see Approve & pay on the same submitted milestone', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(), state: { status: 'signedIn', claims: { role: 'student' } } });
  await render(<ContractDetailScreen route={routeWith(SUBMITTED_CONTRACT)} navigation={{ navigate: jest.fn() } as any} />);
  expect(screen.queryByTestId('approve-pay-m-1')).toBeNull();
});
