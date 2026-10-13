import json
from types import SimpleNamespace

import pytest
from playwright.async_api import Error

from pagequay import page_reader
from pagequay.diagnostics import ReadTrace
from pagequay.errors import PQError
from pagequay.models import ContextSelectionDiagnostic


class Session:
    def __init__(self, mode):
        self.mode, self.calls = mode, []

    def on(self, name, callback):
        self.callback = callback

    async def detach(self):
        pass

    async def send(self, method, params=None):
        self.calls.append((method, params))
        if method == "Runtime.enable":
            for frame in ["gone", "main"]:
                self.callback({"context": {"auxData": {"isDefault": True, "frameId": frame}}})
            return {}
        if method == "Page.createIsolatedWorld":
            if params["frameId"] == "gone":
                raise Error(
                    "No frame for given id found" if self.mode == "stale" else "Permission denied"
                )
            return {"executionContextId": 7}
        if params["functionDeclaration"] == page_reader.FRAME_PATH:
            return {"result": {"value": []}}
        if params["functionDeclaration"] == "function() { return true; }":
            return {"result": {"value": True}}
        return {"result": {"value": json.dumps({"value": {"title": "valid"}})}}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["stale", "other"])
async def test_candidate_disappearance_does_not_hide_live_main_document(monkeypatch, mode):
    session = Session(mode)
    frame = SimpleNamespace(is_detached=lambda: False)

    async def new_session(owner):
        return session

    async def path(frame):
        return []

    monkeypatch.setattr(page_reader, "frame_path", path)
    page = SimpleNamespace(main_frame=frame, context=SimpleNamespace(new_cdp_session=new_session))
    if mode == "other":
        with pytest.raises(PQError):
            await page_reader.isolated_read(page, "fixed_reader", {}, max_bytes=1000)
        assert not any(p and p.get("frameId") == "main" for _, p in session.calls)
    else:
        trace = ReadTrace(frame)
        assert await page_reader.isolated_read(
            page, "fixed_reader", {}, max_bytes=1000, trace=trace
        ) == {"title": "valid"}

        assert ContextSelectionDiagnostic.model_validate(trace.selection).stale_candidate_count == 1

        legacy = {k: v for k, v in trace.selection.items() if k != "stale_candidate_count"}
        assert ContextSelectionDiagnostic.model_validate(legacy).stale_candidate_count is None
        for bad in [-1, 129]:
            with pytest.raises(ValueError):
                ContextSelectionDiagnostic.model_validate(
                    {**trace.selection, "stale_candidate_count": bad}
                )
