-- Precheck for report management migration on MySQL 5.7 / ry-cloud.
-- Read-only. Safe to run before applying 001_apply_report_management.sql.

SELECT VERSION() AS mysql_version;
SELECT DATABASE() AS current_database;

SELECT COUNT(*) AS capability_report_log_rows
FROM capability_report_log;

SELECT
  systemId,
  title,
  report_month,
  COUNT(*) AS duplicate_count
FROM capability_report_log
GROUP BY systemId, title, report_month
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, systemId, title, report_month;

SELECT
  table_name,
  table_rows
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN (
    'capability_report_log',
    'capability_report_version',
    'capability_report_audit',
    'capability_report_audit_prompt'
  )
ORDER BY table_name;

SELECT
  table_name,
  index_name,
  non_unique,
  GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name IN (
    'capability_report_log',
    'capability_report_version',
    'capability_report_audit',
    'capability_report_audit_prompt'
  )
GROUP BY table_name, index_name, non_unique
ORDER BY table_name, index_name;

SELECT
  COUNT(*) AS report_data_file_rows
FROM capability_report_log
WHERE JSON_UNQUOTE(JSON_EXTRACT(report_data, '$.data')) IS NOT NULL
  AND JSON_UNQUOTE(JSON_EXTRACT(report_data, '$.data')) <> '';

DROP PROCEDURE IF EXISTS precheck_optional_report_management_tables;
DELIMITER $$
CREATE PROCEDURE precheck_optional_report_management_tables()
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_version'
  ) THEN
    SELECT
      COUNT(*) AS existing_initial_versions
    FROM capability_report_version
    WHERE version_no = 1
      AND version_type = 'initial';
  ELSE
    SELECT 'capability_report_version_missing' AS existing_initial_versions;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
  ) THEN
    SELECT
      COUNT(*) AS enabled_prompts
    FROM capability_report_audit_prompt
    WHERE enabled = 1;
  ELSE
    SELECT 'capability_report_audit_prompt_missing' AS enabled_prompts;
  END IF;
END$$
DELIMITER ;
CALL precheck_optional_report_management_tables();
DROP PROCEDURE precheck_optional_report_management_tables;
