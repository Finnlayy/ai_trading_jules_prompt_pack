## 2026-05-27 - Frontend.html Dashboard Overhaul
**Learning:** React standalone files (no build step) require careful regex patching or manual sed when modifying. I should be extremely careful to not break existing nested structures. I successfully replaced multiple placeholder/local-storage UI elements with data-driven API elements. Dark mode is now strict CSS variables and does not rely on `localStorage`.
**Action:** When working on standalone React files like this again, it's very easy to miss a closing tag or break a hook dependency array when using regex replacements. I should probably use AST-based tools or very precise manual edits if regex gets too hairy.

## 2024-05-30 - UI TDD Single File
**Learning:** Testing React inside a single `.html` with Babel via CDN using Playwright Python requires careful wait instructions because the initial state might not render immediately and React mounts asynchronously. Also, state initialization bugs due to duplicate identifiers can easily occur when editing via regex/Bash tools and must be validated carefully.
**Action:** Always assert element visibility and wait for React to be interactive before executing clicks or verifying classes in Pytest/Playwright.

## 2024-05-24 - Agentic Stack Explorer Integration
**Learning:** React state components and conditional grid sections can quickly become desynchronized if layout states are not strictly mapped. Subjunctive mood copy ("Simulated win-rate beliefe sich auf...") works best when paired directly with prominent visual veto warnings.
**Action:** When creating multi-column grid layouts with deep conditional logic, always verify that `tab === "Tab Name"` mappings correctly correspond to the string values set inside sidebar navigation arrays.
