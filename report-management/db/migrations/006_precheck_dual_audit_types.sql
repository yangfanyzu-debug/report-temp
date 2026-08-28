SELECT
  (SELECT COUNT(*) FROM capability_report_audit WHERE status = 'running') AS running_audit_rows,
  (SELECT COUNT(*) FROM capability_report_audit_prompt WHERE enabled = 1) AS active_prompt_rows,
  (SELECT COUNT(*)
     FROM capability_report_audit audit
     LEFT JOIN capability_report_version version ON version.id = audit.version_id
    WHERE version.id IS NULL) AS unlinked_audit_rows;
