#!/usr/bin/env python3
"""Extract WordPress posts from SQL dump and generate static HTML."""

import re
import html
import os
from datetime import datetime
import markdown as md_lib

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


def replace_linkpreview(m):
    raw_url = m.group(1)
    # the url attribute sometimes itself contains a nested <a href="...">...</a>
    inner = re.search(r'href="([^"]+)"', raw_url)
    url = inner.group(1) if inner else raw_url
    return f'<p><a href="{url}">{url}</a></p>'


def clean_wp_content(content):
    content = re.sub(r'\[wplinkpreview url="(.*)"\]', replace_linkpreview, content)
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

        content = md_lib.markdown(content, extensions=['extra', 'smarty'])
        content = content.replace('<img ', '<img loading="lazy" ')

        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or fn.replace('.md', '')
        posts.append({
            'id': fn, 'title': title, 'content': content,
            'date': date_str, 'status': 'publish', 'slug': slug, 'date_obj': date_obj,
        })

    return posts


BODY_CLASSES = {
    'abk':        'abk-page',
    'wedding':    'wedding-page',
    'blog':       'plain-post-page',
    'notes':      'plain-post-page',
    'status':     'plain-post-page',
    'journal':    'plain-post-page',
    'newsletter': 'plain-post-page',
}

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

    body_class = BODY_CLASSES.get(blog_type, '')
    body_tag = f'<body class="{body_class}">' if body_class else '<body>'
    masthead = '' if body_class else '''  <header>
    <div class="container">
      <h1><a href="/">Ravikiran Rajagopal</a></h1>
      <p class="tagline">Product, tech, and life</p>
    </div>
  </header>

'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - Ravikiran Rajagopal</title>
  <link rel="stylesheet" href="/style.css">
</head>
{body_tag}
{masthead}  <main class="container">
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


def generate_index(posts, title, description, show_back=False, note=None, body_class='plain-post-page'):
    items = []
    for p in posts:
        pt = html.escape(p['title'] if p['title'] else 'Untitled')
        ds = p['date_obj'].strftime('%b %d, %Y') if p.get('date_obj') else p.get('date', '')
        href = p['href']
        items.append(f'      <li><a href="{href}"><time>{ds}</time> {pt}</a></li>')

    items_html = "\n".join(items)
    nav = '<p><a href="/" class="nav-home">&larr; Home</a></p>\n      ' if show_back else ''
    note_html = f'<p class="section-note">{html.escape(note)}</p>\n      ' if note else ''
    body_tag = f'<body class="{body_class}">' if body_class else '<body>'
    masthead = '' if body_class else f'''  <header>
    <div class="container">
      <h1><a href="/">Ravikiran Rajagopal</a></h1>
      <p class="tagline">{html.escape(description)}</p>
    </div>
  </header>

'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} - Ravikiran Rajagopal</title>
  <link rel="stylesheet" href="/style.css">
</head>
{body_tag}
{masthead}  <main class="container">
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


