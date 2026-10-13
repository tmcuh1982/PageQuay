import json
from types import SimpleNamespace

import pytest
from playwright.async_api import Error

from pagequay import page_reader
from pagequay.errors import PQError


@pytest.mark.parametrize(
    "mode", ["exact", "descendant", "ambiguous", "no_root", "changed", "ancestor"]
)
async def test_shadow_binding_requires_exact_target_and_stable_owner(monkeypatch, mode):
    main = SimpleNamespace(parent_frame=None)
    parent = SimpleNamespace(parent_frame=main)
    frame = SimpleNamespace(
        parent_frame=parent if mode == "ancestor" else main, is_detached=lambda: False
    )
    owner_calls = []

    async def content_frame():
        owner_calls.append(True)
        return object() if mode == "changed" and len(owner_calls) >= 3 else frame

    owner = SimpleNamespace(content_frame=content_frame)

    async def dispose():
        pass

    owner.dispose = dispose

    async def element():
        return owner

    frame.frame_element = element
    calls = []

    class Session:
        def on(self, name, callback):
            self.callback = callback

        async def detach(self):
            pass

        async def send(self, method, params=None):
            calls.append(method)
            if method == "Runtime.enable":
                for name in (
                    ["one", "two"]
                    if mode == "ambiguous"
                    else ["local", "one"]
                    if mode == "descendant"
                    else ["one"]
                ):
                    self.callback({"context": {"auxData": {"isDefault": True, "frameId": name}}})
                return {}
            if method == "DOM.getFrameOwner":
                if mode == "no_root" or params["frameId"] == "local":
                    return {"backendNodeId": 3}
                raise Error("Frame with the given id does not belong to the target.")
            if method == "Page.createIsolatedWorld":
                return {"executionContextId": 1}
            if params["functionDeclaration"] == "function() { return true; }":
                return {"result": {"value": True}}
            return {"result": {"value": json.dumps({"value": {"title": "exact"}})}}

    session = Session()

    async def new_session(target):
        if mode == "ancestor" and target == frame:
            raise Error("does not have a separate CDP session")
        return session

    async def path(target):
        raise PQError(
            "UNAVAILABLE",
            "Frame owner not present in current DOM",
            503,
            details={"cause": "WORLD_NOT_FOUND"},
        )

    monkeypatch.setattr(page_reader, "frame_path", path)
    page = SimpleNamespace(main_frame=main, context=SimpleNamespace(new_cdp_session=new_session))
    if mode in ["exact", "descendant"]:
        assert await page_reader.isolated_read(
            page, "fixed_read", {}, frame=frame, max_bytes=1000
        ) == {"title": "exact"}
    else:
        with pytest.raises(PQError) as raised:
            await page_reader.isolated_read(page, "fixed_read", {}, frame=frame, max_bytes=1000)
        assert raised.value.code == ("NAVIGATION_CHANGED" if mode == "changed" else "UNAVAILABLE")
        if mode in ["ambiguous", "no_root", "ancestor"]:
            assert "Page.createIsolatedWorld" not in calls
