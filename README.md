# UK Property Watch

A public dashboard for historic country properties in England, Scotland, Wales and Ireland, prioritizing rivers and fishing rights, mature gardens, architectural character, privacy and rail access.

Live site: https://markleyboyer.github.io/UK-Property-Watch/

## How it works

- `data/properties.json` is the single source of truth (one record per property, with `id`, listing `link`, notes, and a `check` block).
- `index.html` loads that JSON and renders the cards. No data is embedded in the page.
- `images/<id>.jpg` are thumbnails saved **in this repo**. The site never hotlinks agent CDNs (Rightmove, OnTheMarket, Zoopla…), which is why the original thumbnails failed.
- `scripts/refresh.py` visits each listing link, finds the lead photo (`og:image`, `twitter:image`, JSON-LD), saves a resized copy, and records whether the page still exists and whether its title mentions *sold / under offer / withdrawn*. It only adds hints; it never edits `status` or other human-written fields.
- `.github/workflows/refresh.yml` runs the script every second day (05:17 UTC), commits any changes to `main`, and triggers a Pages rebuild. It can also be run by hand from the **Actions** tab.
- `data/last_run.json` summarises the most recent run, including any records that still have no thumbnail.

New listings and missing links are added by a separate scheduled research task that edits `data/properties.json` and opens a PR/commit.

## Run locally

    pip install requests pillow
    python scripts/refresh.py            # all records
    python scripts/refresh.py --only craskie-estate --force

## Notes

- Fishing-rights wording distinguishes advertised claims from legally verified entitlements. Nothing here is verified title.
- Some agent sites block automated requests; those records show a "blocks automated checks" note and keep any earlier thumbnail.
- Records with no `link` cannot get a thumbnail until a listing URL is added.

## GitHub Pages

Settings → Pages → Deploy from a branch → `main` / `(root)`.
