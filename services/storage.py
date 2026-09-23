from pathlib import Path
import json
from config import WORK_DIR, USERS_FILE, SETTINGS_FILE, ACCOUNTS_FILE


def ensure_storage():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    for p in (USERS_FILE, SETTINGS_FILE, ACCOUNTS_FILE):
        p.touch(exist_ok=True)


def _read(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _write(path: Path, rows):
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def get_settings(user_id):
    rows = _read(SETTINGS_FILE)
    for x in rows:
        if x.get("user_id") == str(user_id):
            # defaults for new fields
            x.setdefault("banner", "")
            x.setdefault("clip_seconds", 30)
            x.setdefault("mirror", False)
            x.setdefault("autopost", False)
            return x
    return {
        "user_id": str(user_id),
        "banner": "",
        "clip_seconds": 30,
        "mirror": False,
        "autopost": False,
    }


def save_settings(user_id, **changes):
    rows = _read(SETTINGS_FILE)
    current = get_settings(user_id)
    current.update(changes)
    for i, x in enumerate(rows):
        if x.get("user_id") == str(user_id):
            rows[i] = current
            break
    else:
        rows.append(current)
    _write(SETTINGS_FILE, rows)
    return current


def save_account(user_id, platform, payload):
    rows = _read(ACCOUNTS_FILE)
    rows = [
        x
        for x in rows
        if not (x.get("user_id") == str(user_id) and x.get("platform") == platform)
    ]
    rows.append({"user_id": str(user_id), "platform": platform, "payload": payload})
    _write(ACCOUNTS_FILE, rows)
