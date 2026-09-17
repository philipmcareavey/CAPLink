import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractFormScreen } from '../ContractFormScreen';
import { useAuth } from '../../../context/AuthContext';
import { ApiError } from '../../../api/client';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

function routeWith(applicationId: string) {
  return { params: { applicationId, projectId: 'p-1' } } as any;
}

test('adds a milestone row and submits a contract with all rows', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/contracts' && opts?.method === 'POST') {
      return { id: 'c-new', ...opts.body };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  await render(<ContractFormScreen route={routeWith('app-1')} navigation={{ goBack } as any} />);

  await fireEvent.changeText(screen.getByTestId('milestone-description-0'), 'First milestone');
  await fireEvent.changeText(screen.getByTestId('milestone-amount-0'), '200');
  await fireEvent.press(screen.getByTestId('add-milestone'));
  await fireEvent.changeText(screen.getByTestId('milestone-description-1'), 'Second milestone');
  await fireEvent.changeText(screen.getByTestId('milestone-amount-1'), '240');

  await fireEvent.press(screen.getByTestId('create-contract'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/contracts', {
    method: 'POST',
    body: {
      application_id: 'app-1',
      milestones: [
        { description: 'First milestone', payment_amount_gbp: 200 },
        { description: 'Second milestone', payment_amount_gbp: 240 },
      ],
    },
  }));
  expect(goBack).toHaveBeenCalled();
});

test('refuses to submit a blank amount rather than creating a silent £0 milestone', async () => {
  const authedApi = jest.fn();
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  await render(<ContractFormScreen route={routeWith('app-1')} navigation={{ goBack } as any} />);
  await fireEvent.changeText(screen.getByTestId('milestone-description-0'), 'First milestone');
  // amount deliberately left blank — Number('') is 0, which the backend's ge=0 accepts
  await fireEvent.press(screen.getByTestId('create-contract'));

  await waitFor(() => expect(screen.getByText('Every milestone needs a description and an amount greater than £0.')).toBeTruthy());
  expect(authedApi).not.toHaveBeenCalled();
  expect(goBack).not.toHaveBeenCalled();
});

test('shows an error card and stays usable when the POST fails', async () => {
  const authedApi = jest.fn(async () => {
    throw new ApiError('That application already has a contract.', 400);
  });
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  await render(<ContractFormScreen route={routeWith('app-1')} navigation={{ goBack } as any} />);
  await fireEvent.changeText(screen.getByTestId('milestone-description-0'), 'First milestone');
  await fireEvent.changeText(screen.getByTestId('milestone-amount-0'), '200');
  await fireEvent.press(screen.getByTestId('create-contract'));

  await waitFor(() => expect(screen.getByText('That application already has a contract.')).toBeTruthy());
  expect(goBack).not.toHaveBeenCalled();
  // The form is still there to retry with, not replaced by the error.
  expect(screen.getByTestId('create-contract')).toBeTruthy();
});
