#!/usr/bin/env python3
"""Read-only Zotero API → page-faithful archive → protected V2 notes."""
import argparse, datetime, hashlib, json, os, re, tempfile, urllib.request, urllib.parse
from contextlib import contextmanager
from settings import ROOT, vault_path, api_url, zotero_data_dir
from pathlib import Path
import yaml
DOMAINS=['fsmis','medical_segmentation','general_cv','survey_benchmark','other']
ALLOWED={'theme','study_area','data_source','methodology','core_variable','key_finding','relevance','paper_domain','analysis_modules','method_tags','reading_status','reading_level','fsmis_relevance','transfer_mode'}
def now():return datetime.datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(s):
 if not re.fullmatch('[A-Z0-9]{8}',s):raise ValueError('需要真实的 8 位 Zotero Key')
 return s
def safe(s):return re.sub(r'[\\/:*?"<>|\[\]#^\x00-\x1f]','_',s).strip(' .')[:100] or '未分类'
def api(path):
 # Ignore system proxies for this loopback-only API.
 req=urllib.request.Request(api_url()+path,headers={'Zotero-API-Version':'3'})
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=15) as r:
  if urllib.parse.urlsplit(r.url).hostname not in {'localhost','127.0.0.1','::1'}:raise ValueError('Unexpected API redirect')
  return json.load(r)
def pages(path):
 result=[];start=0
 while True:
  sep='&' if '?' in path else '?';batch=api(path+sep+f'limit=100&start={start}')
  result.extend(batch)
  if not isinstance(batch,list):raise ValueError('Expected Zotero array response')
  if len(batch)<100:return result
  start+=len(batch)
def split(text):
 m=re.match(r'\A---\n(.*?)\n---\n',text,re.S)
 if not m:raise ValueError('缺少 YAML frontmatter')
 data=yaml.safe_load(m[1])
 if not isinstance(data,dict):raise ValueError('Frontmatter must be a mapping')
 return data,text[m.end():]
def doc(data,body):return '---\n'+yaml.safe_dump(data,allow_unicode=True,sort_keys=False,width=100000)+'---\n'+body
def inside(v,rel):
 p=(v/rel).resolve()
 if not p.is_relative_to(v.resolve()):raise ValueError('路径越出 Vault')
 return p
def atomic(p,text,expected=None):
 p.parent.mkdir(parents=True,exist_ok=True)
 if expected is not None and (not p.exists() or sha(p)!=expected):raise ValueError('文件已被并发修改，请重读')
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.workflow-',suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:f.write(text);f.flush();os.fsync(f.fileno())
  if expected is not None and sha(p)!=expected:raise ValueError('文件已被并发修改，请重读')
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def find_note(v,k):
 matches=[]
 for p in (v/'02vault').rglob('*.md'):
  if p.is_relative_to(v/'02vault/_index'):continue
  try:d,_=split(p.read_text(encoding='utf-8'))
  except (ValueError,yaml.YAMLError):continue
  if d.get('type')=='literature-note' and d.get('zotero_key')==k:matches.append(p)
 if len(matches)>1:raise ValueError('重复父 Key，先合并核对：'+str(matches))
 return matches[0] if matches else None
def inspect(k,pdfkey=None):
 item=api('/items/'+key(k));d=item['data']
 if item.get('library',{}).get('type')!='user':raise ValueError('Group libraries are not supported')
 if d['itemType'] in ('attachment','note','annotation'):raise ValueError('请提供父文献 Key')
 children=pages('/items/'+k+'/children')
 pdfs=[a for a in children if a['data'].get('contentType')=='application/pdf']
 if pdfkey:pdfs=[a for a in pdfs if a['key']==key(pdfkey)]
 if len(pdfs)!=1:raise ValueError('PDF 数量不是 1，请提供 --pdf-key；候选：'+str([a['key'] for a in pdfs]))
 att=pdfs[0];ad=att['data'];u=att.get('links',{}).get('enclosure',{}).get('href','')
 p=Path(urllib.parse.unquote(urllib.parse.urlparse(u).path)) if u.startswith('file://') else zotero_data_dir()/'storage'/att['key']/ad.get('filename','')
 if att['data'].get('parentItem')!=k:raise ValueError('Attachment parent identity mismatch')
 if not p.is_file():raise ValueError('PDF 本地文件不可用：'+str(p))
 cols=[api('/collections/'+key(c))['data']['name'] for c in d.get('collections',[])]
 anns=pages('/items/'+att['key']+'/children')
 return {'item':item,'attachment':att,'pdf_path':str(p),'collections':cols,'annotations':anns}
