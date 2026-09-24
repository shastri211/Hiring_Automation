import os
import re
import uuid
import aiofiles
import hashlib
from typing import BinaryIO, Callable, Tuple
from fastapi import UploadFile
from app.core.config import settings

# Strip any directory components and characters that aren't safe in a
# filesystem path segment, so a hostile `file.filename` (e.g. "../../x",
# an absolute path, or embedded null/control bytes) can never escape the
# intended upload directory. See also get_secure_path(), which guards reads.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str | None, fallback_ext: str = "") -> str:
    """Return a filesystem-safe basename, never empty and never a path."""
    name = os.path.basename((filename or "").strip().replace("\\", "/"))
    name = name.lstrip(".")  # also blocks bare ".." after basename/lstrip
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    if not name:
        name = f"{uuid.uuid4().hex}{fallback_ext}"
    return name


def make_unique_basename(basename: str, used: set) -> str:
    """Disambiguate a basename against every one already used within the
    same upload/prefix. Two different source files (different ZIP folders,
    or two direct-upload files with the same original filename) can
    sanitize to the same basename - without this, the second one would
    silently overwrite the first's file on disk before either Resume row
    is inserted, corrupting the first candidate's stored file with the
    second's content while its DB row still shows its own file_hash."""
    if basename not in used:
        used.add(basename)
        return basename
    stem, ext = os.path.splitext(basename)
    n = 2
    while f"{stem}_{n}{ext}" in used:
        n += 1
    candidate = f"{stem}_{n}{ext}"
    used.add(candidate)
    return candidate


class StorageService:
    def __init__(self):
        self.base_dir = settings.STORAGE_LOCAL_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    async def save_file(self, file: UploadFile, prefix: str = "", filename_override: str | None = None) -> str:
        """Saves file to local filesystem and returns the storage key.

        `filename_override` lets a caller handling multiple files under the
        same prefix (e.g. one upload request) pass an already-disambiguated
        basename (see make_unique_basename) instead of the raw sanitized
        filename, which two different uploads can collide on.
        """
        filename = filename_override if filename_override is not None else sanitize_filename(file.filename)
        storage_key = os.path.join(prefix, filename)
        full_path = os.path.join(self.base_dir, storage_key)

        # Ensure dir exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        await file.seek(0)
        async with aiofiles.open(full_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)
                
        return storage_key

    async def compute_hash(self, file: UploadFile) -> str:
        """Computes SHA-256 hash of the file for duplicate detection."""
        await file.seek(0)
        sha256_hash = hashlib.sha256()
        while chunk := await file.read(4096):
            sha256_hash.update(chunk)
        await file.seek(0)
        return sha256_hash.hexdigest()

    async def save_stream(
        self, read_chunk: Callable[[], bytes], filename: str, prefix: str, max_bytes: int
    ) -> Tuple[str, str, int]:
        """Streams into storage from `read_chunk` (a zero-arg callable
        returning up to a chunk's worth of bytes, empty bytes at EOF - e.g.
        `functools.partial(some_stream.read, 1MB)`), hashing incrementally
        in the same pass rather than the two-pass read-then-save approach
        save_file()/compute_hash() use for an UploadFile's seekable spooled
        buffer. Used by app/services/zip_ingest.py, whose source (a zip
        member's decompression stream) generally can't be seeked back to
        the start the way an UploadFile can.

        Enforces max_bytes DURING streaming - not just against whatever
        size a caller may have observed beforehand, which can be spoofed
        (e.g. a zip entry's declared, but not authoritative, header size) -
        and deletes the partial file before raising if the cap is exceeded
        or read_chunk itself raises, so a rejected/failed stream never
        leaves a partial file behind.

        Returns (storage_key, sha256_hex, total_bytes_written).
        """
        filename = sanitize_filename(filename)
        storage_key = os.path.join(prefix, filename)
        full_path = os.path.join(self.base_dir, storage_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        sha256_hash = hashlib.sha256()
        total = 0
        try:
            async with aiofiles.open(full_path, "wb") as out_file:
                while True:
                    chunk = read_chunk()
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"Stream exceeded the {max_bytes}-byte cap")
                    sha256_hash.update(chunk)
                    await out_file.write(chunk)
        except Exception:
            try:
                os.remove(full_path)
            except OSError:
                pass
            raise

        return storage_key, sha256_hash.hexdigest(), total

    def get_secure_path(self, storage_key: str) -> str:
        """Returns an absolute path if it is safely inside base_dir, else None."""
        full_path = os.path.abspath(os.path.join(self.base_dir, storage_key))
        if not full_path.startswith(os.path.abspath(self.base_dir)):
            return None
        return full_path

    def delete_file(self, storage_key: str) -> bool:
        """Best-effort removal of a stored file, confined to base_dir via
        get_secure_path. Returns True if a file was removed. Only for files
        no DB row references (e.g. the loser of a concurrent duplicate
        insert race) - never for a live Resume's file."""
        full_path = self.get_secure_path(storage_key)
        if not full_path:
            return False
        try:
            os.remove(full_path)
            return True
        except OSError:
            return False

storage_service = StorageService()
