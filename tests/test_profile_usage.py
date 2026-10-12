import os

from bs4 import BeautifulSoup
from conftest import login

from pagequay.profile_usage import profile_disk_usage


def test_profile_sizes_use_allocated_blocks_and_separate_categories(tmp_path):
    root = tmp_path / "profiles" / "project"
    files = {
        "Default/Network/Cookies": ("cookies", b"cookies" * 500),
        "Default/Network/Cookies-wal": ("cookies", b"wal" * 500),
        "Default/Cache/Cache_Data/image.webp": ("web_cache", b"image" * 500),
        "Default/Service Worker/CacheStorage/index": ("web_cache", b"cache" * 500),
        "Default/Code Cache/js/index": ("browser_cache", b"js" * 500),
        "Default/IndexedDB/data": ("site_storage", b"data" * 500),
        "Default/Local Storage/leveldb/data": ("site_storage", b"local" * 500),
        "preview.png": ("images", b"png" * 500),
        "Default/History": ("other", b"history" * 500),
    }
    expected = {}
    logical = 0
    for name, (category, contents) in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        expected[category] = expected.get(category, 0) + path.stat().st_blocks * 512
        logical += len(contents)
    sparse = root / "sparse"
    with sparse.open("wb") as handle:
        handle.truncate(10_000_000)
    expected["other"] += sparse.stat().st_blocks * 512
    logical += sparse.stat().st_size
    os.link(root / "preview.png", root / "copy.png")
    external = tmp_path / "outside"
    external.mkdir()
    (external / "secret").write_bytes(b"outside" * 1000)
    (root / "external").symlink_to(external, target_is_directory=True)
    (root / "linked.png").symlink_to(external / "secret")
    data = profile_disk_usage(tmp_path, "project")
    assert data["exists"] and not data["partial"]
    assert data["categories"] == expected
    assert data["total"] == sum(expected.values())
    assert data["logical"] == logical


def test_missing_symlink_and_unreadable_profiles(tmp_path, monkeypatch):
    assert profile_disk_usage(tmp_path, "missing")["total"] == 0
    path = tmp_path / "profiles" / "unsafe"
    path.parent.mkdir()
    path.symlink_to(tmp_path, target_is_directory=True)
    assert profile_disk_usage(tmp_path, "unsafe")["partial"]
    assert profile_disk_usage(tmp_path, "../outside")["partial"]
    (tmp_path / "profiles" / "unreadable").mkdir()

    def denied(_):
        raise PermissionError("unreadable")

    monkeypatch.setattr(os, "scandir", denied)
    data = profile_disk_usage(tmp_path, "unreadable")
    assert data["partial"] and data["total"] == 0


def test_profile_disk_usage_visible_on_overview_and_projects(client, projects):
    rt = client.app.state.rt
    project = projects[0]
    path = rt.db.root / "profiles" / project["id"] / "Default" / "Network" / "Cookies"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test cookies" * 500)
    login(client)
    for url in ("/admin", "/admin/projects"):
        soup = BeautifulSoup(client.get(url).text, "html.parser")
        disk = soup.select_one(f'[data-profile-disk="{project["id"]}"]')
        assert "UniversRobot" in disk.get_text()
        assert "Cookies" in disk.get_text() and "Cache Web" in disk.get_text()
        assert "0 o" != disk.select_one(".profile-disk-heading div:last-child strong").get_text()
