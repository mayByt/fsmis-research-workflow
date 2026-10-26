#!/usr/bin/env python3
"""Regenerate the literature index, never paper notes."""
import argparse
import json
from pathlib import Path
import yaml
from workflow import atomic, inside, split
from settings import vault_path


def refresh(vault):
    rows = ['# 文献索引', '', '此文件自动生成；个人笔记请写入论文第 10 节。', '', '| 论文 | 领域 | 阅读状态 | FSMIS 价值 |', '|---|---|---|---|']
    for path in sorted((vault / '02vault').rglob('*.md')):
        if path.is_relative_to(vault / '02vault/_index'):
            continue
        data, _ = split(path.read_text(encoding='utf-8'))
        if data.get('type') != 'literature-note':
            continue
        title = data['title'].replace('|', '／').replace('\n', ' ')
        rel = path.relative_to(vault).with_suffix('').as_posix()
        rows.append(f'| [[{rel}\\|{title}]] | {data["paper_domain"]} | {data["reading_status"]} | {data["fsmis_relevance"]} |')
    output = inside(vault, '02vault/_index/文献索引.md')
    atomic(output, '\n'.join(rows) + '\n')
    return str(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({'index': refresh(vault_path(args.vault))}, ensure_ascii=False))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(json.dumps({'state': 'STOPPED', 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
