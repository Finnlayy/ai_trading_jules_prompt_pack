## 2024-05-22 - Add ARIA Labels to Navigation
**Learning:** Single-page React CDNs apps require manual tracking of accessibility attributes like `aria-label` since they bypass static site generators that might enforce a11y rules.
**Action:** Always verify `aria-label` presence on custom tab navigation buttons mapped from arrays.
## 2024-05-22 - Explicit Focus States in Custom Tailwind Dark Mode
**Learning:** Default Tailwind focus rings (usually blue) completely clash with the "Anti-Casino" custom dark palette and are often invisible against dark gray backgrounds.
**Action:** When building custom dark themes, always override the default focus rings on inputs and buttons with custom thematic rings (e.g., `focus-visible:ring-2 focus-visible:ring-matteMint focus:outline-none`) to ensure keyboard users have high-visibility feedback.
