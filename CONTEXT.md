# Report Management

This context describes capacity report records, generated DOCX files, uploaded revisions, and AI audit results for report review workflows.

## Language

**Report Record**:
A report identity for one system, title, and report month. It is uniquely identified by `systemId`, `title`, and `report_month`.
_Avoid_: Batch report, file record

**Report Version**:
A concrete DOCX file belonging to a Report Record. The initial generated file and every later user upload are separate versions.
_Avoid_: Replacement file, overwritten report

**Initial Report**:
The first Report Version created by the scheduled backend batch process.
_Avoid_: Original file, batch file

**Uploaded Report**:
A later Report Version uploaded by a user after manually revising a previous report.
_Avoid_: Updated file, modified file

**Revision Cycle**:
The repeated process of uploading a new Report Version after an AI Audit Record does not pass. A Report Record may have many uploaded versions until the latest version passes audit.
_Avoid_: Single reupload, overwrite flow

**Post-Pass Upload**:
A new Uploaded Report created after the latest version has already passed audit. It becomes the latest version and returns the Report Record to an auditing state.
_Avoid_: Locked passed report, final report

**AI Audit Record**:
An audit result produced by the configured model for a specific Report Version. Every record is explicitly classified as an Initial Audit or Revision Audit; multiple records may exist for one version, and the UI normally shows the latest one.
_Avoid_: Review result, validation result

**Initial Audit**:
An AI Audit Record created for an Initial Report. It uses the Initial Audit Prompt and checks language quality, directory and heading consistency, and basic document completeness.
_Avoid_: First pass, batch audit

**Revision Audit**:
An AI Audit Record created for an Uploaded Report. It uses the Revision Audit Prompt for performance-capacity analysis and does not repeat Initial Audit checks.
_Avoid_: Re-audit, secondary audit, uploaded audit

**Latest Audit Result**:
The most recent AI Audit Record for the latest Report Version of a Report Record. The report list uses this result by default.
_Avoid_: Initial audit result, report status

**AI Audit Service**:
A backend service capability that accepts a Report Version and creates an AI Audit Record for it.
_Avoid_: DeepSeek service, report checker

**Audit Prompt**:
One of two independently versioned instruction sets used by the AI Audit Service: the Initial Audit Prompt or Revision Audit Prompt. Both use the same model connection configuration.
_Avoid_: Hard-coded prompt, audit rule text

**Audit Scope**:
The part of a Report Version that the AI Audit Service is expected to judge. The first version covers DOCX text, tables, and document structure, but does not judge the meaning of images or charts.
_Avoid_: Full document understanding, chart audit
