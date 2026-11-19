"""Secure handling of uploaded files: validate, then store under a random name outside any web root."""

import hashlib
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from rest_framework import serializers

ALLOWED = {".csv", ".xlsx"}
FORBIDDEN_MAGIC = (
    b"%PDF",
    b"MZ",
    b"\x7fELF",
    b"\x89PNG",
    b"GIF8",
    b"\xff\xd8\xff",
    b"#!",
    b"<?php",
    b"<html",
    b"<!DOC",
)


@dataclass
class StoredUpload:
    path: str
    extension: str
    sha256: str
    size: int
    original_name: str
    encoding: str


def _reject(message: str) -> serializers.ValidationError:
    return serializers.ValidationError({"file": message})


def _clean_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    return "".join(c for c in base if c.isprintable() and c not in '<>:"|?*')[:200] or "upload"


def store_upload(uploaded) -> StoredUpload:  # noqa: ANN001
    """Validate and persist. Raises ValidationError (400) and leaves nothing on disk if the file is rejected."""
    original = _clean_name(uploaded.name or "")
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED:
        raise _reject("Only .csv and .xlsx files are accepted.")
    limit = settings.IMPORT_MAX_CSV_BYTES if ext == ".csv" else settings.IMPORT_MAX_XLSX_BYTES
    if uploaded.size is not None and uploaded.size > limit:
        raise _reject(f"File is larger than the {limit // (1024 * 1024)} MB limit for {ext} files.")
    if uploaded.size == 0:
        raise _reject("File is empty.")

    target_dir = Path(settings.MEDIA_ROOT) / settings.IMPORT_STORAGE_SUBDIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid.uuid4().hex}{ext}"  # random name: the client's filename never touches the disk
    sha, size = hashlib.sha256(), 0
    try:
        with open(path, "wb") as out:
            for block in uploaded.chunks():
                size += len(block)
                if size > limit:
                    raise _reject("File exceeds the size limit.")
                sha.update(block)
                out.write(block)
        encoding = _check_content(path, ext)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return StoredUpload(str(path), ext, sha.hexdigest(), size, original, encoding)


def _check_content(path: Path, ext: str) -> str:
    with open(path, "rb") as fh:
        head = fh.read(65536)
    if ext == ".xlsx":
        if not head.startswith(b"PK\x03\x04") or not zipfile.is_zipfile(path):
            raise _reject("File is not a valid .xlsx workbook.")
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise _reject("File is not a valid .xlsx workbook.")
            if sum(i.file_size for i in zf.infolist()) > settings.IMPORT_MAX_XLSX_UNCOMPRESSED:
                raise _reject("Workbook expands to an unreasonable size.")
        return "utf-8-sig"
    if head.startswith(FORBIDDEN_MAGIC) or head.startswith(b"PK\x03\x04") or b"\x00" in head:
        raise _reject("File does not look like a text CSV.")
    try:
        head.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError as exc:
        if len(head) == 65536 and exc.start >= len(head) - 4:  # multi-byte char cut by the sample boundary
            return "utf-8-sig"
        return "latin-1"
