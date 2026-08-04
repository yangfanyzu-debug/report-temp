# 按文件名查询 DOCX 接口

## 接口说明

根据文件名查询服务器中已上传的 DOCX 文档。文件名支持模糊匹配；传入完整文件名时，由于同名文件上传会覆盖，通常只返回一条记录。

## 请求信息

- 请求方法：`GET`
- 生产地址：`http://110.42.239.253/report-docx-api/files`
- Content-Type：无需设置
- 是否需要登录：否

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | string | 是 | DOCX 文件名，支持完整文件名或部分名称模糊匹配 |

分页参数 `pageNum` 和 `pageSize` 可以不传。未传时默认查询第 1 页，每页最多返回 10 条记录。

## Python requests 调用示例

推荐通过 `params` 传递文件名，`requests` 会自动处理中文 URL 编码：

```python
import requests


url = "http://110.42.239.253/report-docx-api/files"
params = {
    "filename": "02_系统容量评估报告.docx"
}

response = requests.get(url, params=params, timeout=10)
response.raise_for_status()

result = response.json()
print(result)
```

按部分文件名模糊查询：

```python
import requests


response = requests.get(
    "http://110.42.239.253/report-docx-api/files",
    params={"filename": "容量评估"},
    timeout=10,
)
response.raise_for_status()

print(response.json())
```

不要直接将未编码的中文文件名拼接到 URL 中。以下写法可能导致中文乱码并返回空结果：

```python
# 错误示例
requests.get(
    "http://110.42.239.253/report-docx-api/files?filename=系统容量评估报告.docx"
)
```

## curl 调用示例

```bash
curl -G \
  --data-urlencode 'filename=02_系统容量评估报告.docx' \
  'http://110.42.239.253/report-docx-api/files'
```

## 成功响应

HTTP 状态码：`200 OK`

```json
{
  "rows": [
    {
      "name": "02_系统容量评估报告.docx",
      "uploader": "若依",
      "size": 72314,
      "sizeDisplay": "70.6 KB",
      "updatedAt": "2026-08-04T09:13:12.871581+00:00",
      "uploadedAt": "2026-08-04T09:13:12.872833+00:00",
      "previewUrl": "/report-docx-api/files/02_%E7%B3%BB%E7%BB%9F%E5%AE%B9%E9%87%8F%E8%AF%84%E4%BC%B0%E6%8A%A5%E5%91%8A.docx/preview",
      "downloadUrl": "/report-docx-api/files/02_%E7%B3%BB%E7%BB%9F%E5%AE%B9%E9%87%8F%E8%AF%84%E4%BC%B0%E6%8A%A5%E5%91%8A.docx/download"
    }
  ],
  "total": 1
}
```

## 未查询到文件

接口仍返回 `200 OK`，`rows` 为空数组，`total` 为 `0`：

```json
{
  "rows": [],
  "total": 0
}
```

## 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rows` | array | 当前查询结果列表 |
| `total` | integer | 符合条件的文件总数 |
| `rows[].name` | string | 完整文件名 |
| `rows[].uploader` | string | 上传人 |
| `rows[].size` | integer | 文件大小，单位为字节 |
| `rows[].sizeDisplay` | string | 便于阅读的文件大小 |
| `rows[].updatedAt` | string | 文件更新时间，ISO 8601 格式 |
| `rows[].uploadedAt` | string或null | 上传时间，ISO 8601 格式 |
| `rows[].previewUrl` | string | 在线预览地址 |
| `rows[].downloadUrl` | string | 文件下载地址 |

## 使用注意事项

1. 当前仅支持查询 `.docx` 文件。
2. 使用完整文件名查询时，应包含 `.docx` 扩展名。
3. 中文文件名必须进行 URL 编码；Python `requests` 使用 `params` 参数即可自动编码。
4. `filename` 使用模糊匹配。例如传入 `报告`，可能返回多份包含“报告”的文件。
5. 未找到文件不会返回 `404`，应通过 `total == 0` 或 `rows` 是否为空判断。
