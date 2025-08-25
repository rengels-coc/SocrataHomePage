# Stylesheet Cleanup Summary

Date: 2025-08-25

## Canonical Stylesheet
`assets/combined_all.css` is now the single layout/style bundle used by both `index.html` and `portal.html`.

It intentionally retains four `@import` statements for fonts/icons:
- `all.css.css` (Font Awesome / icons)
- `OpenSans.css.css`
- `Roboto.css.css`
- `tyler-icons-standard.css.css`

These remain separate for clarity, easy future removal, and to avoid path rewriting risk. They must stay in `assets/`.

## Changes Performed
1. `index.html` and `portal.html` each reduced to one `<link>` pointing at `assets/combined_all.css`.
   - Original long blocks of `<link>` tags preserved via comments (portal) or note comment (index) for rollback context.
2. Deleted redundant / unused bundle artifact:
   - `assets/combined.css` (legacy duplicate of combined_all)
   - (No `combined.min.css` present in repo at cleanup time; previously identified as empty placeholder.)
3. Created `assets/archive/` directory (currently empty) reserved for any future temporary holding if additional deletions occur.

## Rollback Instructions
If you need to restore the previous multi-file setup:
1. Re-add (uncomment or copy) the original individual `<link>` tags into the `<head>` before other styles.
2. Remove or comment out the single `<link>` to `assets/combined_all.css` (avoid double-loading).
3. (Optional) Recreate deleted `combined.css` by copying `combined_all.css` if some legacy reference expects that filename.

## Future Optional Task (Deferred)
Full inlining of the four imported font/icon CSS files into `combined_all.css` can be automated later. Benefit is minimal (removes four small requests); risks include incorrect relative `url(...)` paths and larger cache churn. Skipped by design.

Proposed safe approach if pursued later:
- Write a small Python script to: read each import file in order, adjust relative font URLs (ensure they still point to existing font binaries), strip extra `@charset` directives, and output a banner comment marking each inlined block.
- Validate by loading pages and confirming icon glyphs & fonts render.

## Verification Checklist
- Grep confirms only one `<link>` per HTML referencing `combined_all.css`.
- `combined_all.css` still contains the four `@import` lines (expected).
- No remaining references to deleted `combined.css`.

## Notes
- Leave font/icon CSS files untouched; do not delete unless you also remove the corresponding `@import` lines or replace fonts.
- If you remove a specific font later, delete its `@import` line and associated file together.
- For custom tweaks add them at the very end of `combined_all.css` under a `/* CUSTOM OVERRIDES */` comment.

---
Updated automatically as part of cleanup.
