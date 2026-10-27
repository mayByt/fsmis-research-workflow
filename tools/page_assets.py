"""Durable fulltext, disposable page cache, and link-preserving legacy migration."""
import datetime
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
import zipfile
from contextlib import contextmanager, nullcontext
from pathlib import Path

POLICY = 'on_demand'
AUTO_IMAGE = re.compile(r'^!\[PDF 第 (\d+) 页\]\(images/([A-Z0-9]{8})/(page-\d{3,}\.png)\)\n?', re.M)

@contextmanager
def asset_lock(w, v):
    lock = w.inside(v, '_staging/locks/page-assets.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f'Page asset operation or stale lock exists: {lock}; inspect before removing')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()

def page_numbers(spec, count):
    result = set()
    for part in spec.split(','):
        if not re.fullmatch(r'\d+(?:-\d+)?', part):
            raise ValueError('Pages must be physical PDF pages, e.g. 2,4-6')
        bounds = [int(x) for x in part.split('-')]
        lo, hi = bounds[0], bounds[-1]
        if not 1 <= lo <= hi <= count:
            raise ValueError(f'Page range outside 1..{count}')
        result.update(range(lo, hi + 1))
    return sorted(result)

def fulltext(w, v, k):
    note = w.find_note(v, w.key(k))
    if not note:
        raise ValueError('Ingest paper first')
    nd, _ = w.split(note.read_text(encoding='utf-8'))
    ft = w.inside(v, nd['fulltext_path'])
    if not ft.is_relative_to((v / '03fulltext').resolve()):
        raise ValueError('Noncanonical fulltext path')
    fd, body = w.split(ft.read_text(encoding='utf-8'))
    for field in ['zotero_key', 'pdf_key', 'note_path', 'fulltext_path']:
        if fd.get(field) != nd.get(field):
            raise ValueError('Fulltext identity mismatch: ' + field)
    return ft, fd, body

def digest(fd):
    value = fd.get('source_sha256', '')
    if not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Missing or invalid source PDF SHA-256')
    return value

def cache_path(w, v, fd, page):
    return w.inside(v, f'_staging/page-cache/{w.key(fd["zotero_key"])}/{digest(fd)}/page-{page:03}.png')

def image_path(w, v, ft, k, page):
    return w.inside(v, str((ft.resolve().parent / 'images' / w.key(k) / f'page-{page:03}.png').relative_to(v.resolve())))

def png_targets(text):
    # Both embeds and ordinary links protect assets. Ignore fenced examples only
    # conservatively: an example may still be a link the user intends to use.
    values = re.findall(r'\[\[([^\]\n]+)\]\]', text)
    values += re.findall(r'\]\(\s*(<[^>]+>|[^\n)]+)\)', text)
    values += re.findall(r'(?:src|href)=[\"\']([^\"\']+)[\"\']', text, re.I)
    for raw in values:
        raw = raw.split('|', 1)[0].strip()
        if raw.startswith('<'):
            raw = raw[1:raw.index('>')]
        else:
            raw = re.sub(r'\s+[\"\'].*$', '', raw)
        raw = urllib.parse.unquote(raw.split('#', 1)[0].split('?', 1)[0])
        if raw.lower().endswith('.png') and not urllib.parse.urlsplit(raw).scheme:
            yield raw

def resolve_targets(v, source, raw, candidates):
    # Obsidian supports Vault paths, relative paths, and short filenames.
    exact = {(source.parent / raw).resolve(), (v / raw.lstrip('/')).resolve()}
    if Path(raw).is_absolute():
        exact.add(Path(raw).resolve())
    hits = candidates & exact
    if hits:
        return hits
    return {p for p in candidates if p.as_posix().endswith('/' + raw.lstrip('./'))}

def referenced(w, v, candidates, replacements=None):
    candidates = {p.resolve() for p in candidates}
    found = set()
    replacements = replacements or {}
    for note in v.rglob('*.md'):
        rel = note.relative_to(v)
        if any(x.startswith('.') for x in rel.parts) or rel.parts[0] == '_staging':
            continue
        text = replacements.get(note, note.read_text(encoding='utf-8'))
        for raw in png_targets(text):
            found.update(resolve_targets(v, note, raw, candidates))
    return found

def validate_assets(w, v, ft, fd, body):
    n = fd.get('page_count')
    if type(n) is not int or n < 1:
        raise ValueError('Invalid page_count')
    numbered = [int(x) for x in re.findall(r'^## PDF 第 (\d+) 页$', body, re.M)]
    if numbered != list(range(1, n + 1)):
        raise ValueError('全文缺页/重复页/页序不符')
    policy = fd.get('image_policy')
    if policy not in (None, POLICY):
        raise ValueError('Unknown image_policy')
    if policy is None:
        images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', body)
        if len(images) != n:
            raise ValueError('Legacy 页面图像数量不符；请先迁移')
    else:
        digest(fd)
        retained = fd.get('retained_pages', [])
        if not isinstance(retained, list) or any(type(p) is not int or not 1 <= p <= n for p in retained) or len(set(retained)) != len(retained):
            raise ValueError('Invalid retained_pages')
        for p in retained:
            if not image_path(w, v, ft, fd['zotero_key'], p).is_file():
                raise ValueError(f'精选图缺失: page-{p:03}.png')
    # Actual links are durable; transient cache absence itself is never a failure.
    check_links(w, v, ft, body)

def check_links(w, v, source, body):
    for raw in png_targets(body):
        exact = [(source.parent / raw).resolve(), (v / raw.lstrip('/')).resolve()]
        if any(p.is_relative_to(v.resolve()) and p.is_file() for p in exact):
            continue
        matches = [p for p in v.rglob(Path(raw).name) if p.is_file() and p.as_posix().endswith('/' + raw.lstrip('./'))]
        if not matches:
            raise ValueError(f'图片链接缺失/越界: {raw}')

def render(w, v, k, spec, keep=False):
    v = v.resolve()
    with asset_lock(w, v):
        ft, fd, body = fulltext(w, v, k)
        selected = page_numbers(spec, fd['page_count'])
        # Always verify the current Zotero attachment; stale cache never conceals
        # changed PDF identity/content. Host approval is handled outside Python.
        info = w.inspect(k, fd['pdf_key'])
        pdf = Path(info['pdf_path'])
        if info['attachment']['key'] != fd['pdf_key'] or w.sha(pdf) != digest(fd):
            raise ValueError('PDF identity/content changed; review before rendering')
        if keep and fd.get('image_policy') != POLICY:
            raise ValueError('Run migrate-images --apply before selecting legacy pages')
        import pypdfium2 as pdfium
        result = []
        with pdfium.PdfDocument(str(pdf)) as document:
            if len(document) != fd['page_count']:
                raise ValueError('PDF page count changed')
            original_hash = w.sha(ft)
            retained = set(fd.get('retained_pages', []))
            for number in selected:
                durable = image_path(w, v, ft, k, number)
                cached = cache_path(w, v, fd, number)
                target = durable if keep else cached
                if durable.is_file():
                    target = durable
                elif not target.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if keep and cached.is_file():
                        shutil.copy2(cached, target)
                    else:
                        handle, temporary = tempfile.mkstemp(dir=target.parent, suffix='.png')
                        os.close(handle)
                        try:
                            page = document[number - 1]
                            try:
                                bitmap = page.render(scale=1.5)
                                try:
                                    bitmap.to_pil().save(temporary)
                                finally:
                                    bitmap.close()
                            finally:
                                page.close()
                            os.replace(temporary, target)
                        finally:
                            if os.path.exists(temporary):
                                os.unlink(temporary)
                if target == cached:
                    os.utime(target, None)  # TTL follows last cache use.
                if keep:
                    retained.add(number)
                    rel = f'images/{k}/page-{number:03}.png'
                    if rel not in body:
                        body += f'\n![精选 PDF 第 {number} 页]({rel})\n'
                result.append({'page': number, 'path': str(target), 'retained': target == durable})
            if keep:
                fd['retained_pages'] = sorted(retained)
                w.atomic(ft, w.doc(fd, body), expected=original_hash)
                # Only remove duplicate cache bytes once the durable link is saved.
                caches = [cache_path(w, v, fd, number) for number in selected]
                linked = referenced(w, v, caches)
                for cached in caches:
                    if cached.resolve() not in linked:
                        cached.unlink(missing_ok=True)
        return {'state': 'RENDERED', 'pages': result, 'image_policy': fd.get('image_policy', 'legacy')}

def migrate(w, v, apply=False, backup_dir=None):
    v = v.resolve()
    with asset_lock(w, v) if apply else nullcontext():
        return _migrate(w, v, apply, backup_dir)

def _migrate(w, v, apply, backup_dir):
    errors = w.validate(v)
    if errors:
        raise ValueError('Fix validation before migration: ' + str(errors))
    entries = []
    replacements = {}
    for ft in sorted((v / '03fulltext').rglob('*.md')):
        fd, body = w.split(ft.read_text(encoding='utf-8'))
        if fd.get('type') != 'literature-fulltext' or fd.get('image_policy') == POLICY:
            continue
        digest(fd)
        k = w.key(fd['zotero_key'])
        images = [image_path(w, v, ft, k, i) for i in range(1, fd['page_count'] + 1)]
        if not all(p.is_file() for p in images):
            raise ValueError('Legacy archive does not match generated image layout: ' + str(ft))
        stripped = AUTO_IMAGE.sub(lambda m: '' if m[2] == k else m[0], body)
        replacements[ft] = w.doc(fd, stripped)
        entries.append({'ft': ft, 'fd': fd, 'body': body, 'stripped': stripped,
                        'images': images, 'hash': w.sha(ft)})
    candidates = [p for e in entries for p in e['images']]
    protected = referenced(w, v, candidates, replacements)
    plan = []
    for e in entries:
        retained = [i for i, p in enumerate(e['images'], 1) if p.resolve() in protected]
        e['retained'] = retained
        plan.append({'key': e['fd']['zotero_key'], 'retained_pages': retained,
                     'cached_pages': [i for i in range(1, len(e['images']) + 1) if i not in retained]})
    result = {'state': 'MIGRATED' if apply else 'DRY_RUN', 'papers': plan,
              'retained_images': len(protected), 'cached_images': len(candidates) - len(protected)}
    if not apply or not entries:
        return result
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else w.inside(v, '_staging/backups')
    target_dir.mkdir(parents=True, exist_ok=True)
    backup = target_dir / f'page-assets-{stamp}.zip'
    # Close and fsync backup before changing originals. Archive paths are Vault-relative.
    with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as archive:
        for e in entries:
            for p in [e['ft']] + e['images']:
                archive.write(p, p.relative_to(v).as_posix())
        archive.writestr('migration-plan.json', json.dumps(result, ensure_ascii=False, indent=2))
    with backup.open('rb+') as f:
        os.fsync(f.fileno())
    moved = []
    originals = {e['ft']: e['ft'].read_text(encoding='utf-8') for e in entries}
    # Preflight failures must never restore over another writer's new content.
    if any(w.sha(e['ft']) != e['hash'] for e in entries) or referenced(w, v, candidates, replacements) != protected:
        raise ValueError('Vault changed during migration; rerun preview')
    written = {}
    try:
        for e in entries:
            fd = dict(e['fd'])
            fd.update(image_policy=POLICY, retained_pages=e['retained'])
            if fd.get('source_type') == 'pypdf+page-render':
                fd['source_type'] = 'pypdf'
            keep = set(e['retained'])
            body = AUTO_IMAGE.sub(lambda m: m[0] if m[2] != fd['zotero_key'] or int(m[1]) in keep else '', e['body'])
            w.atomic(e['ft'], w.doc(fd, body), expected=e['hash'])
            written[e['ft']] = w.sha(e['ft'])
            for i, p in enumerate(e['images'], 1):
                if i in keep:
                    continue
                cached = cache_path(w, v, fd, i)
                cached.parent.mkdir(parents=True, exist_ok=True)
                if cached.exists():
                    raise ValueError('Existing cache collision; inspect before migrating')
                os.replace(p, cached)
                moved.append((p, cached))
        errors = w.validate(v)
        if errors:
            raise ValueError('Post-migration validation failed: ' + str(errors))
    except Exception:
        for old, cached in reversed(moved):
            os.replace(cached, old)
        for ft, expected in written.items():
            w.atomic(ft, originals[ft], expected=expected)
        raise
    result['backup'] = str(backup)
    w.atomic(w.inside(v, f'_staging/migrations/page-assets-{stamp}.json'), json.dumps(result, ensure_ascii=False, indent=2))
    return result

def prune(w, v, days=30, apply=False):
    v = v.resolve()
    if days < 0:
        raise ValueError('days must be nonnegative')
    with asset_lock(w, v) if apply else nullcontext():
        root = w.inside(v, '_staging/page-cache')
        candidates = [p for p in root.rglob('*.png') if p.is_file()]
        protected = referenced(w, v, candidates)
        cutoff = time.time() - days * 86400
        eligible = []
        for p in candidates:
            # Never follow a symlink outside the cache, or delete arbitrary assets.
            rel = p.relative_to(root)
            if len(rel.parts) != 3 or not re.fullmatch('[A-Z0-9]{8}', rel.parts[0]) or not re.fullmatch('[a-f0-9]{64}', rel.parts[1]) or not re.fullmatch(r'page-\d{3,}\.png', rel.parts[2]):
                continue
            if not p.is_symlink() and p.resolve().is_relative_to(root.resolve()) and p.resolve() not in protected and p.stat().st_mtime <= cutoff:
                eligible.append(p)
        size = sum(p.stat().st_size for p in eligible)
        if apply:
            for p in eligible:
                p.unlink()
        return {'state': 'PRUNED' if apply else 'DRY_RUN', 'files': len(eligible),
                'bytes': size, 'days': days, 'referenced_cache_files_preserved': len(protected)}
