"""Measure profile files without opening their contents or following symbolic links."""

import os
import stat

CATEGORIES = {
    "cookies": "Cookies",
    "web_cache": "Cache Web",
    "site_storage": "Stockage des sites",
    "browser_cache": "Cache graphique / code",
    "images": "Fichiers image",
    "other": "Autres fichiers",
}


def category(parts):
    names = {part.lower() for part in parts}
    filename = parts[-1].lower()
    if filename in {"cookies", "cookies-journal", "cookies-wal", "cookies-shm"}:
        return "cookies"
    if names & {
        "gpucache",
        "code cache",
        "shadercache",
        "grshadercache",
        "dawncache",
        "scriptcache",
    }:
        return "browser_cache"
    if names & {"cache", "cache_data", "cachestorage", "media cache"}:
        return "web_cache"
    if names & {"local storage", "session storage", "indexeddb", "webstorage", "file system"}:
        return "site_storage"
    if filename.rsplit(".", 1)[-1] in {"png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "ico"}:
        return "images"
    return "other"


def profile_disk_usage(root, project_id):
    path = root / "profiles" / project_id
    result = {
        "total": 0,
        "logical": 0,
        "categories": dict.fromkeys(CATEGORIES, 0),
        "partial": False,
        "exists": False,
    }
    if path.name != project_id or path.is_symlink():
        result["partial"] = True
        return result
    try:
        root_stat = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return result
    except OSError:
        result["partial"] = True
        return result
    result["exists"] = True
    if not stat.S_ISDIR(root_stat.st_mode):
        result["partial"] = True
        return result
    pending, seen = [(path, ())], set()
    visited = 0
    while pending:
        directory, parts = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 100_000:
                        result["partial"] = True
                        return result
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        result["partial"] = True
                        continue
                    child_parts = (*parts, entry.name)
                    if stat.S_ISDIR(info.st_mode):
                        pending.append((entry.path, child_parts))
                    elif stat.S_ISREG(info.st_mode):
                        inode = (info.st_dev, info.st_ino)
                        if inode in seen:
                            continue
                        seen.add(inode)
                        allocated = getattr(info, "st_blocks", (info.st_size + 511) // 512) * 512
                        result["total"] += allocated
                        result["logical"] += info.st_size
                        result["categories"][category(child_parts)] += allocated
        except OSError:
            result["partial"] = True
    return result


def format_bytes(value):
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if value < 1024 or unit == "To":
            return f"{value:.1f} {unit}" if unit != "o" else f"{value} o"
        value /= 1024
