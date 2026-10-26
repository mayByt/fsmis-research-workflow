import unittest,tempfile,sys,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import workflow as w
class Safety(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.v=Path(self.tmp.name);self.n=self.v/'02vault/c/n.md';self.f=self.v/'03fulltext/c/ABCD1234.md'
  d,b=w.split((w.ROOT/'templates/论文精读模板.md').read_text(encoding='utf-8'));d.update(zotero_key='ABCD1234',pdf_key='EFGH5678',note_path='02vault/c/n.md',fulltext_path='03fulltext/c/ABCD1234.md')
  w.atomic(self.n,w.doc(d,b.replace('此区域由我维护','不可丢失的个人想法：中文、公式 $x$。此区域由我维护')))
  fd={k:d[k] for k in ['zotero_key','pdf_key','note_path','fulltext_path']};fd.update(page_count=1)
  w.atomic(self.f,w.doc(fd,'## PDF 第 1 页\n![page](images/p.png)\nEvidence'))
  p=self.f.parent/'images/p.png';p.parent.mkdir();p.write_bytes(b'fixture')
  self.body=self.v/'body.txt';self.body.write_text('\n'.join(f'## {i:02} Section\nEvidence' for i in range(10)),encoding='utf-8')
 def tearDown(self):self.tmp.cleanup()
 def test_update_preserves_human_and_backup(self):
  before=self.n.read_text(encoding='utf-8');human=before.split('<!-- HUMAN:BEGIN -->')[1]
  out=w.update(self.v,'ABCD1234',self.body,None)
  self.assertEqual(human,self.n.read_text(encoding='utf-8').split('<!-- HUMAN:BEGIN -->')[1]);self.assertEqual(Path(out['backup']).read_text(encoding='utf-8'),before);self.assertEqual(w.validate(self.v),[])
 def test_forbid_identity(self):
  meta=self.v/'m.json';meta.write_text(json.dumps({'pdf_key':'ZZZZ9999'}),encoding='utf-8')
  with self.assertRaises(ValueError):w.update(self.v,'ABCD1234',self.body,meta)
 def test_duplicate(self):
  shutil.copy(self.n,self.n.with_name('duplicate.md'))
  with self.assertRaises(ValueError):w.find_note(self.v,'ABCD1234')
 def test_escape(self):
  with self.assertRaises(ValueError):w.inside(self.v,'../secret')
 def test_index_is_not_a_paper(self):
  w.atomic(self.v/'02vault/_index/index.md','# Index\n')
  self.assertEqual(w.validate(self.v),[])
 def test_missing_image(self):
  (self.f.parent/'images/p.png').unlink();self.assertTrue(w.validate(self.v))
 def test_concurrent_change(self):
  h=w.sha(self.n);self.n.write_text('changed',encoding='utf-8')
  with self.assertRaises(ValueError):w.atomic(self.n,'overwrite',expected=h)
 def test_four_domains(self):
  d,_=w.split(self.n.read_text(encoding='utf-8'))
  for domain in w.DOMAINS[:-1]:
   d.update(paper_domain=domain,analysis_modules=[domain]);w.check_fields(d)
  d['paper_domain']='invented'
  with self.assertRaises(ValueError):w.check_fields(d)
if __name__=='__main__':unittest.main()
