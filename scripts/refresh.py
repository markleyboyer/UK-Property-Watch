#!/usr/bin/env python3
"""Refresh data/properties.json.

For every record with a listing link this:
  1. fetches the listing page (browser-like headers),
  2. records whether the page still exists and whether its title/description
     mentions sold / under offer / withdrawn (a hint only; it never edits `status`),
  3. finds the lead photo (og:image, twitter:image, JSON-LD, then `image_hint`),
  4. downloads it, resizes it, and saves it to images/<id>.jpg so the site never
     hotlinks agent CDNs (which is what broke the original thumbnails).

Run locally:  pip install requests pillow && python scripts/refresh.py
Options:      --only id1,id2   limit to some records
              --force          re-download thumbnails even if the source is unchanged
"""
import argparse, datetime, html, io, json, pathlib, re, sys, time
from urllib.parse import urljoin

import requests
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "properties.json"
IMG_DIR = ROOT / "images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
HINT_RE = re.compile(
    r"\b(sold stc|sold subject to contract|sstc|under offer|sale agreed|sold|withdrawn|"
    r"no longer available|off the market)\b", re.I)
SKIP_URL_RE = re.compile(r"logo|favicon|placeholder|sprite|no[-_]?image|default[-_]", re.I)
MIN_WIDTH = 300           # rejects 1x1 trackers / logos
MAX_SIDE = 900
META_RE = re.compile(r"<meta\b[^>]*>", re.I)
ATTR_RE = re.compile(r'([a-zA-Z:_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')


def meta_tags(page):
    for tag in META_RE.findall(page):
        attrs = {k.lower(): (v1 or v2) for k, _, v1, v2 in ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key and "content" in attrs:
            yield key, html.unescape(attrs["content"])


def image_candidates(page, base):
    seen, out = set(), []

    def add(u):
        if u and not u.startswith("data:"):
            u = urljoin(base, u.strip())
            if u not in seen:
                seen.add(u)
                out.append(u)

    metas = list(meta_tags(page))
    for want in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        for k, v in metas:
            if k == want:
                add(v)
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                img = x.get("image")
                if isinstance(img, str):
                    add(img)
                elif isinstance(img, list):
                    for i in img:
                        add(i if isinstance(i, str) else (i or {}).get("url"))
                elif isinstance(img, dict):
                    add(img.get("url"))
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    return out


def page_hint(page):
    texts = [m.group(1) for m in re.finditer(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)]
    texts += [v for k, v in meta_tags(page) if k in ("og:title", "og:description", "description")]
    m = HINT_RE.search(html.unescape(" ".join(texts)))
    return m.group(1).lower() if m else ""


def fetch_image(url, referer):
    r = requests.get(url, headers={**HEADERS, "Referer": referer,
                                   "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}, timeout=30)
    r.raise_for_status()
    if len(r.content) < 20_000:                       # logos / placeholders are tiny files
        raise ValueError(f"file too small ({len(r.content)} bytes)")
    img = Image.open(io.BytesIO(r.content))
    img.load()
    if img.width < MIN_WIDTH:
        raise ValueError(f"too small ({img.width}px)")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}

    doc = json.loads(DATA.read_text(encoding="utf-8"))
    IMG_DIR.mkdir(exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    stats = {"pages_ok": 0, "pages_gone": 0, "pages_blocked": 0, "pages_error": 0,
             "thumbs_new": 0, "thumbs_kept": 0, "thumbs_missing": 0}
    report = []

    for p in doc["properties"]:
        if only and p["id"] not in only:
            continue
        link = p.get("link") or ""
        check = {"at": stamp}
        page, cands = "", []
        if link:
            try:
                r = requests.get(link, headers=HEADERS, timeout=30, allow_redirects=True)
                check["http"] = r.status_code
                if r.status_code in (404, 410):
                    check["state"] = "gone"; stats["pages_gone"] += 1
                elif r.status_code in (401, 403, 429) or r.status_code >= 500:
                    check["state"] = "blocked"; stats["pages_blocked"] += 1
                else:
                    check["state"] = "ok"; stats["pages_ok"] += 1
                    page = r.text
                    hint = page_hint(page)
                    if hint:
                        check["hint"] = hint
                    cands = image_candidates(page, r.url)
            except requests.RequestException as e:
                check["state"] = "error"; check["error"] = type(e).__name__
                stats["pages_error"] += 1
            time.sleep(2)
        p["check"] = check

        # thumbnail
        if p.get("image_hint"):
            cands.append(p["image_hint"])
        thumb_path = IMG_DIR / f"{p['id']}.jpg"
        if p.get("thumb_source") == "manual" and thumb_path.exists() and not args.force:
            stats["thumbs_kept"] += 1          # hand-supplied image: never overwrite
            continue
        if p.get("thumb") and thumb_path.exists() and not args.force and cands and cands[0] == p.get("thumb_source"):
            stats["thumbs_kept"] += 1
            continue
        got = False
        for url in cands:
            if SKIP_URL_RE.search(url):
                continue
            try:
                img = fetch_image(url, link or url)
            except Exception as e:                      # try the next candidate
                report.append(f"{p['id']}: image failed {url[:80]} ({type(e).__name__}: {str(e)[:60]})")
                continue
            img.save(thumb_path, "JPEG", quality=80, optimize=True, progressive=True)
            p["thumb"] = f"images/{p['id']}.jpg"
            p["thumb_source"] = url
            stats["thumbs_new"] += 1
            got = True
            break
        if not got:
            if p.get("thumb") and thumb_path.exists():
                stats["thumbs_kept"] += 1               # keep the old one rather than lose it
            else:
                p["thumb"] = ""; p["thumb_source"] = ""
                stats["thumbs_missing"] += 1
                report.append(f"{p['id']}: NO THUMBNAIL ({'no link' if not link else check.get('state')})")

    doc["updated"] = now.strftime("%Y-%m-%d")
    doc["refreshed_at"] = stamp
    DATA.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (ROOT / "data" / "last_run.json").write_text(
        json.dumps({"at": stamp, "stats": stats, "notes": report}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print("\n".join(report))


if __name__ == "__main__":
    sys.exit(main())
