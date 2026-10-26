import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import workflow as w
import settings
import install
import refresh_index


class Portable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / '中文 Vault with spaces'
        install.install(self.vault)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_is_idempotent_and_preserves_custom_agents(self):
        path = self.vault / 'AGENTS.md'
        content = path.read_text(encoding='utf-8')
        path.write_text(content + '\nPersonal instructions\n', encoding='utf-8')
        again = install.install(self.vault)
        self.assertEqual(again['changed_files'], [])
        self.assertIn('Personal instructions', path.read_text(encoding='utf-8'))
        self.assertEqual(len(list((self.vault / '.agents/skills').glob('*/SKILL.md'))), 7)

    def test_conflicting_template_requires_explicit_update(self):
        path = self.vault / '模板/论文精读模板.md'
        path.write_text('CUSTOM', encoding='utf-8')
        with self.assertRaises(ValueError):
            install.install(self.vault)
        self.assertEqual(path.read_text(encoding='utf-8'), 'CUSTOM')
        result = install.install(self.vault, update_managed=True)
        self.assertEqual((Path(result['backup']) / '模板/论文精读模板.md').read_text(encoding='utf-8'), 'CUSTOM')

    def test_relative_config_and_env(self):
        conf = self.root / 'config.toml'
        conf.write_text('[paths]\nvault_root="relative vault"\n', encoding='utf-8')
        with patch.dict(os.environ, {'RESEARCH_WORKFLOW_CONFIG': str(conf)}, clear=True):
            self.assertEqual(settings.vault_path(), (self.root / 'relative vault').resolve())
        with patch.dict(os.environ, {'RESEARCHVAULT_ROOT': str(self.vault)}, clear=True):
            self.assertEqual(settings.vault_path(), self.vault.resolve())
        with patch.dict(os.environ, {'ZOTERO_LOCAL_API_URL': 'https://external.example/api/users/0'}):
            with self.assertRaises(ValueError):
                settings.api_url()

    def test_cli_requires_real_vault_for_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(settings, 'ROOT', self.root):
                with self.assertRaises(ValueError):
                    settings.vault_path()
        self.assertTrue(w.validate(self.root / 'missing'))

    def test_paper_lock_rejects_concurrent_writer(self):
        with w.paper_lock(self.vault, 'ABCD1234'):
            with self.assertRaises(ValueError):
                with w.paper_lock(self.vault, 'ABCD1234'):
                    pass
        with w.paper_lock(self.vault, 'ABCD1234'):
            pass

    def test_synthetic_pdf_ingest_and_repeat_preserve_human(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        pdf = self.root / 'synthetic.pdf'
        writer = PdfWriter()
        page = writer.add_blank_page(width=320, height=240)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 20 120 Td (Synthetic research fixture with enough text for extraction and rendering.) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(pdf)
        item = {'key': 'ABCD1234', 'data': {'title': 'Synthetic / fixture', 'creators': [], 'itemType': 'journalArticle'}}
        info = {'item': item, 'attachment': {'key': 'EFGH5678'}, 'pdf_path': str(pdf), 'collections': ['Synthetic'], 'annotations': []}
        with patch.object(w, 'inspect', return_value=info):
            first = w.ingest(self.vault, 'ABCD1234')
            self.assertEqual(first['pages'], 1)
            note = Path(first['note'])
            content = note.read_text(encoding='utf-8').replace('此区域由我维护', 'Keep my personal thought. 此区域由我维护')
            note.write_text(content, encoding='utf-8')
            before = w.sha(note)
            second = w.ingest(self.vault, 'ABCD1234')
            self.assertEqual(second['state'], 'REUSED')
            self.assertEqual(w.sha(note), before)
        self.assertEqual(w.validate(self.vault), [])
        index = Path(refresh_index.refresh(self.vault))
        self.assertIn('Synthetic', index.read_text(encoding='utf-8'))
        self.assertEqual(w.validate(self.vault), [])
        # Source mutation must not silently refresh an existing archive.
        pdf.write_bytes(pdf.read_bytes() + b'\n% changed')
        with patch.object(w, 'inspect', return_value=info):
            with self.assertRaises(ValueError):
                w.ingest(self.vault, 'ABCD1234')


if __name__ == '__main__':
    unittest.main()
