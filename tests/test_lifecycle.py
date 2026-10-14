import asyncio
from types import SimpleNamespace

import pytest

from pagequay.artifacts import Artifacts
from pagequay.browser import BrowserManager
from pagequay.events import Events
from pagequay.profiles import ProfileLock
from pagequay.settings import Settings
from pagequay.storage import Storage


async def test_cancelled_browser_launch_releases_profile_and_proxy(tmp_path, monkeypatch):
    from pagequay import browser as module

    proxies = []
    original = module.EgressProxy

    class TrackedProxy(original):
        def __init__(self, policy):
            super().__init__(policy)
            proxies.append(self)

    monkeypatch.setattr(module, "EgressProxy", TrackedProxy)
    settings = Settings(data_dir=tmp_path)
    db = Storage(tmp_path)
    project = db.create_project("test-project", "Test")
    manager = BrowserManager(db, settings, Events(), Artifacts(db, settings))
    started = asyncio.Event()

    async def stalled_launch(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    manager.playwright = SimpleNamespace(
        chromium=SimpleNamespace(
            executable_path="/unused", launch_persistent_context=stalled_launch
        )
    )
    task = asyncio.create_task(manager.start(project))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    lock = ProfileLock(db.root, project["id"])
    lock.acquire()
    lock.release()
    assert not proxies[0].server.is_serving()
    assert not manager.states
    db.close()
