#!/usr/bin/env python3
"""Extract WordPress posts from SQL dump and generate static HTML."""

import re
import html
import os
from datetime import datetime

SQL_FILE = "wp_rkblogs_2023_04_04.sql"


def slugify(title, post_name, post_id):
    if post_name and post_name not in ('', 'autosave', 'revision', 'draft'):
        return post_name
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug if slug else f"post-{post_id}"


def unescape_sql(val):
    val = val.replace("\\'", "'").replace('\\"', '"')
    val = val.replace("\\n", "\n").replace("\\r", "").replace("\\t", "\t")
    val = val.replace("\\\\", "\\")
    return val


def clean_wp_content(content):
    content = re.sub(r'<!--\s*/?(?:wp|/)?.+?-->\s*', '', content)
    content = re.sub(r'https?://[^\s"\']*?/wp-content/uploads/', '/uploads/', content)
    content = re.sub(r'/wp-content/uploads/', '/uploads/', content)
    content = re.sub(r'\[[a-zA-Z_][\w\-]*[^\]]*\]', '', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = html.unescape(content)
    return content.strip()


def parse_row_fields(row_text):
    fields = []
    current = []
    in_string = False
    escape = False

    for ch in row_text:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == '\\':
            current.append(ch)
            escape = True
            continue
        if ch == "'" and not escape:
            in_string = not in_string
            current.append(ch)
            continue
        if ch == ',' and not in_string:
            fields.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)

    if current:
        fields.append(''.join(current).strip())

    return fields


def parse_aside_ids(sql_text):
    """Return set of links post IDs tagged as post-format-aside."""
    aside_term_tax_ids = set()
    for m in re.finditer(
        r"INSERT INTO `links_term_taxonomy` VALUES \((\d+), (\d+), 'post_format'[^\n]+\);",
        sql_text
    ):
        term_tax_id, term_id = m.group(1), m.group(2)
        name_m = re.search(
            rf"INSERT INTO `links_terms` VALUES \({term_id}, '[^']*', '([^']*)'",
            sql_text
        )
        if name_m and 'aside' in name_m.group(1):
            aside_term_tax_ids.add(term_tax_id)

    aside_post_ids = set()
    for m in re.finditer(
        r"INSERT INTO `links_term_relationships` VALUES \((\d+), (\d+),",
        sql_text
    ):
        post_id, term_tax_id = m.group(1), m.group(2)
        if term_tax_id in aside_term_tax_ids:
            aside_post_ids.add(post_id)

    return aside_post_ids


def parse_wp_categories(sql_text):
    """Return dict of wp post_id -> list of category names."""
    tax_to_term = {}
    for m in re.finditer(
        r"INSERT INTO `wp_term_taxonomy` VALUES \((\d+), (\d+), 'category'",
        sql_text
    ):
        tax_to_term[m.group(1)] = m.group(2)

    term_names = {}
    for m in re.finditer(
        r"INSERT INTO `wp_terms` VALUES \((\d+), '([^']*)'",
        sql_text
    ):
        term_names[m.group(1)] = html.unescape(unescape_sql(m.group(2)))

    post_cats = {}
    for m in re.finditer(
        r"INSERT INTO `wp_term_relationships` VALUES \((\d+), (\d+),",
        sql_text
    ):
        post_id, tax_id = m.group(1), m.group(2)
        if tax_id in tax_to_term:
            term_id = tax_to_term[tax_id]
            if term_id in term_names:
                post_cats.setdefault(post_id, []).append(term_names[term_id])

    return post_cats


