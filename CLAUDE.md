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
| `/abk/` | `.md` files in `abk/` | growing |
| `/status/` | `status_posts` table | 3 |
| `/archive/` | Old profile pages downloaded from server | — |

## How to publish a new post

### Newsletter or ABK (the two active writing sections)

Both work identically. Pick the right folder:
- **`newsletter/`** — essays, longer writing, ideas
- **`abk/`** — family memories, photo essays

**Step 1: Create the file**

```
YYYY-MM-DD-slug.md
```

With this frontmatter at the top:

```
---
title: "Your title here"
date: 2024-01-15
description: One-line description (shown in index)
---

Your content here. Full markdown supported:

## Headings work

**Bold**, *italic*, [links](https://example.com)

| Tables | work |
|--------|------|
| yes    | they do |

![Image caption](/uploads/tooth-fairy/one.jpg)
```

**Step 2: Add images (if any)**

For a photo-heavy post, process images before committing:

```bash
# Convert HEIC to JPEG (iPhone photos)
sips -s format jpeg photo.HEIC --out photo.jpg

# Resize to 1200px max (web-appropriate)
sips -Z 1200 photo.jpg --out uploads/tooth-fairy/photo.jpg
```

Put processed images in `uploads/SLUG-NAME/` and reference as `/uploads/SLUG-NAME/photo.jpg`.
Images in `uploads/` are committed to git (not gitignored at the subfolder level).

**Step 3: Build and push**

```bash
python3 extract_posts.py
git add -A
git commit -m "Add post: your title"
git push
```

Site is live at ravikiran.us within ~60 seconds of push.

**Step 4: Preview locally (optional)**

```bash
python3 -m http.server 8000
# open http://localhost:8000/abk/ or /newsletter/
```

Note: local images in `uploads/` display locally. On GitHub Pages they serve from the committed files.

### Adding a new section (beyond newsletter/abk)

1. Create the directory (e.g., `photos/`)
2. In `extract_posts.py`: add `read_md_posts('photos')`, wire it into `main()`, add to `links` dict in `generate_html()`, write index
3. Add `.gitignore` in the new dir to exclude raw/large source files if needed

## Key files

- `extract_posts.py` — the entire build system. Parses SQL, reads .md files, writes HTML. Uses Python `markdown` library (`pip install markdown`) for `.md` → HTML conversion.
- `style.css` — all styles. Single file, no preprocessor.
- `index.html` — profile/homepage. Hand-written, edit directly.
- `newsletter/*.md` — Substack editions 1–11 (Oct 2020 – Feb 2021) already imported.
- `abk/*.md` — family stories and photo essays. First post: tooth fairy (Sept 2024–May 2026).
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
- `.DS_Store`, `__pycache__`

`uploads/` is **not** globally gitignored — subdirectories are committed selectively.
The bulk historical uploads (150MB+) are not committed. New post images go into a named
subfolder (`uploads/tooth-fairy/`, etc.) and are committed normally.

Raw source images (originals, HEICs) in `abk/` are gitignored via `abk/.gitignore`.
Only the processed copies in `uploads/` go into the repo.
