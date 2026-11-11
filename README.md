# UK Property Watch

A public dashboard for historic country properties in England, Scotland, Wales and Ireland, prioritizing rivers and fishing rights, mature gardens, architectural character, privacy and rail access.

## Status

- `index.html`: first published dashboard source, with eight historical sample records.
- Property data are **not yet automatically synchronized** with the daily ChatGPT property search.
- Photographs are placeholders pending identification, licensing and verification.
- Listing links are included only where an actual URL has been established.
- Fishing-rights descriptions distinguish advertised claims from legally verified entitlements.

## Publish via GitHub Pages

In repository **Settings → Pages**, select **Deploy from a branch**, branch **main**, folder **/(root)**, then save.

The expected URL after activation is https://markleyboyer.github.io/UK-Property-Watch/ .

## Next engineering steps

1. Import and reconcile the full historical shortlist; deduplicate records.
2. Verify current listing URLs, property photographs and dates.
3. Move records to a versioned JSON file with source citations and last-checked timestamps.
4. Implement an authenticated, scheduled update pipeline that commits changes to the repository.
5. Record price and status history and notify only on material changes.

**Note:** A scheduled ChatGPT research task does not, by itself, update this GitHub repository.
