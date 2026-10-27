import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import workflow as w
import page_assets as a


class PageAssets(unittest.TestCase):
    def setUp(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        self.temp = tempfile.TemporaryDirectory()
        self.v = Path(self.temp.name).resolve() / 'Vault 中文'
        self.v.mkdir()
        self.k = 'ABCD1234'
        self.pdf = Path(self.temp.name) / 'source.pdf'
        writer = PdfWriter()
        for number in range(2):
            page = writer.add_blank_page(width=320, height=240)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 20 120 Td (A synthetic paper with enough text to exercise page extraction safely.) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(self.pdf)
        self.info = {'item': {'key': self.k, 'data': {'title': 'Fixture', 'creators': [], 'itemType': 'journalArticle'}}, 'attachment': {'key': 'EFGH5678'}, 'pdf_path': str(self.pdf), 'collections': ['c'], 'annotations': []}
        d, body = w.split((w.ROOT / 'templates/论文精读模板.md').read_text(encoding='utf-8'))
        d.update(zotero_key=self.k, pdf_key='EFGH5678', note_path='02vault/c/n.md', fulltext_path=f'03fulltext/c/{self.k}.md')
        self.note = self.v / d['note_path']
        self.ft = self.v / d['fulltext_path']
        body += '\n![[03fulltext/c/images/ABCD1234/page-001.png|850]]\n'
        w.atomic(self.note, w.doc(d, body))
        self.fd = {field: d[field] for field in ['zotero_key', 'pdf_key', 'note_path', 'fulltext_path']}
        self.fd.update(type='literature-fulltext', page_count=2, source_sha256=w.sha(self.pdf), source_type='pypdf+page-render')
        self.body = ''.join(f'## PDF 第 {i} 页\n\n[Zotero](zotero://open-pdf/library/items/EFGH5678?page={i})\n\n![PDF 第 {i} 页](images/{self.k}/page-{i:03}.png)\n\nOriginal text {i}: $x+y$\n' for i in range(1, 3))
        w.atomic(self.ft, w.doc(self.fd, self.body))
        for i in range(1, 3):
            p = a.image_path(w, self.v, self.ft, self.k, i)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'old fixture image ' + str(i).encode())
        self.backups = Path(self.temp.name) / 'backups'

    def tearDown(self):
        self.temp.cleanup()

    def migrate(self):
        return a.migrate(w, self.v, True, self.backups)

    def test_preview_is_read_only_and_migration_preserves_links_and_text(self):
        before = {p.relative_to(self.v): p.read_bytes() for p in self.v.rglob('*') if p.is_file()}
        preview = a.migrate(w, self.v)
        self.assertEqual(preview['papers'][0]['retained_pages'], [1])
        self.assertEqual(before, {p.relative_to(self.v): p.read_bytes() for p in self.v.rglob('*') if p.is_file()})
        result = self.migrate()
        self.assertEqual(self.note.read_bytes(), before[self.note.relative_to(self.v)])
        fd, body = w.split(self.ft.read_text(encoding='utf-8'))
        self.assertEqual(a.AUTO_IMAGE.sub('', body), a.AUTO_IMAGE.sub('', self.body))
        self.assertEqual(fd['source_sha256'], self.fd['source_sha256'])
        self.assertEqual(w.validate(self.v), [])
        with zipfile.ZipFile(result['backup']) as archive:
            self.assertEqual(archive.read(self.ft.relative_to(self.v).as_posix()), before[self.ft.relative_to(self.v)])
        self.assertEqual(a.migrate(w, self.v, True, self.backups)['papers'], [])

    def test_failed_migration_rolls_back(self):
        original = self.ft.read_bytes()
        with patch.object(w, 'validate', side_effect=[[], ['simulated failure']]):
            with self.assertRaises(ValueError):
                self.migrate()
        self.assertEqual(self.ft.read_bytes(), original)
        self.assertTrue(a.image_path(w, self.v, self.ft, self.k, 2).exists())
        self.assertEqual(w.validate(self.v), [])

    def test_cache_cleanup_never_removes_retained_or_referenced_images(self):
        self.migrate()
        cached = a.cache_path(w, self.v, self.fd, 2)
        w.atomic(self.v / '04projects/link.md', f'[page](<{cached.relative_to(self.v)}> "important")')
        result = a.prune(w, self.v, 0, True)
        self.assertEqual(result['files'], 0)
        self.assertTrue(cached.exists())
        (self.v / '04projects/link.md').unlink()
        self.assertEqual(a.prune(w, self.v, 0)['files'], 1)
        self.assertTrue(cached.exists())
        self.assertEqual(a.prune(w, self.v, 0, True)['files'], 1)
        self.assertTrue(a.image_path(w, self.v, self.ft, self.k, 1).exists())
        self.assertEqual(w.validate(self.v), [])

    def test_all_vault_links_and_short_names_protect_legacy_pages(self):
        w.atomic(self.v / '01knowledge/example.md', '[figure](page-002.png)')
        result = self.migrate()
        self.assertEqual(result['retained_images'], 2)
        self.assertEqual(result['cached_images'], 0)

    def test_cache_absence_allowed_but_retained_missing_fails(self):
        self.migrate()
        a.prune(w, self.v, 0, True)
        self.assertEqual(w.validate(self.v), [])
        a.image_path(w, self.v, self.ft, self.k, 1).unlink()
        self.assertTrue(w.validate(self.v))

    def test_bad_page_mapping_fails(self):
        self.migrate()
        fd, body = w.split(self.ft.read_text(encoding='utf-8'))
        w.atomic(self.ft, w.doc(fd, body.replace('## PDF 第 2 页', '## PDF 第 1 页')))
        self.assertTrue(w.validate(self.v))

    def test_render_cache_then_promote_and_prune(self):
        self.migrate()
        a.prune(w, self.v, 0, True)
        with patch.object(w, 'inspect', return_value=self.info):
            before = self.ft.read_bytes()
            result = a.render(w, self.v, self.k, '2')
            cache = Path(result['pages'][0]['path'])
            self.assertTrue(cache.read_bytes().startswith(b'\x89PNG'))
            self.assertFalse(result['pages'][0]['retained'])
            self.assertEqual(self.ft.read_bytes(), before)
            kept = a.render(w, self.v, self.k, '2', True)
            durable = Path(kept['pages'][0]['path'])
            self.assertTrue(kept['pages'][0]['retained'])
            self.assertFalse(cache.exists())
        a.prune(w, self.v, 0, True)
        self.assertTrue(durable.exists())
        fd, _ = w.split(self.ft.read_text(encoding='utf-8'))
        self.assertEqual(fd['retained_pages'], [1, 2])
        self.assertEqual(w.validate(self.v), [])

    def test_promoting_cache_preserves_existing_cache_links(self):
        self.migrate()
        cache = a.cache_path(w, self.v, self.fd, 2)
        w.atomic(self.v / '04projects/old-link.md', f'![[{cache.relative_to(self.v).as_posix()}]]')
        with patch.object(w, 'inspect', return_value=self.info):
            result = a.render(w, self.v, self.k, '2', True)
        self.assertTrue(Path(result['pages'][0]['path']).exists())
        self.assertTrue(cache.exists())
        self.assertEqual(a.prune(w, self.v, 0, True)['files'], 0)

    def test_source_mutation_and_out_of_bounds_refuse_render(self):
        self.migrate()
        with patch.object(w, 'inspect', return_value=self.info) as inspect:
            with self.assertRaises(ValueError):
                a.render(w, self.v, self.k, '0,3')
            inspect.assert_not_called()
            self.pdf.write_bytes(self.pdf.read_bytes() + b'\n%changed')
            with self.assertRaises(ValueError):
                a.render(w, self.v, self.k, '2')

    def test_fresh_ingest_has_no_png_and_reuses_text(self):
        fresh = Path(self.temp.name) / 'fresh'
        template = fresh / '模板/论文精读模板.md'
        template.parent.mkdir(parents=True)
        shutil.copy(w.ROOT / 'templates/论文精读模板.md', template)
        with patch.object(w, 'inspect', return_value=self.info):
            result = w.ingest(fresh, self.k)
            self.assertEqual(list(fresh.rglob('*.png')), [])
            fd, body = w.split(Path(result['fulltext']).read_text(encoding='utf-8'))
            self.assertEqual(fd['image_policy'], 'on_demand')
            self.assertEqual(body.count('## PDF 第 '), 2)
            self.assertEqual(w.ingest(fresh, self.k)['state'], 'REUSED')
        self.assertEqual(w.validate(fresh), [])

    def test_path_escape_and_stale_asset_lock(self):
        self.migrate()
        with a.asset_lock(w, self.v):
            with self.assertRaises(ValueError):
                a.prune(w, self.v, 0, True)
        with self.assertRaises(ValueError):
            a.cache_path(w, self.v, dict(self.fd, source_sha256='../escape'), 1)


if __name__ == '__main__':
    unittest.main()
