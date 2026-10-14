import asyncio
import os
import socket
import threading
from pathlib import Path

import pytest
from playwright.async_api import TimeoutError, async_playwright

from pagequay.cdp_launch import (
    browser_executable,
    launch_executable,
    pipe_to_socket,
    port_arguments,
    socket_to_pipe,
    validate_endpoint,
)


def test_transport_changes_only_debugging_arguments():
    original = [
        "--user-data-dir=/isolated",
        "--remote-debugging-pipe",
        "--proxy-server=local",
        "--disable-quic",
        "about:blank",
    ]
    result = port_arguments(original, 12345)
    assert result[:2] == ["--remote-debugging-port=12345", "--remote-debugging-address=127.0.0.1"]
    assert result[2:] == [arg for arg in original if arg != "--remote-debugging-pipe"]
    for port in (0, 80, 65536):
        with pytest.raises(ValueError):
            port_arguments(original, port)
    with pytest.raises(ValueError):
        port_arguments(original + ["--remote-debugging-port=1234"], 12345)
    with pytest.raises(ValueError):
        port_arguments(["about:blank"], 12345)


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://localhost:12345/devtools/browser/a",
        "ws://192.168.1.1:12345/devtools/browser/a",
        "ws://127.0.0.1:54321/devtools/browser/a",
        "ws://user@127.0.0.1:12345/devtools/browser/a",
        "ws://127.0.0.1:12345/devtools/page/a",
        "ws://127.0.0.1:12345/devtools/browser/",
        "wss://127.0.0.1:12345/devtools/browser/a",
        "ws://127.0.0.1:12345/devtools/browser/a?q=1",
    ],
)
def test_endpoint_must_be_own_loopback_browser(endpoint):
    with pytest.raises(ValueError):
        validate_endpoint(endpoint, 12345)


def test_endpoint_and_wrapper_cleanup(tmp_path):
    assert validate_endpoint("ws://127.0.0.1:12345/devtools/browser/a", 12345)
    with (
        pytest.raises(RuntimeError),
        launch_executable(tmp_path, "/path with spaces/Chrome") as name,
    ):
        assert Path(name).stat().st_mode & 0o777 == 0o700
        raise RuntimeError("cancelled")
    assert not Path(name).exists()


def test_fragmented_pipe_frames_and_eof():
    messages = []
    closed = threading.Event()

    class Connection:
        def send(self, message):
            messages.append(message)

        def close(self):
            closed.set()

    reader, writer = os.pipe()
    thread = threading.Thread(target=pipe_to_socket, args=(Connection(), reader))
    thread.start()
    try:
        os.write(writer, b'{"id":')
        os.write(writer, '1,"text":"été"}\0{"id":2}\0'.encode())
        os.close(writer)
        thread.join(2)
        assert not thread.is_alive()
        assert messages == ['{"id":1,"text":"été"}', '{"id":2}']
        assert closed.is_set()
    finally:
        os.close(reader)


def test_socket_frames_preserved_on_pipe():
    reader, writer = os.pipe()
    try:
        socket_to_pipe(iter(['{"id":1}', '{"method":"event"}']), writer)
        assert os.read(reader, 4096) == b'{"id":1}\0{"method":"event"}\0'
    finally:
        os.close(reader)
        os.close(writer)


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Requires browser")
@pytest.mark.parametrize("channel", ["chromium", "chrome"])
async def test_real_port_and_browser_cleanup(tmp_path, channel):
    async with async_playwright() as playwright:
        executable = browser_executable(playwright.chromium, channel)
        with launch_executable(tmp_path, executable) as launcher:
            context = await playwright.chromium.launch_persistent_context(
                str(tmp_path / "separate profile"),
                executable_path=launcher,
                channel=channel,
                headless=True,
                chromium_sandbox=True,
                accept_downloads=False,
                service_workers="block",
                permissions=[],
            )
        try:
            session = await context.browser.new_browser_cdp_session()
            processes = await session.send("SystemInfo.getProcessInfo")
            pid = next(p["id"] for p in processes["processInfo"] if p["type"] == "browser")
            # Inspect the actual child: explicit ports need not write DevToolsActivePort.
            import subprocess

            arguments = await asyncio.to_thread(
                subprocess.check_output, ["ps", "-p", str(pid), "-o", "command="], text=True
            )
            assert "--remote-debugging-pipe" not in arguments
            port = int(arguments.split("--remote-debugging-port=", 1)[1].split()[0])
            assert port > 0
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                pass
        finally:
            await context.close()
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Chrome survived context.close()")
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1)
        assert not list((tmp_path / "runtime").iterdir())


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Requires Playwright")
async def test_real_startup_timeout_cleans_child(tmp_path):
    fake = tmp_path / "browser"
    pid_file = tmp_path / "pid"
    fake.write_text(f'#!/bin/sh\necho $$ > "{pid_file}"\nexec /bin/sleep 60\n')
    fake.chmod(0o700)
    async with async_playwright() as playwright:
        with launch_executable(tmp_path, fake) as launcher:
            with pytest.raises(TimeoutError):
                await playwright.chromium.launch_persistent_context(
                    str(tmp_path / "profile"),
                    executable_path=launcher,
                    timeout=1000,
                )
        pid = int(pid_file.read_text())
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Chrome survived failed launch")
