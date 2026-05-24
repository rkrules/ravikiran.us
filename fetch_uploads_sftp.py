#!/usr/bin/env python3
"""Fetch wp-content/uploads via SFTP and rewrite local HTML links to /uploads/.

Usage:
  SFTP_PASSWORD='pw' python3 fetch_uploads_sftp.py host [port] [username]

The script will attempt to locate the remote wp-content/uploads directory under
common webroot locations and download it to ./uploads/. After download it will
rewrite generated HTML files (posts/, wedding/, status/ and index.html) to
point to local /uploads/ paths.
"""

import os
import sys
import posixpath
from stat import S_ISDIR
import re

try:
    import paramiko
except Exception as e:
    print('paramiko is required. Please run: python3 -m pip install --user paramiko')
    raise


def sftp_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except IOError:
        return False


def find_remote_uploads(sftp):
    # Start from the SFTP current working directory (fall back to '/')
    try:
        cwd = sftp.getcwd()
    except Exception:
        cwd = None
    if not cwd:
        cwd = '/'
    candidates = [cwd,
                  posixpath.join(cwd, 'public_html'),
                  posixpath.join(cwd, 'www'),
                  posixpath.join(cwd, 'htdocs'),
                  posixpath.join(cwd, 'httpdocs'),
                  posixpath.join(cwd, 'html'),
                  posixpath.join(cwd, 'site'),
                  posixpath.join(cwd, 'site/wwwroot'),
                  '/var/www/html',
                  '/home']

    # Also include top-level directories in cwd
    try:
        for a in sftp.listdir_attr(cwd):
            if S_ISDIR(a.st_mode):
                candidates.append(posixpath.join(cwd, a.filename))
    except Exception:
        pass

    # Normalize and uniq
    seen = set()
    candidates2 = []
    for c in candidates:
        if not c:
            continue
        norm = posixpath.normpath(c)
        if norm in seen:
            continue
        seen.add(norm)
        candidates2.append(norm)

    for base in candidates2:
        check = posixpath.join(base, 'wp-content', 'uploads')
        if sftp_exists(sftp, check):
            return check

    # Last resort: check directly at 'wp-content/uploads' relative to cwd
    if sftp_exists(sftp, posixpath.join(cwd, 'wp-content', 'uploads')):
        return posixpath.join(cwd, 'wp-content', 'uploads')

    return None


def download_dir(sftp, remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    for entry in sftp.listdir_attr(remote_dir):
        rpath = posixpath.join(remote_dir, entry.filename)
        lpath = os.path.join(local_dir, entry.filename)
        if S_ISDIR(entry.st_mode):
            download_dir(sftp, rpath, lpath)
        else:
            # skip if file exists and same size
            try:
                rsize = entry.st_size
            except Exception:
                rsize = None
            if os.path.exists(lpath) and rsize is not None and os.path.getsize(lpath) == rsize:
                print('skip', rpath)
                continue
            print('get', rpath, '->', lpath)
            try:
                ensure_local_dir(lpath)
                sftp.get(rpath, lpath)
            except Exception as e:
                print('ERROR downloading', rpath, e)


def ensure_local_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def rewrite_html_links(root='.'):
    # Replace URLs that reference wp-content/uploads or ravikiran.us/.../wp-content/uploads
    patterns = [
        re.compile(r'https?://[^\s"\']*?/wp-content/uploads/([\w\-./%]+)'),
        re.compile(r'/wp-content/uploads/([\w\-./%]+)')
    ]

    files = []
    for sub in ['posts', 'wedding', 'status']:
        if os.path.isdir(sub):
            for fn in os.listdir(sub):
                if fn.endswith('.html'):
                    files.append(os.path.join(sub, fn))
    files.append('index.html')
    files.append('status/index.html')
    files.append('wedding/index.html')

    files = [f for f in files if f and os.path.exists(f)]

    changed = 0
    for path in files:
        s = open(path, 'r', encoding='utf-8').read()
        orig = s
        for pat in patterns:
            s = pat.sub(r'/uploads/\1', s)
        if s != orig:
            open(path, 'w', encoding='utf-8').write(s)
            changed += 1
            print('rewrote', path)
    print('rewrote files:', changed)


def main():
    if len(sys.argv) < 2:
        print('usage: SFTP_PASSWORD=... python3 fetch_uploads_sftp.py host [port] [username]')
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 22
    username = sys.argv[3] if len(sys.argv) > 3 else None
    password = os.environ.get('SFTP_PASSWORD')
    if not password:
        print('Set SFTP_PASSWORD environment variable with the account password')
        sys.exit(1)
    if not username:
        print('username required as third argument')
        sys.exit(1)

    print('connecting to', host, 'port', port, 'user', username)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=username, password=password, timeout=20)
    except Exception as e:
        print('SSH connect failed:', e)
        sys.exit(1)

    sftp = client.open_sftp()
    try:
        print('finding remote uploads directory...')
        uploads_remote = find_remote_uploads(sftp)
        if not uploads_remote:
            print('Could not find wp-content/uploads on server. Checked common locations.')
            sftp.close()
            client.close()
            sys.exit(1)
        print('remote uploads dir:', uploads_remote)

        download_dir(sftp, uploads_remote, 'uploads')

        print('download complete; rewriting HTML to point to /uploads/')
        rewrite_html_links()

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass

    print('done')


if __name__ == '__main__':
    main()
