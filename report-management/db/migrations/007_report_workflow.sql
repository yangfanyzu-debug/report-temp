-- Add batch-generation idempotency, JIRA creation state, and report finalization.
-- Compatible with MySQL 5.7 and safe to re-run.

SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS ensure_report_workflow_columns_and_indexes;
DELIMITER $$
CREATE PROCEDURE ensure_report_workflow_columns_and_indexes()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'final_version_id'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `final_version_id` bigint(20) DEFAULT NULL COMMENT '定稿版本ID'
      AFTER `jira_id`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'finalized_at'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `finalized_at` datetime(3) DEFAULT NULL COMMENT '定稿时间'
      AFTER `final_version_id`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'finalized_by'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `finalized_by` varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '定稿确认人'
      AFTER `finalized_at`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'jira_status'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `jira_status` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'not_created' COMMENT 'JIRA创建状态'
      AFTER `finalized_by`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'jira_error'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `jira_error` text COLLATE utf8mb4_bin COMMENT 'JIRA创建错误'
      AFTER `jira_status`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'jira_attempts'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `jira_attempts` int(11) NOT NULL DEFAULT '0' COMMENT 'JIRA创建尝试次数'
      AFTER `jira_error`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'jira_version_id'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `jira_version_id` bigint(20) DEFAULT NULL COMMENT '触发JIRA创建的报告版本ID'
      AFTER `jira_attempts`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND column_name = 'jira_audit_id'
  ) THEN
    ALTER TABLE capability_report_log
      ADD COLUMN `jira_audit_id` bigint(20) DEFAULT NULL COMMENT '触发JIRA创建的初审记录ID'
      AFTER `jira_version_id`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_version'
      AND column_name = 'generation_id'
  ) THEN
    ALTER TABLE capability_report_version
      ADD COLUMN `generation_id` varchar(128) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '批次生成幂等标识'
      AFTER `source`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_version'
      AND index_name = 'uk_report_generation'
  ) THEN
    ALTER TABLE capability_report_version
      ADD UNIQUE KEY `uk_report_generation` (`report_id`, `generation_id`) USING BTREE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND index_name = 'idx_jira_status'
  ) THEN
    ALTER TABLE capability_report_log
      ADD KEY `idx_jira_status` (`jira_status`, `jira_attempts`, `id`) USING BTREE;
  END IF;
END$$
DELIMITER ;

CALL ensure_report_workflow_columns_and_indexes();
DROP PROCEDURE ensure_report_workflow_columns_and_indexes;

UPDATE capability_report_log
SET jira_status = 'created'
WHERE jira_id <> ''
  AND jira_status <> 'created';

SELECT
  (SELECT COUNT(*) FROM capability_report_version WHERE generation_id IS NOT NULL) AS generation_rows,
  (SELECT COUNT(*) FROM capability_report_log WHERE finalized_at IS NOT NULL) AS finalized_rows,
  (SELECT COUNT(*) FROM capability_report_log WHERE jira_id <> '' AND jira_status <> 'created') AS invalid_jira_status_rows;
