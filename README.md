# DOCX 文档收件台

一个仅支持 DOCX 文件的轻量文件服务，后端使用 Flask。管理页面已接入独立的 RuoYi-Vue 项目。

## 功能

- 上传有效的 `.docx` 文档，同名文件自动替换
- 查看全部文档，按文件名或上传人模糊查询
- 返回文件大小、上传人、更新时间、预览和下载链接
- 提供 DOCX 二进制预览接口，供 RuoYi 前端在线渲染
- 下载已归档的文档
- 单个文件最大 50 MB

## 本地运行

需要 Python 3.10+ 和 Node.js 18+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/run.py
```

默认文件目录是 `backend/storage/documents/`。如需改变存储位置，可以设置环境变量：

```bash
DOCX_STORAGE_DIR=/absolute/path/to/documents python backend/run.py
```

部署在反向代理后时，可通过 `DOCX_PUBLIC_API_PREFIX` 设置返回给前端的公开 API 前缀，默认是 `/api`。

## API

按文件名查询的独立接口文档见 [docs/query-document-by-filename-api.md](docs/query-document-by-filename-api.md)。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/files/upload` | 使用 multipart/form-data 的 `file` 字段上传文档 |
| `GET` | `/api/files?filename=报告&uploader=张&pageNum=1&pageSize=10` | 全量列表及模糊查询 |
| `GET` | `/api/files/<文件名>/download` | 下载文档 |
| `GET` | `/api/files/<文件名>/preview` | 获取 DOCX 二进制流用于在线查看 |

## 测试

```bash
python -m unittest discover -s backend/tests -v
```

## Docker

```bash
docker build -t docx-file-service .
docker run --rm -p 5000:5000 \
  -e DOCX_STORAGE_DIR=/data/documents \
  -e DOCX_PUBLIC_API_PREFIX=/report-docx-api \
  -v docx_documents:/data/documents \
  docx-file-service
```
