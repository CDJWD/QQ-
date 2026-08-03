"""任务状态读写（断点续传）。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def task_dir(save_dir: str | Path, group_id: str) -> Path:
    d = Path(save_dir) / '.qq_album_task' / str(group_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(save_dir: str | Path, group_id: str) -> Path:
    return task_dir(save_dir, group_id) / 'state.json'


def load_state(save_dir: str | Path, group_id: str) -> dict[str, Any] | None:
    path = state_path(save_dir, group_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def find_latest_state(base: Path | None = None) -> dict[str, Any] | None:
    """在常见位置或给定目录下寻找最近的任务状态。"""
    candidates: list[Path] = []
    if base and base.exists():
        candidates.append(base)
    home = Path.home() / 'Downloads'
    if home.exists():
        candidates.append(home)
    cwd = Path.cwd()
    candidates.append(cwd)

    latest: dict[str, Any] | None = None
    latest_mtime = 0.0
    for root in candidates:
        for path in root.rglob('.qq_album_task/*/state.json'):
            try:
                mtime = path.stat().st_mtime
                if mtime > latest_mtime:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    latest = data
                    latest_mtime = mtime
            except Exception:
                continue
    return latest


def new_state(
    group_id: str,
    mode: str,
    save_dir: str,
    albums: list[dict[str, Any]],
    selected_ids: list[str],
) -> dict[str, Any]:
    album_map: dict[str, Any] = {}
    for a in albums:
        aid = a['id']
        if aid not in selected_ids:
            continue
        album_map[aid] = {
            'title': a.get('title') or '',
            'photoCount': a.get('photoCount') or 0,
            'status': 'pending',
            'doneParts': [],
            'donePhotoIds': [],
            'error': None,
        }
    return {
        'groupId': str(group_id),
        'mode': mode,
        'saveDir': str(save_dir),
        'selectedAlbumIds': list(selected_ids),
        'albums': album_map,
        'createdAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'updatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
    }


def save_state(state: dict[str, Any]) -> Path:
    save_dir = state['saveDir']
    group_id = state['groupId']
    state['updatedAt'] = time.strftime('%Y-%m-%d %H:%M:%S')
    path = state_path(save_dir, group_id)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def update_album(state: dict[str, Any], album_id: str, **fields: Any) -> None:
    album = state['albums'].setdefault(album_id, {})
    album.update(fields)
    save_state(state)
