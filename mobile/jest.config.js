module.exports = {
  preset: '@react-native/jest-preset',
  // The preset's own default only exempts react-native/@react-native(-community)
  // packages from Jest's node_modules transform-skip — every other RN library
  // this app depends on ships untranspiled ESM and needs the same exemption,
  // or `import` statements inside them throw `SyntaxError` under plain CommonJS
  // require(). Extend, don't replace the base pattern (jest.config.js can't
  // merge arrays with a preset, so the whole thing has to be re-listed here).
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|@react-navigation|react-native-gesture-handler|react-native-safe-area-context|react-native-screens|react-native-keychain|react-native-maps)/)',
  ],
  // react-native-gesture-handler's native TurboModule doesn't exist in the
  // Jest environment at all — its own officially-shipped jestSetup.js mocks
  // it out. Without this, importing App.tsx (which imports the library at
  // module scope, the library's own required setup pattern) throws inside
  // TurboModuleRegistry.getEnforcing before a single test can even run.
  // Same array-can't-merge-with-a-preset issue as transformIgnorePatterns
  // above: the preset's own setupFiles (its jest/setup.js, which mocks
  // several other native modules tests rely on) must be re-listed here too,
  // not just gesture-handler's — otherwise this line would silently drop it.
  setupFiles: [
    require.resolve('@react-native/jest-preset/jest/setup.js'),
    './node_modules/react-native-gesture-handler/jestSetup.js',
  ],
};
