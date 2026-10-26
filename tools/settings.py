"""Portable configuration. Local paths are never included in the repository."""
from __future__ import annotations
import os
import tomllib
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> dict:
    selected = os.environ.get('RESEARCH_WORKFLOW_CONFIG')
    path = Path(selected).expanduser() if selected else ROOT / 'config.toml'
    if selected and not path.is_file():
        raise ValueError(f'Configured file does not exist: {path}')
    raw = tomllib.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    values = dict(raw.get('paths', {}))
    values['zotero_api_url'] = raw.get('zotero', {}).get('api_url', 'http://localhost:23119/api/users/0')
    for name, env in [('vault_root', 'RESEARCHVAULT_ROOT'), ('zotero_data_dir', 'ZOTERO_DATA_DIR'), ('zotero_api_url', 'ZOTERO_LOCAL_API_URL')]:
        if os.environ.get(env):
            values[name] = os.environ[env]
    for name in ['vault_root', 'zotero_data_dir']:
        if values.get(name):
            p = Path(values[name]).expanduser()
            values[name] = str((p if p.is_absolute() else path.parent / p).resolve())
    return values


def vault_path(explicit: Path | None = None) -> Path:
    value = explicit or load_settings().get('vault_root')
    if not value:
        raise ValueError('Set --vault, RESEARCHVAULT_ROOT, or paths.vault_root in config.toml')
    return Path(value).expanduser().resolve()


def api_url() -> str:
    value = load_settings()['zotero_api_url'].rstrip('/')
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != '/api/users/0'):
        raise ValueError('Only a loopback HTTP Zotero personal-library API ending in /api/users/0 is supported')
    return value


def zotero_data_dir() -> Path:
    return Path(load_settings().get('zotero_data_dir', Path.home() / 'Zotero')).expanduser().resolve()
