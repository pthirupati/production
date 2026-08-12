import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import a11y from 'eslint-plugin-jsx-a11y'
import globals from 'globals'

export default [
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2021 },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks, 'jsx-a11y': a11y },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/no-unescaped-entities': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // no-undef is an ERROR (not warn): an undefined symbol — e.g. a missing
      // import — is a real runtime crash, not a style nit. A missing import in
      // ScenarioDetail.jsx crashed the scenario page in prod while all CI was
      // green, because this was warn-only and warnings were suppressed. Keeping
      // it as an error makes `eslint` exit non-zero so the CI job fails.
      'no-undef': 'error',
      'no-empty': 'warn',
      'no-useless-escape': 'off',
      'no-control-regex': 'off',

      // ── Accessibility (audit Z6-12) ──────────────────────────────────────
      //
      // NOT the full jsx-a11y recommended set. Measured first: it reports **789**
      // violations, overwhelmingly `label-has-associated-control` (302),
      // `no-static-element-interactions` (197) and `click-events-have-key-events`
      // (173). Turning all of that on would either fail the build on day one or,
      // worse, be downgraded to warnings and ignored — which is how a lint rule
      // stops meaning anything.
      //
      // These 26 rules are the ones the codebase **already passes**. Gating them as
      // errors costs nothing today and makes a regression impossible: shipping an
      // <img> with no alt, an invalid ARIA role, or a positive tabindex now fails
      // CI. The same ratchet approach as ruff on the backend.
      //
      // The three big remaining rules are a real backlog, not an oversight — every
      // clickable <div> in the app needs a keyboard handler, which is a change to
      // behaviour rather than to config.
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/anchor-has-content': 'error',
      'jsx-a11y/aria-activedescendant-has-tabindex': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-proptypes': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/autocomplete-valid': 'error',
      'jsx-a11y/heading-has-content': 'error',
      'jsx-a11y/html-has-lang': 'error',
      'jsx-a11y/iframe-has-title': 'error',
      'jsx-a11y/img-redundant-alt': 'error',
      'jsx-a11y/mouse-events-have-key-events': 'error',
      'jsx-a11y/no-access-key': 'error',
      'jsx-a11y/no-distracting-elements': 'error',
      'jsx-a11y/no-interactive-element-to-noninteractive-role': 'error',
      'jsx-a11y/no-noninteractive-element-to-interactive-role': 'error',
      'jsx-a11y/no-noninteractive-tabindex': 'error',
      'jsx-a11y/no-redundant-roles': 'error',
      'jsx-a11y/role-has-required-aria-props': 'error',
      'jsx-a11y/role-supports-aria-props': 'error',
      'jsx-a11y/scope': 'error',
      'jsx-a11y/tabindex-no-positive': 'error',
    },
  },
  {
    // R3F / drei use non-DOM props (args, attach, intensity, …)
    files: [
      'src/**/*Twin3D*.jsx',
      'src/**/*Scene3D*.jsx',
      'src/**/r3f/**/*.{js,jsx}',
      'src/components/datacenter/DcCableSystem.jsx',
    ],
    rules: {
      'react/no-unknown-property': 'off',
    },
  },
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
]