def _ingest(v,k,pdfkey=None):
 info=inspect(k,pdfkey);d=info['item']['data'];pk=info['attachment']['key'];pdf=Path(info['pdf_path']);digest=sha(pdf)
 existing=find_note(v,k)
 if existing:
  nd,_=split(existing.read_text(encoding='utf-8'));ft=inside(v,nd['fulltext_path'])
  if nd['pdf_key']!=pk:raise ValueError('PDF 身份已变化，须显式审查后迁移')
  if not ft.is_file():raise ValueError('已有笔记但全文缺失，需要定向修复，不自动覆盖笔记')
  fd,_=split(ft.read_text(encoding='utf-8'))
  if fd.get('source_sha256')!=digest:raise ValueError('PDF 内容变化，停止自动覆盖；请审查刷新')
  errs=validate(v)
  if errs:raise ValueError('复用校验失败：'+str(errs))
  return {'state':'REUSED','note':str(existing),'fulltext':str(ft)}
 col=safe(info['collections'][0] if info['collections'] else '未分类')
 nr=f'02vault/{col}/{safe(d["title"])}--{k}.md';fr=f'03fulltext/{col}/{k}.md'
 note=inside(v,nr);ft=inside(v,fr)
 if note.exists() or ft.exists():raise ValueError('目标已存在但未匹配唯一身份，停止覆盖')
 from pypdf import PdfReader
 import pypdfium2 as pdfium
 reader=PdfReader(pdf);texts=[p.extract_text() or '' for p in reader.pages]
 if not texts or any(len(t.strip())<30 for t in texts):raise ValueError('存在扫描/低文本页面，需 OCR 核验；未创建正式笔记')
 nd,body=split((v/'模板/论文精读模板.md').read_text(encoding='utf-8'))
 nd.update(title=d['title'],created=now()[:10],source=d.get('publicationTitle',d.get('proceedingsTitle','')),author='; '.join(c.get('name') or (c.get('firstName','')+' '+c.get('lastName','')).strip() for c in d.get('creators',[])),year=(re.search(r'\b(?:19|20)\d{2}\b',d.get('date','')) or [''])[0] or None,zotero_key=k,pdf_key=pk,doi=d.get('DOI',''),collection=col,note_path=nr,fulltext_path=fr,zotero_item=f'zotero://select/library/items/{k}',zotero_pdf=f'zotero://open-pdf/library/items/{pk}')
 body=body.replace('{{title}}',d['title']).replace('- 文献与全文入口：由入库工具填入。',f'- [Zotero 条目]({nd["zotero_item"]}) · [原 PDF]({nd["zotero_pdf"]}) · [[{fr[:-3]}|逐页全文]]')
 fd={x:nd[x] for x in ['title','zotero_key','pdf_key','doi','collection','note_path','fulltext_path','zotero_item','zotero_pdf']}
 fd.update(type='literature-fulltext',source_type='pypdf+page-render',source_sha256=digest,page_mapping='physical_pdf_1_based',page_count=len(texts),extraction_quality='text_extracted_visual_verification_required')
 image_dir=inside(v,f'03fulltext/{col}/images/{k}');image_dir.mkdir(parents=True,exist_ok=True)
 render=pdfium.PdfDocument(str(pdf));chunks=[f'# {d["title"]}\n\n[[{nr[:-3]}|精读笔记]]\n\n原文逐页提取；公式及表格请核对页面图像。页号为 PDF 物理页。\n']
 for i,t in enumerate(texts,1):
  name=f'page-{i:03}.png';page=render[i-1];bitmap=page.render(scale=1.5);bitmap.to_pil().save(image_dir/name);bitmap.close();page.close()
  chunks.append(f'\n## PDF 第 {i} 页\n\n[在 Zotero 打开此页]({nd["zotero_pdf"]}?page={i})\n\n![PDF 第 {i} 页](images/{k}/{name})\n\n'+t+'\n')
 render.close()
 atomic(ft,doc(fd,''.join(chunks)));atomic(note,doc(nd,body))
 atomic(inside(v,f'_staging/metadata/{k}.json'),json.dumps(info,ensure_ascii=False,indent=2))
 errors=validate(v)
 if errors:raise ValueError(str(errors))
 return {'state':'INGESTED_NOT_ANALYZED','note':str(note),'fulltext':str(ft),'pages':len(texts)}
def _update(v,k,bodyfile,metafile):
 p=find_note(v,key(k))
 if not p:raise ValueError('请先入库')
 original=p.read_text(encoding='utf-8');h=sha(p);d,b=split(original)
 for marker in ['<!-- AUTO:BEGIN -->','<!-- AUTO:END -->','<!-- HUMAN:BEGIN -->','<!-- HUMAN:END -->']:
  if b.count(marker)!=1:raise ValueError('区域标记缺失/重复，先人工审查迁移')
 markers=['<!-- AUTO:BEGIN -->','<!-- AUTO:END -->','<!-- HUMAN:BEGIN -->','<!-- HUMAN:END -->']
 if [b.index(m) for m in markers]!=sorted(b.index(m) for m in markers):raise ValueError('Protected regions overlap or are out of order')
 new=Path(bodyfile).read_text(encoding='utf-8');meta=json.loads(Path(metafile).read_text(encoding='utf-8')) if metafile else {}
 if set(meta)-ALLOWED:raise ValueError('禁止覆盖身份/人工字段：'+str(set(meta)-ALLOWED))
 if '<!--' in new or re.search(r'^## 10 ',new,re.M):raise ValueError('分析区不得含保护标记或人工章节')
 for i in range(10):
  if not re.search(r'^## '+f'{i:02d}'+r' ',new,re.M):raise ValueError(f'缺少章节 {i:02d}')
 d.update(meta);check_fields(d)
 a=b.index('<!-- AUTO:BEGIN -->')+len('<!-- AUTO:BEGIN -->');z=b.index('<!-- AUTO:END -->')
 if a>=z:raise ValueError('标记顺序错误')
 updated=doc(d,b[:a]+'\n'+new.strip()+'\n'+b[z:])
 backup=inside(v,'_staging/backups/'+k+'-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')+'.md')
 atomic(backup,original);atomic(p,updated,expected=h)
 return {'state':'UPDATED','note':str(p),'backup':str(backup)}
