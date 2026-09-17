import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractFormScreen } from '../ContractFormScreen';
import { useAuth } from '../../../context/AuthContext';

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
