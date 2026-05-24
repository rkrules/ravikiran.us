#!/usr/bin/env python3
"""Reconstruct wp-content/uploads/ from SQL dump by downloading attachment GUIDs.

This script:
- Parses prefix_postmeta for meta_key='_wp_attached_file' to get relative paths
- Parses prefix_posts for post_type='attachment' to get GUIDs
- Attempts to download each file to uploads/<relative_path>

It writes uploads/ files and uploads-manifest.json with success/failure info.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

SQL_FILE = 'wp_rkblogs_2023_04_04.sql'
UPLOAD_ROOT = 'uploads'
PREFIXES = ['links', 'status', 'wedding']
MAX_WORKERS = 8
TIMEOUT = 30


def iter_insert_rows(sql_text, table):
    """Yield each row's inner text for INSERT INTO `table` VALUES (...),(...);"""
    needle = f"INSERT INTO `{table}` VALUES"
    pos = 0
    while True:
        idx = sql_text.find(needle, pos)
        if idx == -1:
            return
        # find first '(' after VALUES
        i = sql_text.find('(', idx)
        if i == -1:
            pos = idx + 1
            continue
        j = i
        rows = []
        depth = 0
        in_string = False
        escape = False
        start = i
        while j < len(sql_text):
            ch = sql_text[j]
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_string = not in_string
            elif not in_string:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        row = sql_text[start+1:j]
                        rows.append(row)
                        # find next non-space char
                        k = j + 1
                        while k < len(sql_text) and sql_text[k].isspace():
                            k += 1
                        if k < len(sql_text) and sql_text[k] == ',':
                            # more rows in this INSERT; find next '(' and continue
                            start = sql_text.find('(', k)
                            if start == -1:
                                pos = j + 1
                                break
                            j = start
                            depth = 0
                            in_string = False
                            escape = False
                            continue
                        else:
                            pos = j + 1
                            break
            j += 1
        for r in rows:
            yield r
        pos = j + 1


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


def unq(val):
    v = val.strip()
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    return v


def build_attachment_maps(sql_text):
    # map (prefix, post_id) -> relative path
    attached = {}
    # map (prefix, post_id) -> guid
    guid_map = {}

    # postmeta: (meta_id, post_id, meta_key, meta_value)
    for prefix in PREFIXES:
        table = f"{prefix}_postmeta"
        for row in iter_insert_rows(sql_text, table):
            fields = parse_row_fields(row)
            if len(fields) < 4:
                continue
            meta_id = unq(fields[0])
            post_id = unq(fields[1])
            meta_key = unq(fields[2])
            meta_value = unq(fields[3])
            if meta_key == '_wp_attached_file' and meta_value:
                attached[(prefix, post_id)] = meta_value

    # posts: capture attachment guid for posts with post_type == 'attachment'
    for prefix in PREFIXES:
        table = f"{prefix}_posts"
        for row in iter_insert_rows(sql_text, table):
            fields = parse_row_fields(row)
            if len(fields) < 21:
                continue
            post_id = unq(fields[0])
            guid = unq(fields[18]) if len(fields) > 18 else ''
            post_type = unq(fields[20]) if len(fields) > 20 else ''
            if post_type == 'attachment':
                guid_map[(prefix, post_id)] = guid

    return attached, guid_map


def ensure_dir_for(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def download_file(url, dest_path):
    headers = {'User-Agent': 'upload-reconstructor/1.0'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
            ensure_dir_for(dest_path)
            with open(dest_path, 'wb') as f:
                f.write(data)
        return True, len(data)
    except urllib.error.HTTPError as e:
        return False, f'HTTPError {e.code}'
    except urllib.error.URLError as e:
        return False, f'URLError {e.reason}'
    except Exception as e:
        return False, str(e)


def reconstruct():
    print('Reading SQL...')
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_text = f.read()

    attached, guid_map = build_attachment_maps(sql_text)
    print(f'Found {len(attached)} _wp_attached_file entries and {len(guid_map)} attachment posts')

    # build list of unique download tasks
    tasks = {}
    default_site = 'http://ravikiran.us'
    for (prefix, post_id), relpath in attached.items():
        # prefer GUID if available
        guid = guid_map.get((prefix, post_id), '')
        url = ''
        if guid and (guid.startswith('http://') or guid.startswith('https://')):
            url = guid
        else:
            # construct fallback
            url = default_site.rstrip('/') + '/wp-content/uploads/' + relpath.lstrip('/')
        dest = os.path.join(UPLOAD_ROOT, relpath.replace('..', '').lstrip('/'))
        tasks[(prefix, post_id, relpath)] = {'url': url, 'dest': dest}

    print(f'Prepared {len(tasks)} unique file tasks')

    manifest = {'total': len(tasks), 'succeeded': [], 'failed': []}

    # download in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_map = {}
        for key, info in tasks.items():
            dest = info['dest']
            url = info['url']
            # skip file if exists
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                manifest['succeeded'].append({'key': key, 'url': url, 'dest': dest, 'size': os.path.getsize(dest), 'skipped': True})
                continue
            future = ex.submit(download_file, url, dest)
            future_map[future] = (key, url, dest)

        for fut in as_completed(future_map):
            key, url, dest = future_map[fut]
            try:
                ok, info = fut.result()
            except Exception as e:
                ok = False
                info = str(e)
            if ok:
                size = info
                manifest['succeeded'].append({'key': key, 'url': url, 'dest': dest, 'size': size})
                print(f'OK: {url} -> {dest} ({size} bytes)')
            else:
                manifest['failed'].append({'key': key, 'url': url, 'dest': dest, 'error': info})
                print(f'FAIL: {url} -> {dest} ({info})')

    # write manifest
    with open('uploads-manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print('Done. Manifest written to uploads-manifest.json')


if __name__ == '__main__':
    reconstruct()
