# Report Management Module

This folder is reserved for the new report management feature so it can be developed without changing the existing DOCX file service layout.

## Scope

- RuoYi-Cloud `ruoyi-ui` menu page integration notes and frontend source handoff.
- Python backend for report records, versions, uploads, preview, download, DOCX extraction, and asynchronous AI audit.
- Database migration drafts for `capability_report_log` extension and new report version, audit, and audit prompt tables.
- DeepSeek integration placeholders until the model URL and key are provided.

## Constraints

- Do not modify the existing `backend/` file service unless the change is explicitly needed and confirmed.
- Keep initial AI audit scope to DOCX text, tables, and document structure.
- Do not process image or chart semantics in the first version.
- Preserve every report version instead of overwriting uploaded files.

## Backend Status

The isolated backend skeleton lives in `backend/`.

Implemented so far:

- Flask app factory and `/health`.
- Environment-based configuration placeholders for MySQL and DeepSeek.
- DOCX structure validation helper.
- DOCX text/table extraction helper.
- Versioned server filename generation that does not reuse same-name replacement behavior.
- PyMySQL database connection wrapper.
- Report list and detail API routes.
- MySQL report repository for the read-side queries.
- Batch initial report registration route.
- Versioned DOCX upload route.
- Version preview and download routes.
- Audit detail route.
- Active audit prompt route.
- Versioned audit prompt creation route.
- Audit input assembly from DOCX text, tables, and report metadata.
- Single-run audit worker framework.
- Long-running audit worker entrypoint.
- Ark/OpenAI-compatible model client placeholder with JSON response parsing and validation.
- Deployment drafts for systemd and Nginx.
- Foundation tests for the above.

Not implemented yet:

- Ark model API key configuration and live integration test.

## Model Configuration

The backend defaults to the Ark Coding OpenAI-compatible base URL and model name:

```bash
export ARK_API_URL="https://ark.cn-beijing.volces.com/api/coding/v3"
export ARK_MODEL="ark-code-latest"
export ARK_API_KEY="<set outside git>"
```

`DEEPSEEK_API_URL`, `DEEPSEEK_MODEL`, and `DEEPSEEK_API_KEY` are still accepted as backward-compatible aliases.

## Local Backend Commands

```bash
cd report-management/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python run.py
.venv/bin/python run_worker.py
.venv/bin/python run_worker.py --once
```

## Frontend Status

RuoYi UI source handoff files live in `frontend/ruoyi-ui/`.

Implemented so far:

- Report list page.
- Report detail page.
- DOCX preview page using `@vue-office/docx`.
- Audit prompt configuration page.
- RuoYi API modules.
- Route snippet and menu SQL draft.

The files are staged in this module for migration into the real RuoYi-Cloud `ruoyi-ui` project.
