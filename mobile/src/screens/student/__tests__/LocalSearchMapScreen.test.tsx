import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { LocalSearchMapScreen } from '../LocalSearchMapScreen';
import { useAuth } from '../../../context/AuthContext';
import { ApiError } from '../../../api/client';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const mockAnimateToRegion = jest.fn();

jest.mock('react-native-maps', () => {
  const ReactLib = require('react');
  const { View } = require('react-native');
  // Forwards a ref exposing animateToRegion, since the screen keeps a MapView
  // ref specifically to re-centre the map after each successful search.
  // (The spy has to be named mock* — jest.mock factories may only reference
  // out-of-scope variables whose names start with "mock".)
  const MockMapView = ReactLib.forwardRef(({ children, ...props }: any, ref: any) => {
    ReactLib.useImperativeHandle(ref, () => ({ animateToRegion: mockAnimateToRegion }));
    return <View testID="map-view" {...props}>{children}</View>;
  });
  const MockMarker = (props: any) => <View testID={`marker-${props.testID ?? props.title}`} {...props} />;
  return { __esModule: true, default: MockMapView, Marker: MockMarker };
});

const META = { campus_name: 'University of Manchester', campus_postcode: 'M13 9PL', campus_latitude: 53.4668, campus_longitude: -2.2339, radius_miles: 10, total_results: 1 };
const RESULTS = [
  { business_id: 'b-1', company_name: 'Northbridge Analytics', industry: 'Data & Analytics', postcode: 'M1 1AE', latitude: 53.4794, longitude: -2.2453, distance_miles: 2.1, degree_relevance_score: 0.9, degree_relevance_label: 'Data Science', approved_categories: ['data_analytics'], average_rating: 4.5, completed_projects_count: 3 },
];

test('centers the map on campus and plots a marker per result', async () => {
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async (path: string) => {
      if (path.includes('/local-businesses/meta')) return META;
      if (path.includes('/local-businesses?')) return RESULTS;
      throw new Error(`unexpected call: ${path}`);
    }),
    state: { status: 'signedIn', claims: { university_id: 'uni-1' } },
  });

  await render(<LocalSearchMapScreen />);
  await waitFor(() => expect(screen.getByTestId('map-view')).toBeTruthy());
  const map = screen.getByTestId('map-view');
  expect(map.props.initialRegion.latitude).toBe(53.4668);
  expect(map.props.initialRegion.longitude).toBe(-2.2339);
  expect(screen.getByTestId('marker-Northbridge Analytics')).toBeTruthy();
});

test('re-centres and re-zooms the map after a wider-radius search', async () => {
  mockAnimateToRegion.mockClear();
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async (path: string) => {
      if (path.includes('/local-businesses/meta')) return META;
      if (path.includes('/local-businesses?')) return RESULTS;
      throw new Error(`unexpected call: ${path}`);
    }),
    state: { status: 'signedIn', claims: { university_id: 'uni-1' } },
  });

  await render(<LocalSearchMapScreen />);
  await waitFor(() => expect(screen.getByTestId('map-view')).toBeTruthy());

  await fireEvent.changeText(screen.getByTestId('radius-input'), '50');
  await fireEvent.press(screen.getByTestId('run-search'));

  // initialRegion only applies at mount, so a wider radius has to be applied
  // imperatively or the new markers land outside the viewport.
  await waitFor(() => expect(mockAnimateToRegion).toHaveBeenCalledWith({
    latitude: META.campus_latitude,
    longitude: META.campus_longitude,
    latitudeDelta: (50 / 69) * 2,
    longitudeDelta: (50 / 69) * 2,
  }));
});

test('keeps the search controls usable when a search fails', async () => {
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async () => {
      throw new ApiError('Search failed on the server.', 500);
    }),
    state: { status: 'signedIn', claims: { university_id: 'uni-1' } },
  });

  await render(<LocalSearchMapScreen />);
  await waitFor(() => expect(screen.getByText('Search failed on the server.')).toBeTruthy());
  // The error is a card above the controls, not a screen that replaces them.
  expect(screen.getByTestId('radius-input')).toBeTruthy();
  expect(screen.getByTestId('run-search')).toBeTruthy();
});
