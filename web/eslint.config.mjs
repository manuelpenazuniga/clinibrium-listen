import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Vendored third-party visual components (see THIRD_PARTY_NOTICES.md),
    // kept close to upstream. They mutate refs / three.js objects inside
    // render-loop callbacks by design, which the React Compiler lint rules
    // flag. The rules stay ON for all of our own code.
    files: ["components/ui/orb.tsx", "components/ui/waveform.tsx"],
    rules: {
      "react-hooks/refs": "off",
      "react-hooks/immutability": "off",
      "react-hooks/purity": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "lib/contracts.ts",
  ]),
]);

export default eslintConfig;
