Use this as the agent task.

This lint pass should support Step 4’s role as a **read-only analyst browser**, so the rules should focus on **correctness, React safety, accessibility, and test hygiene**, not style churn or cosmetic formatting battles. Step 4.2 is only a thin UI shell, not a big app, so keep the lint setup strong but pragmatic.

# Agent task — set up proper linting for `ui/explorer`

## Goal

Upgrade the current lint setup from a minimal baseline to a **real project-grade ESLint configuration** for a React + TypeScript + Vite UI.

The final setup must:

* catch React correctness issues
* catch TypeScript async/promise mistakes
* catch unused imports and poor import hygiene
* enforce basic accessibility rules
* lint Vitest and Playwright tests appropriately
* stay pragmatic for a small analyst UI
* avoid turning ESLint into a formatting tool

Do **not** use blanket disables.
Do **not** relax rules globally just to make the code pass.
If a rule is too noisy, scope the override to the smallest possible area and document why.

---

## Files to change

At minimum:

* `ui/explorer/package.json`
* `ui/explorer/eslint.config.js`

Possibly add/update:

* `ui/explorer/.eslintcache` in `.gitignore`
* CI workflow or verify script if this repo has one
* a short section in `ui/explorer/README.md` for lint commands

---

## 1) Install the missing lint plugins

From `ui/explorer/` install:

```bash
npm i -D eslint-plugin-react eslint-plugin-jsx-a11y eslint-plugin-testing-library eslint-plugin-playwright eslint-plugin-unused-imports eslint-plugin-simple-import-sort
```

Do **not** add Prettier in this task. Keep lint semantic, not formatting-first.

---

## 2) Replace the current ESLint config with a stronger flat config

Replace `ui/explorer/eslint.config.js` with this baseline and adjust only if a plugin export shape differs in the installed version.

```js
import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import testingLibrary from 'eslint-plugin-testing-library'
import playwright from 'eslint-plugin-playwright'
import unusedImports from 'eslint-plugin-unused-imports'
import simpleImportSort from 'eslint-plugin-simple-import-sort'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'node_modules/**',
      'playwright-report/**',
      'test-results/**',
      '.eslintcache',
    ],
  },

  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,

  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: {
        projectService: true,
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      'unused-imports': unusedImports,
      'simple-import-sort': simpleImportSort,
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,

      // React correctness
      'react-hooks/set-state-in-effect': 'error',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'react/jsx-key': 'error',
      'react/no-unknown-property': 'error',
      'react/self-closing-comp': 'warn',

      // General safety
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'error',
      'curly': ['error', 'all'],
      'eqeqeq': ['error', 'always', { null: 'ignore' }],

      // TypeScript safety
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': [
        'error',
        { checksVoidReturn: { attributes: false } },
      ],
      '@typescript-eslint/no-unnecessary-condition': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',

      // Unused code / import hygiene
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      'unused-imports/no-unused-imports': 'error',
      'unused-imports/no-unused-vars': [
        'warn',
        {
          vars: 'all',
          varsIgnorePattern: '^_',
          args: 'after-used',
          argsIgnorePattern: '^_',
          caughtErrors: 'all',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',

      // Accessibility
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/role-has-required-aria-props': 'error',
      'jsx-a11y/role-supports-aria-props': 'error',
      'jsx-a11y/no-autofocus': ['warn', { ignoreNonDOM: true }],
    },
  },

  {
    files: ['**/*.{test,spec}.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.vitest,
      },
    },
    plugins: {
      'testing-library': testingLibrary,
    },
    rules: {
      ...(testingLibrary.configs['flat/react']?.rules ?? {}),
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/unbound-method': 'off',
      'no-console': 'off',
    },
  },

  {
    files: ['tests/e2e/**/*.{ts,tsx}'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    plugins: {
      playwright,
    },
    rules: {
      ...(playwright.configs['flat/recommended']?.rules ?? {}),
      'playwright/no-focused-test': 'error',
      'playwright/no-skipped-test': 'warn',
    },
  },

  {
    files: ['eslint.config.js', 'vite.config.ts', 'playwright.config.ts'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
)
```

