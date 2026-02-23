import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Keep lint signal, but don't hard-fail the build while this redesign is in flight.
      "@typescript-eslint/no-explicit-any": "warn",
      "react/no-unescaped-entities": "warn",

      // These React 19 purity rules are valuable, but they currently flag a lot of common patterns
      // in this codebase (localStorage hydration, setMounted, interval refresh, etc.).
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",

      // Avoid hard failures for nested component helpers while iterating.
      "react/no-unstable-nested-components": "warn",
    },
  },
]);

export default eslintConfig;
