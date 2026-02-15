import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import tsRecommended from 'eslint-config-next/typescript';

export default [
  {
    ignores: [
      '.next/**',
      '.firebase/**',
      'node_modules/**',
      'out/**',
      'dist/**',
      'coverage/**',
      '_tmp_npm/**',
      // Utility scripts are useful, but not worth blocking deploys on lint right now.
      'scripts/**',
    ],
  },
  ...nextCoreWebVitals,
  ...tsRecommended,
  {
    rules: {
      // Pragmatic: this codebase uses `any` in API/SDK boundaries and test helpers.
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      'import/no-anonymous-default-export': 'off',

      // These rules are too strict for common patterns used in this app.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/refs': 'off',
    },
  },
];