# Journal posts tagged with a WordPress review category (Movie Reviews, Book
# Review, Play Review, Movie talk) that read as genuine, public-safe critique
# of the work itself rather than personal/diary content. Curated in
# post-audit.csv (audience=P, action=Keep) after reading all 113 review-tagged
# posts; see fill_ratings.py's REVIEW_RATINGS for the full audit with notes.
REVIEW_SLUGS = {
    # Movies
    'yuva': 'Movies',
    'hum-tum': 'Movies',
    'veer-zaara': 'Movies',
    '7g': 'Movies',
    'aptha-mitra': 'Movies',
    '85': 'Movies',
    'sarkar': 'Movies',
    'sahara': 'Movies',
    'war-of-the-worlds': 'Movies',
    'funtastic-four': 'Movies',
    'holiweek': 'Movies',
    'jogi-a-feel-that-never-ends': 'Movies',
    'iqbal': 'Movies',
    'weekend-movies-2': 'Movies',
    'the-myth': 'Movies',
    'apaharan': 'Movies',
    'india-questions-aamir-khan': 'Movies',
    'rang-de-basanti': 'Movies',
    '9211': 'Movies',
    '%e0%b2%ac%e0%b2%82%e0%b2%97%e0%b2%be%e0%b2%b0%e0%b2%a6-%e0%b2%ae%e0%b2%a8%e0%b3%81%e0%b2%b7%e0%b3%8d%e0%b2%af-%e0%b2%87%e0%b2%a8%e0%b3%8d%e0%b2%a8%e0%b2%bf%e0%b2%b2%e0%b3%8d%e0%b2%b2': 'Movies',
    'being-cyrus-zathura': 'Movies',
    'crash': 'Movies',
    'my-autograph': 'Movies',
    'gangster-a-love-story': 'Movies',
    'fanaa': 'Movies',
    'chup-chup-ke': 'Movies',
    'first-impressions-of-kank': 'Movies',
    'krrish-cyanideomkarasomething-somethingvettaiyaadu': 'Movies',
    'nenapirali': 'Movies',
    'lage-raho-munnabhai': 'Movies',
    'pksedorkkg': 'Movies',
    'dor': 'Movies',
    'woh-lamhe': 'Movies',
    'jote-joteyalikkgdonumrao-jaan': 'Movies',
    'dhoom-2': 'Movies',
    'thank-you-note': 'Movies',
    'movie-mela': 'Movies',
    'guru': 'Movies',
    'united-93': 'Movies',
    'happy-feet': 'Movies',
    'mungaru-male': 'Movies',
    'duniya': 'Movies',
    'vertigo': 'Movies',
    'bheja-fry': 'Movies',
    'just-what-i-wanted-to-say-2': 'Movies',
    'salaam-e-ishq-black-friday-in-pursuit': 'Movies',
    'life-in-a-metro': 'Movies',
    'himesh-shows-signs-of-becoming-rajinikanth': 'Movies',
    'aap-ka-suroor-or-rather-himesh-reshammiyas-topi-2': 'Movies',
    'satyavan-savitri': 'Movies',
    'cheeni-kum': 'Movies',
    'jhoom-barabar-jhoom': 'Movies',
    'honeymoon-travels-pvt-ltd': 'Movies',
    'chak-de': 'Movies',
    'heyy-babyy': 'Movies',
    'manorama-six-feet-under': 'Movies',
    'cinema-halls': 'Movies',
    'jodha-akbar': 'Movies',
    'u-me-aur-hum-2-2': 'Movies',
    'little_miss_sunshine': 'Movies',
    'the_shawshank_redemption': 'Movies',
    'rock-on': 'Movies',
    'sorry-bhai': 'Movies',
    'milkshake_before_sunrise': 'Movies',
    'all-things-inception': 'Movies',
    'movies-in-usa': 'Movies',
    'o-saathi-re': 'Movies',
    'happiness-is-beautiful-birds-singing': 'Movies',
    # Books
    'oxymoronica': 'Books',
    'da-vinci-code': 'Books',
    'who-moved-my-cheese': 'Books',
    'a-life-lived': 'Books',
    'shantaram': 'Books',
    'man-who-knew-infinity-abachurina-post-office-toofan-mail': 'Books',
    'kafkas-metamorphosis': 'Books',
    'atlas-shrugged': 'Books',
    'mini-book-reviews': 'Books',
    'to-kill-a-mocking-bird': 'Books',
    'kane-and-abel-jeffry-archer': 'Books',
    # Plays
    'rangashankara-rehearsal': 'Plays',
    'rangashankara-the-final-rehearsal': 'Plays',
    'iti-ninna-amritha': 'Plays',
    'a-heap-of-broken-images': 'Plays',
    'rangashankara-sleuth': 'Plays',
    'sankranti': 'Plays',
    'all-the-best': 'Plays',
    'hayavadana': 'Plays',
    'rangashankara-sankramana': 'Plays',
    'heegadre-hege': 'Plays',
    'rangashankara-mallinatha-dhyana': 'Plays',
    'rangashankara-maduve-maduve': 'Plays',
    'rangashankara-neenaanaadrenaaneenena': 'Plays',
    'checkmate-rangashankara': 'Plays',
    'common-man': 'Plays',
    'dance_festiva': 'Plays',
    'all-you-need-is-love': 'Plays',
    'sadarame-rangashankara': 'Plays',
}


