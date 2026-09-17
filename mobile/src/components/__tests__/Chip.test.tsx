import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { Chip } from '../Chip';

// NOTE: @testing-library/react-native@14 made `render` async (it now uses
// the new `test-renderer` package, not the old sync react-test-renderer) —
// `render(...)` returns a Promise, so it must be awaited before `screen`
// queries work. Every future screen test using `render` needs the same
// `await`.
test('renders the given label', async () => {
  await render(<Chip label="Python" />);
  expect(screen.getByText('Python')).toBeTruthy();
});

test('applies reason styling when tone is "reason"', async () => {
  await render(<Chip label="Within budget" tone="reason" />);
  expect(screen.getByText('Within budget')).toBeTruthy();
});