### Important rule choice

Keep:

```js
'react-hooks/set-state-in-effect': 'error'
```

That rule should stay strong because it already caught a real issue pattern in this UI flow.

---

## 3) Update npm scripts

In `ui/explorer/package.json`, replace the lint scripts with these:

```json
{
  "scripts": {
    "lint": "eslint . --cache --cache-location .eslintcache",
    "lint:fix": "eslint . --fix --cache --cache-location .eslintcache",
    "lint:ci": "eslint . --max-warnings=0",
    "typecheck": "tsc -b --noEmit",
    "verify": "npm run typecheck && npm run lint:ci && npm run test"
  }
}
```

Keep existing `build`, `test`, and `test:e2e` scripts unless they need small compatibility updates.

Also add `.eslintcache` to `.gitignore` if it is not already ignored.

---

## 4) Fix current violations instead of weakening rules

After the config change:

```bash
npm run lint
```

Then fix all violations.

### Priority order for fixes

#### A. React correctness

Fix any:

* setState in effect loops
* missing hook deps
* unsafe async event handling

#### B. Import hygiene

Run:

```bash
npm run lint:fix
```

Then manually clean any remaining:

* unused imports
* unsorted imports
* duplicated type/value imports

#### C. Accessibility

Fix real issues, especially:

* missing alt text
* invalid aria props
* interactive elements without clear accessible semantics

#### D. Tests

For test-only violations, prefer **narrow overrides** over global config weakening.

Example:

* `any` can stay allowed in tests
* non-null assertions can stay allowed in tests
* app code should remain stricter than tests

---

## 5) Do not add these noisy rules in this pass

Do **not** enable a flood of stylistic rules that create churn without much value.

Avoid in this pass:

* mandatory explicit return types everywhere
* overly strict naming conventions
* exhaustive JSX prop sorting
* semicolon/quote battles
* magic-number policing
* very strict `no-explicit-any` as error
* huge `import/no-cycle` style dependency policing

This is a lint hardening pass for reliability, not a formatting crusade.

---

## 6) Add a small README section

Update `ui/explorer/README.md` with:

```md
## Linting

Run locally:

- `npm run lint`
- `npm run lint:fix`
- `npm run lint:ci`

Project linting focuses on:
- React correctness
- TypeScript async safety
- accessibility
- test hygiene
- import cleanup
```

---

## 7) CI / verification expectation

If this repo has CI for the UI, make sure the UI job runs:

```bash
npm ci
npm run typecheck
npm run lint:ci
npm run test
npm run build
```

Do not let lint become optional.

---

## 8) What I want back from the agent

Return:

1. updated `eslint.config.js`
2. updated `package.json`
3. list of installed dev dependencies
4. summary of code fixes made to satisfy lint
5. output of:

   * `npm run typecheck`
   * `npm run lint`
   * `npm run test`
   * `npm run build`

Also explicitly mention:

* which rules had to be scoped only to tests
* whether any rule had to be downgraded because it was too noisy
* whether any file needed a one-line inline disable, and why

---

## 9) Done criteria

This task is done only when all are true:

* `npm run typecheck` passes
* `npm run lint` passes
* `npm run lint:ci` passes
* `npm run test` passes
* `npm run build` passes
* no blanket `eslint-disable` comments were added
* no global weakening was done just to silence one file
* app code is stricter than test code

---

## 10) One implementation note for the agent

This UI is part of the analyst browser layer, so the lint rules should protect:

* correctness of routed detail pages
* reliability of search/filter state
* safe async behavior
* accessibility of the inspection surface

They should **not** try to turn the project into a style-only ruleset. That keeps the lint aligned with the actual Step 4 purpose.

**Confidence: High** — based on the current UI bundle shape, the existing minimal ESLint setup, and the specific reliability issues already surfaced during the Step 4.2 audit.
