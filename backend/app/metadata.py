from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock


METADATA_FILENAME = ".documents.json"
metadata_lock = Lock()


def load_metadata(storage_dir: Path) -> dict[str, dict[str, str]]:
    path = storage_dir / METADATA_FILENAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_document_metadata(storage_dir: Path, filename: str, uploader: str, uploaded_at: str) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    with metadata_lock:
        metadata = load_metadata(storage_dir)
        metadata[filename] = {"uploader": uploader, "uploadedAt": uploaded_at}

        descriptor, temporary_name = tempfile.mkstemp(prefix=".metadata-", suffix=".json", dir=storage_dir)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(metadata, stream, ensure_ascii=False, indent=2)
            os.replace(temporary_path, storage_dir / METADATA_FILENAME)
        finally:
            temporary_path.unlink(missing_ok=True)
