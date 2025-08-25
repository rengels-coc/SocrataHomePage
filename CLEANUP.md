# CSS Fragment Cleanup

Date: 2025-08-25

All individually extracted `assets/css-<uuid>_mhtml.blink.css` fragment files
have been removed to reduce repository clutter after consolidating them into
`assets/combined.css` (and optional `combined.min.css`).

## Rationale
* Visual parity confirmed using the unified stylesheet.
* Order of rules is preserved inside `combined.css`; keeping the fragments
  offered no additional value but added noise.

## Regenerating (If Ever Needed)
1. Re-run the original MHTML conversion if you want fresh fragments:
   ```bash
   python mhtml_to_html.py "City of Seattle Open Data portal.mhtml" index.html assets
   ```
2. Rebuild the combined file:
   ```bash
   python bundle_css.py
   ```
3. Commit the updated `combined.css` (leave fragment files untracked unless
   you have a specific audit need).

## Adding Overrides
Place any hand-authored tweaks at the bottom of `assets/combined.css` below the
`CUSTOM OVERRIDES` marker to keep provenance clear.

## Print / Theming Considerations
If a future need arises for a distinct print or theme stylesheet, add a new
dedicated file (e.g. `print.css`) and document its purpose here (do NOT split
the combined file casually—ensure the cascade impact is understood).

-- End of note --