def generate_reviews_index(journal_posts):
    """Curated index of public-safe movie/book/play reviews, linking to their
    existing /journal/<slug>.html pages (no separate HTML is generated)."""
    by_group = {'Movies': [], 'Books': [], 'Plays': []}
    for p in journal_posts:
        group = REVIEW_SLUGS.get(p['slug'])
        if group:
            by_group[group].append(p)

    sections = []
    for group in ['Movies', 'Books', 'Plays']:
        posts = sorted(by_group[group], key=lambda p: p.get('date', ''), reverse=True)
        items = []
        for p in posts:
            pt = html.escape(p['title'] if p['title'] else 'Untitled')
            ds = p['date_obj'].strftime('%b %d, %Y') if p.get('date_obj') else p.get('date', '')
            items.append(f'        <li><a href="{p["href"]}"><time>{ds}</time> {pt}</a></li>')
        items_html = "\n".join(items)
        sections.append(f'''      <h3>{group}</h3>
      <ul class="post-list">
{items_html}
      </ul>''')

    sections_html = "\n".join(sections)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reviews - Ravikiran Rajagopal</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body class="plain-post-page">
  <main class="container">
    <section>
      <h2>Reviews</h2>
      <p><a href="/" class="nav-home">&larr; Home</a></p>
      <p class="section-note">Movie, book, and play reviews written between 2004 and 2010, pulled out of the journal archive.</p>
{sections_html}
    </section>
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2024 Ravikiran Rajagopal</p>
    </div>
  </footer>
</body>
</html>'''


# Posts excluded from the build entirely (not generated, not indexed) per the
# post-audit.csv "Delete" action. Kept out of the generated site without
# touching the SQL source or post-audit.csv history -- scoped by section since
# slugs like "165" or "movies" are reused across sections.
HIDDEN_SLUGS = {
    ('notes', 'twitter'),  # image-only post; screenshot not committed to uploads/, no text content
}


def hide_deleted(posts, section):
    return [p for p in posts if (section, p['slug']) not in HIDDEN_SLUGS]


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

    main_posts       = hide_deleted(main_posts,       'blog')
    notes_posts      = hide_deleted(notes_posts,      'notes')
    status_posts     = hide_deleted(status_posts,     'status')
    wedding_posts    = hide_deleted(wedding_posts,    'wedding')
    journal_posts    = hide_deleted(journal_posts,    'journal')
    newsletter_posts = hide_deleted(newsletter_posts, 'newsletter')
    abk_posts        = hide_deleted(abk_posts,        'abk')

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
        f.write(generate_index(wedding_posts, 'Wedding', 'Our wedding, 2012–2013', show_back=True, body_class='wedding-page'))

    with open('journal/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            journal_posts, 'Journal', 'Personal writing, 2004–2021', show_back=True,
            note='Personal writing from 2004 to 2021. Unpolished, unfiltered. '
                 'Movie, book, and play reviews have been pulled out into a dedicated Reviews page.'
        ))

    os.makedirs('reviews', exist_ok=True)
    with open('reviews/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_reviews_index(journal_posts))

    with open('newsletter/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            newsletter_posts, 'Newsletter', 'Occasional writing on product, tech, and life',
            show_back=True,
            note='Occasional longer essays. More coming soon.' if not newsletter_posts else None
        ))

    with open('abk/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_index(
            abk_posts, 'ABK', 'Family stories and memories',
            show_back=True, body_class='abk-page',
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
