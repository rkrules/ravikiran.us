#!/usr/bin/env python3
"""Generate post-audit.csv for reviewing all posts across sections."""

import os
import csv
import re
from html.parser import HTMLParser


class PostParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.date = ''
        self.word_count = 0
        self.has_images = False
        self._in_h2 = False
        self._in_time = False
        self._in_content = False
        self._content_depth = 0
        self._text_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h2':
            self._in_h2 = True
        elif tag == 'time':
            self._in_time = True
            if 'datetime' in attrs:
                self.date = attrs['datetime'][:10]
        elif tag == 'div' and attrs.get('class') == 'post-content':
            self._in_content = True
            self._content_depth = 1
        elif self._in_content:
            if tag == 'div':
                self._content_depth += 1
            if tag == 'img':
                self.has_images = True

    def handle_endtag(self, tag):
        if tag == 'h2':
            self._in_h2 = False
        elif tag == 'time':
            self._in_time = False
        elif tag == 'div' and self._in_content:
            self._content_depth -= 1
            if self._content_depth <= 0:
                text = ' '.join(self._text_buffer)
                self.word_count = len(text.split())
                self._in_content = False

    def handle_data(self, data):
        if self._in_h2 and not self.title:
            self.title = data.strip()
        if self._in_content:
            self._text_buffer.append(data.strip())


def parse_post(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    parser = PostParser()
    parser.feed(content)
    return {
        'title': parser.title,
        'date': parser.date,
        'word_count': parser.word_count,
        'has_images': 'Y' if parser.has_images else 'N',
    }


SECTIONS = [
    ('newsletter', 'newsletter'),
    ('blog', 'blog'),
    ('notes', 'notes'),
    ('journal', 'journal'),
    ('wedding', 'wedding'),
    ('status', 'status'),
]

RATING_HEADERS = [
    'originality', 'imagery', 'philosophical_depth',
    'structure', 'sentence_control', 'voice',
    'pm_share', 'audience', 'relevance', 'action', 'notes',
]

rows = []
for section_name, directory in SECTIONS:
    if not os.path.isdir(directory):
        continue
    files = sorted(
        f for f in os.listdir(directory)
        if f.endswith('.html') and f != 'index.html'
    )
    for filename in files:
        filepath = os.path.join(directory, filename)
        info = parse_post(filepath)
        rows.append({
            'section': section_name,
            'slug': filename.replace('.html', ''),
            'title': info['title'],
            'date': info['date'],
            'word_count': info['word_count'],
            'has_images': info['has_images'],
            **{h: '' for h in RATING_HEADERS},
        })

output = 'post-audit.csv'
fieldnames = ['section', 'slug', 'title', 'date', 'word_count', 'has_images'] + RATING_HEADERS

with open(output, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

by_section = {}
for r in rows:
    by_section.setdefault(r['section'], 0)
    by_section[r['section']] += 1

print(f"Wrote {output} with {len(rows)} posts:")
for sec, count in by_section.items():
    print(f"  {sec}: {count}")
