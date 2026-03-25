For a **real Step 4.2 UI audit**, give me the **full audit bundle**, not just a few screenshots.

## What I need by default

### 1. The actual frontend code

Send the whole UI app or a zip with at least:

* `package.json`
* lockfile (`package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`)
* `vite.config.*`
* `tsconfig.*`
* Tailwind config
* shadcn/ui config if present
* all `src/` code
* any shared UI libs used by this app
* Playwright config
* Vitest config
* ESLint config if relevant

If it is in a monorepo, include the **workspace root files** too, not only the app folder.

---

### 2. A short audit handoff note

I need one markdown file like `AUDIT_HANDOFF.md` that says:

* what step this is
* what was implemented
* what is intentionally out of scope
* what changed since the last audit
* whether backend contracts changed
* any known issues or compromises
* exact commands to run app and tests

This saves a lot of ambiguity.

---

### 3. Backend alignment materials

Because this UI depends on the explorer API, I need:

* the expected `/browser/*` route list
* sample request/response payloads
* any Zod schemas or typed contracts if frontend uses them
* note whether backend is unchanged from accepted Step 4.1
* if backend changed, include the changed backend files too

At minimum I need the contract shape for:

* `/browser/search`
* `/browser/facets`
* `/browser/rule/{id}`
* `/browser/evidence/{id}`
* `/browser/concept/{id}`
* `/browser/concept/{id}/neighbors`
* `/browser/lesson/{id}`

---

### 4. Run instructions

I need exact instructions, not general ones.

Include:

* install command
* dev run command
* build command
* unit test command
* e2e command
* env vars required
* expected backend URL
* whether mocks are supported
* whether the UI can run without the backend

Example:

* `npm ci`
* `npm run dev`
* `npm run build`
* `npm run test`
* `npm run test:e2e`

---

### 5. Environment file examples

Include:

* `.env.example`
* any API base URL settings
* any feature flags
* any mock mode flags

If the app requires a live backend, say that explicitly.

---

### 6. Test artifacts

I need both the tests **and** their outputs.

Send:

* unit/component test files
* integration/page test files
* Playwright tests
* latest test output logs
* build output log
* typecheck output
* lint output if relevant

Best bundle includes:

* `vitest_output.txt`
* `playwright_output.txt`
* `build_output.txt`
* `typecheck_output.txt`

If Playwright generated HTML reports, include them or screenshots from them.

---

### 7. Visual proof

For UI work, I need evidence of actual behavior.

Please include screenshots or short recordings of:

* search page in browse mode
* search page with real query
* filters open
* active filter chips
* rule detail page
* evidence detail page
* concept detail page
* neighbor navigation
* lesson detail page
* not found state
* loading or empty state if possible

This helps catch issues that tests often miss.

---

### 8. Acceptance mapping

I want one file like `AUDIT_CHECKLIST.md` or section in handoff showing:

* each acceptance criterion
* where it is implemented
* what test proves it

Example format:

* Search page supports empty-query browse — `SearchPage.tsx`, `search.spec.ts`
* Filters survive refresh via URL — `useSearchUrlState.ts`, `search-page.test.tsx`
* Rule detail page renders linked evidence — `RulePage.tsx`, `detail-rule.spec.ts`

This makes audit much faster and more reliable.

---

## What functionality I will audit against

For Step 4.2, I will check all of these by default:

### Core behavior

* search works
* empty-query browse works
* filters work
* filters are reflected in URL
* result cards are usable
* rule detail works
* evidence detail works
* concept detail works
* concept neighbors work
* lesson detail works
* not-found and error states work

### Contract discipline

* UI only calls `/browser/*`
* no raw retrieval docs are accessed directly
* no hidden backend bypasses
* response parsing is typed/validated if claimed

### UX correctness

* browse vs search mode is understandable
* support/provenance is visible
* entity navigation is consistent
* page refresh preserves state
* deep links work

### Quality

* build passes
* tests pass
* no obvious dead routes
* no broken loading states
* no silent error swallowing

### Regression protection

I will also check that the accepted search behavior still shows up in the UI flow for:

* stop-loss example retrieval
* timeframe rule-card preference
* daily-level actionable preference
* any Step 3.1 behaviors explicitly claimed as preserved

---

## Exact files I would ideally like in the audit zip

This is the best-case audit bundle:

```text
AUDIT_HANDOFF.md
AUDIT_CHECKLIST.md
README.md
package.json
package-lock.json / pnpm-lock.yaml / yarn.lock
vite.config.ts
tsconfig.json
tsconfig.app.json
tailwind.config.ts
postcss.config.js
src/...
tests/...
playwright.config.ts
.env.example
vitest_output.txt
playwright_output.txt
build_output.txt
typecheck_output.txt
lint_output.txt
screenshots/
videos/
browser_api_samples/
```

If backend changed, add:

```text
backend_changed_files/
  ...
```

---

## What is the minimum I can work with

If you want a lighter audit, minimum useful set is:

* full UI source
* `package.json`
* run instructions
* test files
* test outputs
* screenshots
* `AUDIT_HANDOFF.md`

But for a **real acceptance audit**, I strongly prefer the full bundle above.

---

## One more thing I want every time

Please include a short section called:

**“Known gaps / things you want specifically challenged”**

That helps me focus on areas where the agent may have taken shortcuts.

## My recommendation

For your next UI audit, send a single zip with the full bundle plus a one-page handoff note and proof outputs.

**Confidence: High** — this is the comprehensive audit input set I would want to make a reliable acceptance decision on the UI implementation.
