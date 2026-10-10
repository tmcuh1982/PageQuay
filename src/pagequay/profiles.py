import fcntl
import shutil

from .errors import PQError


class ProfileLock:
    def __init__(self, root, project_id):
        # Lock outside the resettable profile; kernel releases flock on process death.
        self.path = root / "profiles" / (project_id + ".lock")
        self.handle = None

    def acquire(self):
        self.handle = self.path.open("a+")
        self.path.chmod(0o600)
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise PQError("CONFLICT", "Profile is already in use", 409) from exc

    def release(self):
        if self.handle:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


def reset_directory(root, project_id):
    path = root / "profiles" / project_id
    # Caller IDs come only from SQLite. This also rejects unexpected symlinks.
    if path.is_symlink() or path.resolve().parent != (root / "profiles").resolve():
        raise PQError("CONFLICT", "Unsafe profile path", 409)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(mode=0o700)
