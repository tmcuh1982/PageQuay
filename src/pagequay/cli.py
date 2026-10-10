import argparse
import getpass
import os
import sys

import uvicorn

from .auth import PASSWORDS, strong_password
from .settings import Settings
from .storage import Storage, uid


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(prog="pq", description="PageQuay local browser gateway")
    parser.add_argument("command", choices=["init-admin", "migrate", "serve", "doctor"])
    args = parser.parse_args()
    settings = Settings()
    if args.command == "serve":
        from .main import create_app

        uvicorn.run(
            create_app(settings),
            host="127.0.0.1",
            port=settings.port,
            workers=1,
            proxy_headers=False,
            access_log=False,
            ws_max_size=16384,
            ws_ping_interval=20,
            ws_ping_timeout=20,
        )
        return
    db = Storage(settings.data_dir)
    try:
        if args.command == "init-admin":
            if db.one("SELECT id FROM admins LIMIT 1"):
                raise SystemExit("An administrator already exists; initialization refused.")
            if not sys.stdin.isatty():
                raise SystemExit(
                    "Interactive terminal required; no passwords in command arguments."
                )
            username = input("Administrator username: ").strip()
            if not username or len(username) > 100:
                raise SystemExit("Invalid username")
            password = getpass.getpass("Password (14+ characters): ")
            try:
                strong_password(password)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if password != getpass.getpass("Confirm password: "):
                raise SystemExit("Passwords differ")
            db.execute(
                "INSERT INTO admins VALUES (?,?,?)", (uid(), username, PASSWORDS.hash(password))
            )
            db.audit("admin.initialized")
            print("Administrator created. Start with pq serve.")
        elif args.command == "migrate":
            print("Schema ready; numbered migrations applied.")
        else:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                from pathlib import Path

                executable = Path(playwright.chromium.executable_path)
                print(
                    "Chromium:",
                    "installed" if executable.exists() else "MISSING: playwright install chromium",
                )
            print("Data directory:", db.root)
            print(
                "Administrator:",
                "initialized"
                if db.one("SELECT id FROM admins LIMIT 1")
                else "MISSING: pq init-admin",
            )
            print("Listener:", f"127.0.0.1:{settings.port}")
            print("Headed browser requires an open macOS graphical user session.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
