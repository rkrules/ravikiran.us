# ravikiran.us — Project Context

## What this is

Static personal site for Ravikiran Rajagopal, hosted on GitHub Pages at ravikiran.us.
Source of truth: `rkrules/ravikiran.us` repo, `main` branch, served from root `/`.
DNS: 4 A records → GitHub Pages IPs. CNAME file contains `ravikiran.us`.

## How the site is built

**No build tools, no Jekyll, no Node.** One Python script generates everything.

```bash
python3 extract_posts.py   # regenerates all HTML from SQL + .md files
git add -A && git commit -m "..." && git push
```

The SQL dump (`wp_rkblogs_2023_04_04.sql`, 70 MB, gitignored) is the source for all
WordPress-era content. The script parses it directly — no database needed.

## Site sections

| URL | Source | Count |
|-----|--------|-------|
| `/` | `index.html` (hand-written profile page) | — |
| `/blog/` | `links_posts` table, non-aside posts | 17 |
| `/notes/` | `links_posts` post-format-aside (term_id=3) | 178 |
| `/journal/` | `wp_posts` private/draft/publish (2004–2021) | 583 |
| `/wedding/` | `wedding_posts` table | 58 |
| `/newsletter/` | `.md` files in `newsletter/` | 11 |
| `/status/` | `status_posts` table | 3 |
| `/archive/` | Old profile pages downloaded from server | — |

## Adding new posts

**Blog or notes:** Re-run `extract_posts.py` (pulls from SQL). To add a new post,
it must be in the SQL dump. For new writing going forward, use the newsletter or
drop a `.md` file (see below).

**Newsletter (Substack imports or new essays):**
1. Create `newsletter/YYYY-MM-DD-slug.md` with frontmatter:
   ```
   ---
   title: "Title here"
   date: 2024-01-15
   description: One-line description
   ---
   
   Body content in markdown...
   ```
2. Run `python3 extract_posts.py`
3. Push

**Images:** Drop into `uploads/YYYY/MM/filename.jpg`. Reference in posts as `/uploads/YYYY/MM/filename.jpg`.

## Key files

- `extract_posts.py` — the entire build system. Parses SQL, reads .md files, writes HTML.
- `style.css` — all styles. Single file, no preprocessor.
- `index.html` — profile/homepage. Hand-written, edit directly.
- `newsletter/*.md` — Substack editions 1–11 (Oct 2020 – Feb 2021) already imported.
- `archive/work/index.html` — old jQuery portfolio (AccuWeather PM work), preserved as-is.
- `static_assets/resume.pdf` — PM resume downloaded from live server.

## SQL tables

The dump has four WordPress installs in one file:

| Prefix | Blog | Notes |
|--------|------|-------|
| `wp_` | Original rkblogs.net (2004–2021) | → `/journal/` |
| `links_` | ravikiran.us main blog (2018–2020) | → `/blog/` + `/notes/` |
| `status_` | status.ravikiran.us (nearly empty) | → `/status/` |
| `wedding_` | wedding blog (2012–2013) | → `/wedding/` |

## SFTP (live server — still running WordPress)

```
Host:     access941206769.webspace-data.io
Port:     22
Protocol: SFTP
User:     u1114753971
```
Password in 1Password / known to owner. Use `fetch_uploads_sftp.py` to pull uploads.

## GitHub Pages

- Repo: `rkrules/ravikiran.us`
- Branch: `main`, path: `/`
- Custom domain: `ravikiran.us` (CNAME file + GitHub Pages setting)
- HTTPS: enable in repo Settings → Pages → "Enforce HTTPS" once cert provisions
- `.nojekyll` file exists — GitHub Pages serves files as-is, no Jekyll processing

## What's gitignored

- `wp_rkblogs_2023_04_04.sql` (70 MB)
- `wp_rkblogs_2023_04_04.zip`
- `uploads/` (152 MB of images — too large for GitHub)
- `.DS_Store`, `__pycache__`

The `uploads/` directory exists locally and on the live server. Images referenced in
posts as `/uploads/...` will only display when served locally with the uploads/ dir
present, or when the site is configured with an image CDN or the uploads are committed.
Consider committing just the dated subdirs that are actually referenced.