def check_fields(d):
 choices={'paper_domain':DOMAINS,'reading_status':['inbox','skimmed','reading','deep_read','reported'],'reading_level':['skim','deep'],'fsmis_relevance':['high','potential','low','uncertain'],'transfer_mode':['brief','deep']}
 for f,values in choices.items():
  if d.get(f) not in values:raise ValueError(f+' 非法值')
 for f in ['analysis_modules','method_tags']:
  if not isinstance(d.get(f),list):raise ValueError(f+' 必须为列表')
 if not all(isinstance(x,str) for f in ['analysis_modules','method_tags'] for x in d[f]):raise ValueError('List values must be strings')
 if set(d['analysis_modules'])-set(DOMAINS[:-1]):raise ValueError('非法领域模块')
def validate(v):
 errors=[];seen=set()
 if not (v/'02vault').is_dir() or not (v/'03fulltext').is_dir():return ['Vault not initialized: 02vault/ or 03fulltext/ is missing']
 for p in (v/'02vault').rglob('*.md'):
  if p.is_relative_to(v/'02vault/_index'):continue
  try:
   d,b=split(p.read_text(encoding='utf-8'))
   if d.get('type')!='literature-note':continue
   check_fields(d);k=key(d['zotero_key']);key(d['pdf_key'])
   if k in seen:raise ValueError('重复 Key')
   seen.add(k)
   if inside(v,d['note_path'])!=p.resolve():raise ValueError('note_path 不匹配')
   ft=inside(v,d['fulltext_path'])
   if not ft.is_relative_to((v/'03fulltext').resolve()):raise ValueError('非规范全文路径')
   fd,fb=split(ft.read_text(encoding='utf-8'))
   for f in ['zotero_key','pdf_key','note_path','fulltext_path']:
    if fd.get(f)!=d.get(f):raise ValueError(f+' 双向不匹配')
   n=fd.get('page_count',0)
   if not n or len(re.findall(r'^## PDF 第 \d+ 页$',fb,re.M))!=n:raise ValueError('全文缺页')
   images=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',fb)
   if len(images)!=n:raise ValueError('页面图像数量不符')
   for im in images:
    ip=(ft.parent/im).resolve()
    if not ip.is_relative_to(v.resolve()) or not ip.is_file():raise ValueError('图片缺失/越界')
   for marker in ['<!-- AUTO:BEGIN -->','<!-- AUTO:END -->','<!-- HUMAN:BEGIN -->','<!-- HUMAN:END -->']:
    if b.count(marker)!=1:raise ValueError('保护标记不唯一')
  except Exception as e:errors.append(str(p)+': '+str(e))
 return errors
@contextmanager
def paper_lock(v,k):
 lock=inside(v,f'_staging/locks/{key(k)}.lock');lock.parent.mkdir(parents=True,exist_ok=True)
 try:
  fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:
  raise ValueError(f'Another run or stale lock exists: {lock}; inspect before removing')
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(str(os.getpid()))
  yield
 finally:lock.unlink()

def ingest(v,k,pdfkey=None):
 with paper_lock(v,k):return _ingest(v,k,pdfkey)

def update(v,k,bodyfile,metafile):
 with paper_lock(v,k):return _update(v,k,bodyfile,metafile)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--vault',type=Path)
 sub=parser.add_subparsers(dest='cmd',required=True)
 l=sub.add_parser('list');l.add_argument('--query',default='')
 for c in ['inspect','ingest']:
  s=sub.add_parser(c);s.add_argument('key');s.add_argument('--pdf-key')
 s=sub.add_parser('update');s.add_argument('key');s.add_argument('--body',required=True);s.add_argument('--metadata')
 sub.add_parser('validate');a=parser.parse_args()
 try:
  if a.cmd=='list':result=[{'key':x['key'],'title':x['data'].get('title'),'type':x['data']['itemType']} for x in pages('/items/top?q='+urllib.parse.quote(a.query))]
  elif a.cmd=='inspect':result=inspect(a.key,a.pdf_key)
  elif a.cmd=='ingest':result=ingest(vault_path(a.vault),key(a.key),a.pdf_key)
  elif a.cmd=='update':result=update(vault_path(a.vault),a.key,a.body,a.metadata)
  else:
   errs=validate(vault_path(a.vault));result={'state':'FAIL' if errs else 'PASS','errors':errs}
   if errs:print(json.dumps(result,ensure_ascii=False,indent=2));return 1
  print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'state':'STOPPED','error':str(e)},ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