def extract_posts(sql_text, prefix, aside_ids=None):
    """Extract posts. Returns (blog_posts, notes_posts); notes only populated when aside_ids given."""
    table = f"{prefix}_posts"
    print(f"  Parsing {table}...", end=' ')

    pattern = re.compile(
        rf"INSERT INTO `{re.escape(table)}` VALUES\s*\((.*?)\)\s*;",
        re.DOTALL
    )

    blog_posts = []
    notes_posts = []

    for match in pattern.finditer(sql_text):
        row_text = match.group(1)
        fields = parse_row_fields(row_text)

        if len(fields) < 21:
            continue

        def unq(val):
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            return val

        post_id    = unq(fields[0])
        post_date  = unq(fields[2])
        post_content = unescape_sql(unq(fields[4]))
        post_title = html.unescape(unescape_sql(unq(fields[5])))
        post_status = unq(fields[7])
        post_name  = unq(fields[11])
        post_type  = unq(fields[20])

        if post_status not in ('publish', 'draft'):
            continue
        if post_type not in ('post', 'page'):
            continue

        date_obj = None
        if post_date and post_date != '0000-00-00 00:00:00':
            try:
                date_obj = datetime.strptime(post_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        post = {
            'id': post_id,
            'title': post_title,
            'content': post_content,
            'date': post_date,
            'status': post_status,
            'slug': slugify(post_title, post_name, post_id),
            'date_obj': date_obj,
        }

        if aside_ids is not None and post_id in aside_ids:
            notes_posts.append(post)
        else:
            blog_posts.append(post)

    print(f"{len(blog_posts)} posts, {len(notes_posts)} notes")
    return blog_posts, notes_posts


def extract_wp_posts(sql_text, categories):
    """Extract journal posts from wp_posts (private/draft/publish), with categories."""
    table = 'wp_posts'
    print(f"  Parsing {table}...", end=' ')

    pattern = re.compile(
        rf"INSERT INTO `{re.escape(table)}` VALUES\s*\((.*?)\)\s*;",
        re.DOTALL
    )

    posts = []
    seen_slugs = {}

    for match in pattern.finditer(sql_text):
        row_text = match.group(1)
        fields = parse_row_fields(row_text)

        if len(fields) < 21:
            continue

        def unq(val):
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            return val

        post_id      = unq(fields[0])
        post_date    = unq(fields[2])
        post_content = unescape_sql(unq(fields[4]))
        post_title   = html.unescape(unescape_sql(unq(fields[5])))
        post_status  = unq(fields[7])
        post_name    = unq(fields[11])
        post_type    = unq(fields[20])

        if post_date == '0000-00-00 00:00:00':
            continue
        if post_status not in ('publish', 'private', 'draft'):
            continue
        if post_type not in ('post', 'page'):
            continue

        date_obj = None
        if post_date:
            try:
                date_obj = datetime.strptime(post_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        slug = slugify(post_title, post_name, post_id)
        if slug in seen_slugs:
            slug = f"{slug}-{post_id}"
        seen_slugs[slug] = True

        posts.append({
            'id': post_id,
            'title': post_title,
            'content': post_content,
            'date': post_date,
            'status': post_status,
            'slug': slug,
            'date_obj': date_obj,
            'categories': categories.get(post_id, []),
        })

    print(f"{len(posts)} journal posts found")
    return posts


def read_md_posts(directory):
    """Read .md files from a directory and return as post dicts."""
    posts = []
    if not os.path.isdir(directory):
        return posts

    for fn in sorted(os.listdir(directory)):
        if not fn.endswith('.md'):
            continue
        with open(os.path.join(directory, fn), 'r', encoding='utf-8') as f:
            content = f.read()

        title, date_str = fn.replace('.md', ''), ''
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if line.startswith('title:'):
                        title = line.split(':', 1)[1].strip().strip('"\'')
                    elif line.startswith('date:'):
                        date_str = line.split(':', 1)[1].strip()
                content = parts[2].strip()

        date_obj = None
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
            try:
                date_obj = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                pass

        # Basic markdown → HTML
        content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
        content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" loading="lazy">', content)
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)
        paras = [p.strip() for p in content.split('\n\n') if p.strip()]
        content = '\n'.join(
            f'<p>{p}</p>' if not p.startswith('<') else p for p in paras
        )

        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or fn.replace('.md', '')
        posts.append({
            'id': fn, 'title': title, 'content': content,
            'date': date_str, 'status': 'publish', 'slug': slug, 'date_obj': date_obj,
        })

    return posts


def generate_html(post, blog_type='main'):
    title = html.escape(post['title'] if post['title'] else 'Untitled')
    content = clean_wp_content(post['content'])
    dt = post.get('date_obj')
    date_str = dt.strftime('%B %d, %Y') if dt else ''
    year = dt.strftime('%Y') if dt else '2024'

    links = {
        'status':     ('/status/', 'Status Updates'),
        'wedding':    ('/wedding/', 'Wedding'),
        'notes':      ('/notes/', 'Notes'),
        'journal':    ('/journal/', 'Journal'),
        'newsletter': ('/newsletter/', 'Newsletter'),
        'abk':        ('/abk/', 'ABK'),
    }
    back_link, section = links.get(blog_type, ('/blog/', 'Blog'))

    cats = post.get('categories', [])
    cats_html = ''
    if cats:
        tags = ' '.join(f'<span class="tag">{html.escape(c)}</span>' for c in cats)
        cats_html = f'\n      <div class="post-tags">{tags}</div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - Ravikiran Rajagopal</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <div class="container">
      <h1><a href="/">Ravikiran Rajagopal</a></h1>
      <p class="tagline">Product, tech, and life</p>
    </div>
  </header>

  <main class="container">
    <article>
      <header class="post-header">
        <h2>{title}</h2>
        <time datetime="{post['date']}">{date_str}</time>{cats_html}
      </header>
      <div class="post-content">
{content}
      </div>
      <nav class="post-nav">
        <a href="{back_link}">&larr; Back to {section}</a>
      </nav>
    </article>
  </main>

  <footer>
    <div class="container">
      <p>&copy; {year} Ravikiran Rajagopal</p>
    </div>
  </footer>
</body>
</html>'''


def generate_index(posts, title, description, show_back=False, note=None):
    items = []
    for p in posts:
        pt = html.escape(p['title'] if p['title'] else 'Untitled')
        ds = p['date_obj'].strftime('%b %d, %Y') if p.get('date_obj') else p.get('date', '')
        href = p['href']
        items.append(f'      <li><a href="{href}"><time>{ds}</time> {pt}</a></li>')

    items_html = "\n".join(items)
    nav = '<p><a href="/" class="nav-home">&larr; Home</a></p>\n      ' if show_back else ''
    note_html = f'<p class="section-note">{html.escape(note)}</p>\n      ' if note else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} - Ravikiran Rajagopal</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <div class="container">
      <h1><a href="/">Ravikiran Rajagopal</a></h1>
      <p class="tagline">{html.escape(description)}</p>
    </div>
  </header>

  <main class="container">
    <section>
      <h2>{html.escape(title)}</h2>
      {nav}{note_html}<ul class="post-list">
{items_html}
      </ul>
    </section>
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2024 Ravikiran Rajagopal</p>
    </div>
  </footer>
</body>
</html>'''


def main():
    print("Reading SQL file...")
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_text = f.read()

    print("\nParsing post-format-aside IDs...")
    aside_ids = parse_aside_ids(sql_text)
    print(f"  {len(aside_ids)} aside posts")

    print("\nParsing wp_posts categories...")
    wp_cats = parse_wp_categories(sql_text)

    print("\nExtracting main blog + notes (links)...")
    main_posts, notes_posts = extract_posts(sql_text, 'links', aside_ids)

    print("\nExtracting status blog...")
    status_posts, _ = extract_posts(sql_text, 'status')

    print("\nExtracting wedding blog...")
    wedding_posts, _ = extract_posts(sql_text, 'wedding')

    print("\nExtracting journal (wp_posts)...")
    journal_posts = extract_wp_posts(sql_text, wp_cats)

    print("\nReading newsletter .md files...")
    newsletter_posts = read_md_posts('newsletter')
    print(f"  {len(newsletter_posts)} newsletter posts")

    print("\nReading ABK .md files...")
    abk_posts = read_md_posts('abk')
    print(f"  {len(abk_posts)} ABK posts")

    for lst in [main_posts, notes_posts, status_posts, wedding_posts, journal_posts, newsletter_posts, abk_posts]:
        lst.sort(key=lambda p: p.get('date', ''), reverse=True)

    for d in ['blog', 'notes', 'status', 'wedding', 'journal', 'newsletter', 'abk']:
        os.makedirs(d, exist_ok=True)

    print("\nGenerating HTML pages...")

    def write_section(posts, directory, blog_type):
        slugs_seen = {}
        for post in posts:
            slug = post['slug']
            if slug in slugs_seen:
                slug = f"{slug}-{post['id']}"
            slugs_seen[slug] = True
            post['slug'] = slug
            filepath = f"{directory}/{slug}.html"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(generate_html(post, blog_type))
            post['href'] = f"/{directory}/{slug}.html"

    write_section(main_posts,       'blog',       'main')
    write_section(notes_posts,      'notes',      'notes')
    write_section(status_posts,     'status',     'status')
    write_section(wedding_posts,    'wedding',    'wedding')
    write_section(journal_posts,    'journal',    'journal')
    write_section(newsletter_posts, 'newsletter', 'newsletter')
    write_section(abk_posts,       'abk',        'abk')

    with open('blog/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(main_posts, 'Blog', 'Writing on product, tech, and life', show_back=True))

    with open('notes/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(notes_posts, 'Notes', 'Short links and thoughts', show_back=True))

    with open('status/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(status_posts, 'Status Updates', 'Short thoughts and links', show_back=True))

    with open('wedding/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(wedding_posts, 'Wedding', 'Our wedding, 2012–2013', show_back=True))

    with open('journal/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            journal_posts, 'Journal', 'Personal writing, 2004–2021', show_back=True,
            note='Personal writing from 2004 to 2021. Unpolished, unfiltered.'
        ))

    with open('newsletter/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            newsletter_posts, 'Newsletter', 'Occasional writing on product, tech, and life',
            show_back=True,
            note='Occasional longer essays. More coming soon.' if not newsletter_posts else None
        ))

    with open('abk/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            abk_posts, 'ABK', 'Family stories and memories',
            show_back=True,
        ))

    print(f"\nDone!")
    print(f"  Blog:       {len(main_posts):>4} posts  → /blog/")
    print(f"  Notes:      {len(notes_posts):>4} posts  → /notes/")
    print(f"  Status:     {len(status_posts):>4} posts  → /status/")
    print(f"  Wedding:    {len(wedding_posts):>4} posts  → /wedding/")
    print(f"  Journal:    {len(journal_posts):>4} posts  → /journal/")
    print(f"  Newsletter: {len(newsletter_posts):>4} posts  → /newsletter/")
    print(f"  ABK:        {len(abk_posts):>4} posts  → /abk/")


if __name__ == '__main__':
    main()
