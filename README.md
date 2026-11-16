# Essential Music Practice

Static rebuild of essential-music-practice.com (previously on Solo Build It), home of The Practice Code.
It shares its design system and page pattern with the LearningForSuccess site (`simonhorsey/remake`):
hero, three paths, three-step plan, numbered showcase, free guide, testimonials, closing paths.

The product ladder is: free guide → **First Steps** (starter book) → **The Practice Code** (full book) →
**The Practice Code Academy** (online course). Teachers have their own section and page, with certification planned for later.
No ads, no trackers, and nothing to install beyond Python 3.

## Change the words

Sales copy, prices, links, navigation and redirects all live in **`site.json`**.
Articles and simple pages are one file each in **`content/`**.

While `"draft": true` is set, anything still waiting on you shows a red "Draft" tag and search
engines are told not to index the site. Fill a `null` in and its tag goes. Set `"draft": false` to launch.

## Run it

```bash
python3 build.py --serve
```

Builds into `dist/` and serves it at http://localhost:8000.

## Put it on Cloudflare

Same setup as LearningForSuccess: a Worker serving static files (`wrangler.jsonc` points at `dist/`).

1. Push this folder to a GitHub repository.
2. Cloudflare dashboard → Workers & Pages → Create application → GitHub → pick the repository.
3. Project name `essentialmusicpractice`. Build command `python3 build.py`. Deploy command `npx wrangler deploy`.
4. Every push to `main` rebuilds the site.

Preview address: https://essentialmusicpractice.simonhorsey.workers.dev

`html_handling` is set to `none` in `wrangler.jsonc` so the old `.html` addresses keep working unchanged.
In that mode Cloudflare does not serve `index.html` at `/` by itself, so `build.py` writes a
`/ /index.html 200` line at the top of `_redirects`. Leave both in place.

## Where things are

| Path | What it is |
| --- | --- |
| `site.json` | All sales copy, prices, links, navigation, article sections and redirects |
| `content/*.html` | One file per page: a short header, then the page HTML |
| `build.py` | Builds the site. Page layouts are described at the top of the file |
| `static/` | CSS, scripts, fonts, images and PDFs, copied to `dist/` unchanged |
| `source/pages/` | Untouched copy of every page from the old site (16 Nov 2026) |
| `tools/convert.py` | One-off converter from `source/pages` to `content/`. Never run it with `--force`: it overwrites hand edits |

## Before launch

- [ ] First Steps (the starter book): write it, then set its price and checkout link (`offers.first-steps` in `site.json`)
- [ ] The Practice Code: price, checkout link and final contents (`offers.book`)
- [ ] Academy and teacher pages: confirm the draft outlines (`offers.academy`, `offers.teachers`)
- [ ] Newsletter provider (`forms.newsletter_action`) and contact form (`forms.contact_action`)
- [ ] Review `content/privacy-policy.html` and `content/simon-horsey.html`
- [ ] Real book cover and a larger author photo
- [ ] Transfer the domain away from SiteSell and copy the Google mail (MX) records first
- [ ] Set `"draft": false`
