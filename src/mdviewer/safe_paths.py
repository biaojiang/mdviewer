"""Open document paths without following links, including during replacement races."""
from contextlib import contextmanager, ExitStack
import errno
import os
import stat
import weakref
from functools import lru_cache

_ROOTS = weakref.WeakSet()


class OpenedPath:
    def __init__(self, fd, directory_path=None):
        self.fd = fd
        self.directory_path = directory_path
        self.is_dir = directory_path is not None or stat.S_ISDIR(os.fstat(fd).st_mode)

    def entries(self):
        location = self.directory_path if self.directory_path is not None else self.fd
        for name in sorted(os.listdir(location)):
            try:
                if self.directory_path is not None:
                    info = os.lstat(os.path.join(self.directory_path, name))
                else:
                    info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                continue
            if stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode):
                yield name, stat.S_ISDIR(info.st_mode)

    def binary_stream(self):
        if self.is_dir:
            raise IsADirectoryError()
        return os.fdopen(os.dup(self.fd), 'rb')


def _parts(relative):
    # Reject aliases rather than normalizing away unsafe components.
    if '\x00' in relative or os.path.isabs(relative) or (os.name == 'nt' and '\\' in relative):
        raise PermissionError('Invalid document path')
    parts = relative.split('/') if relative else []
    if any(part in ('', '.', '..') or (os.name == 'nt' and ':' in part) for part in parts):
        raise PermissionError('Invalid document path')
    return parts


@contextmanager
def _windows_path(root, parts):
    """Hold non-delete-shared handles so checked ancestors cannot be replaced."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    attributes = kernel.GetFileInformationByHandleEx
    attributes.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]

    with ExitStack() as stack:
        path = root
        final = None
        is_dir = True
        for index, component in enumerate([None] + parts):
            if component is not None:
                path = os.path.join(path, component)
            # OPEN_REPARSE_POINT prevents dereferencing the final component.
            handle = create(path, 0x80000000, 0x1 | 0x2, None, 3,
                            0x02000000 | 0x00200000, None)
            if handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            stack.callback(close, handle)
            info = AttributeTagInfo()
            if not attributes(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.attributes & 0x400:
                raise PermissionError('Reparse points are not served')
            is_dir = bool(info.attributes & 0x10)
            if index < len(parts) and not is_dir:
                raise NotADirectoryError(path)
            final = handle
        if is_dir:
            yield OpenedPath(None, path)
        else:
            # Duplicate the HANDLE before transferring ownership to the CRT.
            duplicate = kernel.DuplicateHandle
            duplicate.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                  ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                  wintypes.BOOL, wintypes.DWORD]
            process = kernel.GetCurrentProcess
            process.restype = wintypes.HANDLE
            copied = wintypes.HANDLE()
            if not duplicate(process(), final, process(), ctypes.byref(copied), 0, False, 2):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                fd = msvcrt.open_osfhandle(copied.value, os.O_RDONLY | os.O_BINARY)
            except Exception:
                close(copied)
                raise
            stack.callback(os.close, fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise PermissionError("Only regular files are served")
            yield OpenedPath(fd)


class DocumentRoot:
    """Pin the operator-selected root once, before serving any requests."""
    def __init__(self, path):
        self.path = os.path.realpath(path)
        self.stack = ExitStack()
        if os.name == 'nt':
            self.stack.enter_context(_windows_path(self.path, []))
            self.fd = None
        else:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.stack.callback(os.close, self.fd)
        self.finalizer = weakref.finalize(self, self.stack.close)
        _ROOTS.add(self)

    def close(self):
        self.finalizer()


@lru_cache(maxsize=8)
def document_root(root):
    return DocumentRoot(root)


def close_document_roots():
    """Release retained directory handles when a server or test shuts down."""
    for root in list(_ROOTS):
        root.close()
    document_root.cache_clear()


@contextmanager
def open_document(root, relative=''):
    parts = _parts(relative)
    pinned = document_root(os.fspath(root))
    if os.name == 'nt':
        with _windows_path(pinned.path, parts) as opened:
            yield opened
        return
    with ExitStack() as stack:
        fd = os.dup(pinned.fd)
        stack.callback(os.close, fd)
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts) - 1:
                flags |= os.O_DIRECTORY
            try:
                fd = os.open(part, flags, dir_fd=fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise PermissionError('Links are not served') from exc
                raise
            stack.callback(os.close, fd)
        mode = os.fstat(fd).st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise PermissionError('Only regular files and directories are served')
        yield OpenedPath(fd)
