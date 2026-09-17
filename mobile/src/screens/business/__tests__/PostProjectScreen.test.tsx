import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { PostProjectScreen } from '../PostProjectScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const AGREEMENT = {
  id: 'a-1', university_id: 'uni-1', university_name: 'University of Manchester', business_id: 'b-1',
  status: 'approved', allowed_bands: ['year_3', 'year_4_plus'], allowed_categories: ['data_analytics'],
  max_active_projects: null, requires_university_project_review: false,
};

test('loads approved agreements and posts a project targeting the selected one', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/businesses/me/agreements') return [AGREEMENT];
    if (path === '/projects' && opts?.method === 'POST') {
      return { id: 'p-new', ...opts.body, status: 'open' };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  await render(<PostProjectScreen navigation={{ goBack } as any} />);
  await waitFor(() => expect(screen.getByText('University of Manchester')).toBeTruthy());

  await fireEvent.changeText(screen.getByTestId('post-title'), 'New project');
  await fireEvent.changeText(screen.getByTestId('post-description'), 'Description text');
  await fireEvent.changeText(screen.getByTestId('post-rate'), '25');
  await fireEvent.press(screen.getByText('University of Manchester'));
  await fireEvent.press(screen.getByText('year_3'));
  await fireEvent.press(screen.getByTestId('post-submit'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/projects', {
    method: 'POST',
    body: expect.objectContaining({
      title: 'New project',
      target_university_ids: ['uni-1'],
      target_bands: ['year_3'],
      category: 'data_analytics',
    }),
  }));
  expect(goBack).toHaveBeenCalled();
});
