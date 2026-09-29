"""Serialize cooperating local release controllers, not chat or voice work.

The inode is permanent. Never unlink a busy lock. Kernel ownership ends when
the process exits; an interrupted activation still needs explicit recovery.
"""
from contextlib import contextmanager
import fcntl
from functools import wraps
import os
from pathlib import Path
import stat
import threading


_local = threading.local()
_NAME = 'webbob-release.lock'


class Ownership:
    def __init__(self, root):
        self.fd = self.directory = self.parent = None
        self.pid = os.getpid()
        self.thread = threading.get_ident()
        self.parent_path = root / 'conductor'
        self.folder = self.parent_path / 'locks'
        try:
            self.parent_path.mkdir(mode=0o700, exist_ok=True)
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            self.parent = os.open(self.parent_path, directory_flags)
            try:
                os.mkdir('locks', 0o700, dir_fd=self.parent)
            except FileExistsError:
                pass
            self.directory = os.open('locks', directory_flags, dir_fd=self.parent)
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            try:
                self.fd = os.open(_NAME, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=self.directory)
            except FileExistsError:
                self.fd = os.open(_NAME, flags, dir_fd=self.directory)
            self.validate()
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Another Web Bob release or rollback is running. Try again after it finishes.') from None
            self.validate()
        except BaseException:
            self.close()
            raise

    def validate(self):
        if self.pid != os.getpid() or self.thread != threading.get_ident():
            raise RuntimeError('Release ownership belongs to another process or thread')
        file = os.fstat(self.fd)
        named = os.stat(_NAME, dir_fd=self.directory, follow_symlinks=False)
        directory = os.fstat(self.directory)
        current_directory = self.folder.lstat()
        parent = os.fstat(self.parent)
        current_parent = self.parent_path.lstat()
        if (not stat.S_ISREG(file.st_mode) or file.st_nlink != 1 or file.st_uid != os.getuid()
                or file.st_mode & 0o077 or not stat.S_ISREG(named.st_mode)
                or (file.st_dev, file.st_ino) != (named.st_dev, named.st_ino)
                or (directory.st_dev, directory.st_ino) != (current_directory.st_dev, current_directory.st_ino)
                or (parent.st_dev, parent.st_ino) != (current_parent.st_dev, current_parent.st_ino)
                or any(p.st_uid != os.getuid() or p.st_mode & 0o022 for p in (parent, directory))):
            raise RuntimeError('Release ownership file is unsafe or has changed')

    def close(self):
        # Closing, rather than LOCK_UN, cannot unlock a forked parent's shared
        # open-file description. These descriptors are also close-on-exec.
        for name in ('fd', 'directory', 'parent'):
            value = getattr(self, name)
            if value is not None:
                os.close(value)
                setattr(self, name, None)


@contextmanager
def controller(root):
    root = Path(root).resolve()
    held = getattr(_local, 'held', None)
    if held is None:
        held = _local.held = {}
    owner = held.get(root)
    if owner is not None and owner.pid != os.getpid():
        owner.close()
        del held[root]
        owner = None
    if owner is not None:
        owner.validate()
        yield owner
        return
    owner = Ownership(root)
    held[root] = owner
    try:
        yield owner
    finally:
        del held[root]
        owner.close()


def serialized(function):
    """Hold ownership across nested deployment/recovery and evidence writes."""
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        folder = root.root if not isinstance(root, (str, Path)) else root
        with controller(folder):
            return function(root, *args, **kwargs)
    return wrapped
