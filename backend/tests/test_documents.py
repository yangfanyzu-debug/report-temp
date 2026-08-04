from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402


def make_docx(content: str = "document") -> io.BytesIO:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{content}</w:t></w:r></w:p></w:body></w:document>",
        )
    stream.seek(0)
    return stream


class DocumentApiTest(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "STORAGE_DIR": self.storage.name})
        self.client = self.app.test_client()

    def tearDown(self):
        self.storage.cleanup()

    def upload(self, name: str, content: str = "document", uploader: str = "张三"):
        return self.client.post(
            "/api/files/upload",
            data={"file": (make_docx(content), name), "uploader": uploader},
            content_type="multipart/form-data",
        )

    def test_upload_list_preview_and_download(self):
        upload = self.upload("季度报告.docx")
        self.assertEqual(upload.status_code, 201)
        self.assertFalse(upload.json["replaced"])
        self.assertEqual(upload.json["file"]["uploader"], "张三")

        query = self.client.get(
            "/api/files",
            query_string={"filename": "季度", "uploader": "张", "pageNum": 1, "pageSize": 10},
        )
        self.assertEqual(query.status_code, 200)
        self.assertEqual(query.json["total"], 1)
        self.assertEqual(query.json["rows"][0]["name"], "季度报告.docx")
        self.assertTrue(query.json["rows"][0]["downloadUrl"].startswith("http://localhost/api/files/"))
        self.assertTrue(query.json["rows"][0]["previewUrl"].startswith("http://localhost/api/files/"))
        self.assertEqual(query.headers["Cache-Control"], "no-store")

        preview = self.client.get(query.json["rows"][0]["previewUrl"])
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(preview.data)))
        preview.close()

        download = self.client.get(query.json["rows"][0]["downloadUrl"])
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        download.close()

    def test_same_name_replaces_existing_file(self):
        first = self.upload("report.docx", "first")
        second = self.upload("report.docx", "second version", uploader="李四")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json["replaced"])
        self.assertEqual(second.json["file"]["uploader"], "李四")
        self.assertNotEqual(first.json["file"]["size"], second.json["file"]["size"])

        query = self.client.get("/api/files", query_string={"filename": "report.docx"})
        self.assertEqual(query.json["rows"][0]["size"], second.json["file"]["size"])
        with zipfile.ZipFile(Path(self.storage.name) / "report.docx") as archive:
            self.assertIn(b"second version", archive.read("word/document.xml"))

    def test_rejects_wrong_extension_and_invalid_content(self):
        wrong_extension = self.upload("report.pdf")
        self.assertEqual(wrong_extension.status_code, 400)

        invalid_docx = self.client.post(
            "/api/files/upload",
            data={"file": (io.BytesIO(b"not a docx"), "fake.docx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid_docx.status_code, 400)
        self.assertFalse((Path(self.storage.name) / "fake.docx").exists())

    def test_list_returns_all_files_and_supports_empty_result(self):
        self.upload("alpha.docx", uploader="Alice")
        self.upload("beta.DOCX", uploader="Bob")

        all_files = self.client.get("/api/files", query_string={"pageSize": 1})
        self.assertEqual(all_files.status_code, 200)
        self.assertEqual(all_files.json["total"], 2)
        self.assertEqual(len(all_files.json["rows"]), 1)

        missing = self.client.get("/api/files", query_string={"uploader": "Nobody"})
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json, {"rows": [], "total": 0})


if __name__ == "__main__":
    unittest.main()
