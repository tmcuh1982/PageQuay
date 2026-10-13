from types import SimpleNamespace

import pytest

from pagequay import structured
from pagequay.errors import PQError


@pytest.mark.asyncio
async def test_global_export_deadline_is_typed_before_any_read(monkeypatch):
    ticks = iter([0, 41])
    monkeypatch.setattr(structured, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    frame = object()
    page = SimpleNamespace(main_frame=frame, frames=[frame])
    with pytest.raises(PQError) as error:
        await structured.extract_structured(page)
    assert error.value.code == "TIMEOUT"
