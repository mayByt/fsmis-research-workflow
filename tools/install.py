#!/usr/bin/env python3
"""Install portable templates and seven skills without silently replacing existing files."""
from __future__ import annotations
import argparse
import datetime
import json
import sys
from pathlib import Path
from workflow import ROOT, atomic, inside


def install(vault: Path, update_managed: bool = False) -> dict:
    vault = vault.expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    planned = {}
    for source_root, target_root in [(ROOT / 'templates', '模板'), (ROOT / 'skills', '.agents/skills')]:
        for source in sorted(source_root.rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts:
                rel = f'{target_root}/{source.relative_to(source_root).as_posix()}'
                text = source.read_text(encoding='utf-8').replace('{{WORKFLOW_ROOT}}', str(ROOT))
                planned[rel] = text
    guide = (ROOT / 'docs/VAULT_WORKFLOW.md').read_text(encoding='utf-8').replace('{{WORKFLOW_ROOT}}', str(ROOT)).replace('{{PYTHON}}', sys.executable)
    planned['WORKFLOW.md'] = guide
    planned['00dashboard/科研阅读首页.md'] = (ROOT / 'docs/DASHBOARD.md').read_text(encoding='utf-8')
    conflicts = [rel for rel, value in planned.items() if inside(vault, rel).exists() and inside(vault, rel).read_text(encoding='utf-8') != value]
    if conflicts and not update_managed:
        raise ValueError('Existing different files; review and rerun with --update-managed to back up and replace only managed files: ' + ', '.join(conflicts))
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    backup = inside(vault, '_staging/install-backups/' + stamp)
    changed = []
    for rel, value in planned.items():
        target = inside(vault, rel)
        if target.exists() and target.read_text(encoding='utf-8') == value:
            continue
        if target.exists():
            atomic(inside(vault, f'_staging/install-backups/{stamp}/{rel}'), target.read_text(encoding='utf-8'))
        atomic(target, value)
        changed.append(rel)
    # Preserve an existing AGENTS.md; add a small discoverable pointer only once.
    agents = inside(vault, 'AGENTS.md')
    original = agents.read_text(encoding='utf-8') if agents.exists() else '# Research Vault\n'
    pointer = '\n<!-- FSMIS-WORKFLOW -->\n论文入库、精读、检索和知识维护请先读取本 Vault 的 WORKFLOW.md，并使用 .agents/skills/ 下相应技能。\n'
    if '<!-- FSMIS-WORKFLOW -->' not in original:
        if agents.exists():
            atomic(inside(vault, f'_staging/install-backups/{stamp}/AGENTS.md'), original)
        atomic(agents, original.rstrip() + '\n' + pointer)
        changed.append('AGENTS.md')
    for rel in ['00dashboard', '01knowledge', '02vault/_index', '03fulltext', '04projects/ideas', '05meetings', '06assets', '_staging']:
        inside(vault, rel).mkdir(parents=True, exist_ok=True)
    manifest = {'version': '0.1.0', 'workflow_root': str(ROOT), 'vault_root': str(vault), 'managed_files': list(planned), 'changed_files': changed, 'backup': str(backup) if conflicts else None}
    atomic(inside(vault, '_staging/workflow-install.json'), json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, required=True)
    parser.add_argument('--update-managed', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.vault, args.update_managed), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'state': 'STOPPED', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
