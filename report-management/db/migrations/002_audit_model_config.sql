-- Add model endpoint configuration to report audit prompt versions.
-- MySQL 5.7 compatible and safe to re-run.

DROP PROCEDURE IF EXISTS ensure_report_audit_prompt_model_config;
DELIMITER $$
CREATE PROCEDURE ensure_report_audit_prompt_model_config()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
      AND column_name = 'api_url'
  ) THEN
    ALTER TABLE capability_report_audit_prompt
      ADD COLUMN `api_url` varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT 'https://ark.cn-beijing.volces.com/api/coding/v3' COMMENT '大模型API地址'
      AFTER `model_name`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
      AND column_name = 'api_key'
  ) THEN
    ALTER TABLE capability_report_audit_prompt
      ADD COLUMN `api_key` varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '大模型API Key'
      AFTER `api_url`;
  END IF;
END$$
DELIMITER ;
CALL ensure_report_audit_prompt_model_config();
DROP PROCEDURE ensure_report_audit_prompt_model_config;

UPDATE capability_report_audit_prompt
   SET api_url = 'https://ark.cn-beijing.volces.com/api/coding/v3'
 WHERE api_url = '';

SELECT
  COUNT(*) AS prompt_rows,
  SUM(api_url <> '') AS configured_api_url_rows,
  SUM(api_key <> '') AS configured_api_key_rows
FROM capability_report_audit_prompt;
