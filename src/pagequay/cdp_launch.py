"""Keep Playwright's persistent-context setup, with a loopback CDP port on Chrome.

Playwright owns this relay as its executable. Only the relay uses its pipe;
Chrome receives a nonzero debugging port and never inherits the pipe descriptors.
"""

import json
import os
import queue
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from websockets.sync.client import connect

MAX_MESSAGE = 128 * 1024 * 1024


def browser_executable(chromium, channel):
    if channel == "chrome":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return chromium.executable_path


@contextmanager
def launch_executable(root, executable):
    """A private, per-launch wrapper; shell quoting handles paths containing spaces."""
    directory = root / "runtime"
    directory.mkdir(mode=0o700, exist_ok=True)
    code = (
        f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r}); "
        f"from pagequay.cdp_launch import main; sys.exit(main({str(executable)!r}))"
    )
    fd, name = tempfile.mkstemp(prefix="cdp-launch-", suffix=".sh", dir=directory)
    try:
        with os.fdopen(fd, "w") as wrapper:
            wrapper.write(
                f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(code)} "$@"\n'
            )
        os.chmod(name, 0o700)
        yield name
    finally:
        Path(name).unlink(missing_ok=True)


def port_arguments(arguments, port):
    if not 1024 <= port <= 65535:
        raise ValueError("CDP requires an explicit unprivileged port")
    if "--remote-debugging-pipe" not in arguments:
        raise ValueError("Unexpected Playwright transport")
    if any(
        arg.startswith(("--remote-debugging-port", "--remote-debugging-address"))
        for arg in arguments
    ):
        raise ValueError("Conflicting CDP transport")
    return [
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        *(arg for arg in arguments if arg != "--remote-debugging-pipe"),
    ]


def validate_endpoint(endpoint, port):
    url = urlsplit(endpoint)
    if (
        url.scheme != "ws"
        or url.hostname != "127.0.0.1"
        or url.port != port
        or url.username is not None
        or url.password is not None
        or not url.path.startswith("/devtools/browser/")
        or not url.path.removeprefix("/devtools/browser/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Unexpected Chrome CDP endpoint")
    return endpoint


def pipe_to_socket(connection, fd):
    pending = bytearray()
    try:
        while chunk := os.read(fd, 65536):
            pending.extend(chunk)
            while (end := pending.find(0)) >= 0:
                if end > MAX_MESSAGE:
                    raise ValueError("CDP message too large")
                connection.send(bytes(pending[:end]).decode("utf-8"))
                del pending[: end + 1]
            if len(pending) > MAX_MESSAGE:
                raise ValueError("CDP message too large")
    except Exception:
        # EOF, malformed input or transport failure all close the owned browser.
        pass
    finally:
        connection.close()


class StartupConnection:
    """Buffer the initial handshake, but honor shutdown before Chrome is ready."""

    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.lock = threading.Lock()
        self.connection = None
        self.pending = []
        self.size = 0
        self.closed = False

    def send(self, message):
        with self.lock:
            if self.closed:
                raise BrokenPipeError("Relay closed")
            if self.connection is not None:
                self.connection.send(message)
                return
            if len(message) < 1024 and json.loads(message).get("method") == "Browser.close":
                self.closed = True
                self.endpoints.put(None)
                return
            self.size += len(message.encode("utf-8"))
            if self.size > MAX_MESSAGE:
                raise ValueError("CDP startup buffer too large")
            self.pending.append(message)

    def attach(self, connection):
        with self.lock:
            if self.closed:
                raise BrokenPipeError("Relay closed before CDP was ready")
            self.connection = connection
            for message in self.pending:
                connection.send(message)
            self.pending.clear()

    def close(self):
        with self.lock:
            self.closed = True
            self.endpoints.put(None)
            connection = self.connection
        if connection is not None:
            connection.close()


def socket_to_pipe(connection, fd):
    for message in connection:
        data = memoryview(
            (message.encode("utf-8") if isinstance(message, str) else message) + b"\0"
        )
        while data:
            written = os.write(fd, data)
            if not written:
                raise BrokenPipeError("Playwright pipe closed")
            data = data[written:]


def main(executable):
    child = None

    def stop(_signum, _frame):
        raise SystemExit(1)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    try:
        # Reserve a candidate, then let Chrome bind it. A collision fails closed:
        # we connect only to the endpoint announced on our own child's stderr.
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        arguments = port_arguments(sys.argv[1:], port)
        try:
            child = subprocess.Popen(
                [executable, *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                close_fds=True,
            )
        except FileNotFoundError:
            print("PAGEQUAY_BROWSER_EXECUTABLE_MISSING", file=sys.stderr, flush=True)
            return 1
        endpoints = queue.Queue()

        def read_stderr():
            for line in child.stderr:
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
                if line.startswith(b"DevTools listening on "):
                    endpoints.put(line.decode().strip().removeprefix("DevTools listening on "))
            endpoints.put(None)

        threading.Thread(target=read_stderr, daemon=True).start()
        startup = StartupConnection(endpoints)
        threading.Thread(target=pipe_to_socket, args=(startup, 3), daemon=True).start()
        endpoint = endpoints.get(timeout=30)
        if endpoint is None or child.poll() is not None:
            raise RuntimeError("Chrome exited before CDP was ready")
        endpoint = validate_endpoint(endpoint, port)
        with connect(
            endpoint,
            proxy=None,
            compression=None,
            ping_interval=None,
            max_size=MAX_MESSAGE,
            open_timeout=10,
            close_timeout=1,
        ) as connection:
            startup.attach(connection)
            socket_to_pipe(connection, 4)
        return 0
    except Exception as error:
        # CDP contents and URLs aren't included in relay diagnostics.
        print(f"PAGEQUAY_CDP_RELAY_FAILED: {type(error).__name__}", file=sys.stderr, flush=True)
        return 1
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            with suppress(OSError):
                child.stderr.close()
