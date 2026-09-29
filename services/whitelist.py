from config import WHITELIST_FILE, ENV_WHITELIST, WORK_DIR, ADMIN_IDS


def _ensure():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if not WHITELIST_FILE.exists():
        ids = sorted(ENV_WHITELIST | ADMIN_IDS)
        WHITELIST_FILE.write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")


def load() -> set[str]:
    _ensure()
    ids = set()
    for line in WHITELIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.add(line)
    ids |= ENV_WHITELIST
    ids |= ADMIN_IDS
    return ids


def save(ids: set[str]) -> None:
    _ensure()
    ids = set(ids) | ADMIN_IDS
    WHITELIST_FILE.write_text("\n".join(sorted(ids, key=lambda x: (len(x), x))) + "\n", encoding="utf-8")


def is_allowed(user_id: int) -> bool:
    ids = load()
    if not ids and not ENV_WHITELIST and not ADMIN_IDS:
        return True
    return str(user_id) in ids


def add(user_id) -> bool:
    uid = str(user_id).strip()
    ids = load()
    if uid in ids:
        return False
    ids.add(uid)
    save(ids)
    return True


def remove(user_id) -> bool:
    uid = str(user_id).strip()
    if uid in ADMIN_IDS:
        return False
    ids = load()
    if uid not in ids:
        return False
    ids.discard(uid)
    save(ids)
    return True


def list_ids() -> list[str]:
    return sorted(load(), key=lambda x: (len(x), x))
