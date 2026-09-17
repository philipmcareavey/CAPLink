// Manual mock for react-native-maps, auto-applied by Jest to every test
// (per Jest's node_modules manual-mock convention: a file here, adjacent to
// node_modules, is used automatically without a per-test jest.mock() call).
// Needed because react-native-maps' native TurboModule
// (RNMapsAirModule) doesn't exist in the Jest environment at all — merely
// *importing* the real package (e.g. transitively, via App.tsx ->
// RootNavigator -> StudentTabs -> LocalSearchMapScreen) throws at
// module-load time otherwise. Tests that need to assert on props passed to
// MapView/Marker (see LocalSearchMapScreen.test.tsx) still declare their own
// more detailed jest.mock('react-native-maps', ...) inline, which Jest lets
// override this automatic one.
const React = require('react');
const { View } = require('react-native');

const MapView = ({ children, ...props }) => React.createElement(View, props, children);
const Marker = (props) => React.createElement(View, props);
const Callout = ({ children, ...props }) => React.createElement(View, props, children);

module.exports = { __esModule: true, default: MapView, Marker, Callout };
