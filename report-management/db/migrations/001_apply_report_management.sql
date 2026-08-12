-- Apply report management schema on MySQL 5.7 / ry-cloud.
-- Review and run 001_precheck_report_management.sql first.

SET @duplicate_report_identity_count := (
  SELECT COUNT(*)
  FROM (
    SELECT systemId, title, report_month
    FROM capability_report_log
    GROUP BY systemId, title, report_month
    HAVING COUNT(*) > 1
  ) duplicated
);

SET @abort_message := IF(
  @duplicate_report_identity_count > 0,
  CONCAT('Duplicate capability_report_log identity rows exist: ', @duplicate_report_identity_count),
  NULL
);

DROP PROCEDURE IF EXISTS fail_if_report_identity_duplicates;
DELIMITER $$
CREATE PROCEDURE fail_if_report_identity_duplicates()
BEGIN
  IF @duplicate_report_identity_count > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = @abort_message;
  END IF;
END$$
DELIMITER ;
CALL fail_if_report_identity_duplicates();
DROP PROCEDURE fail_if_report_identity_duplicates;

CREATE TABLE IF NOT EXISTS `capability_report_version` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '版本ID',
  `report_id` int(11) NOT NULL COMMENT '报告主记录ID',
  `version_no` int(11) NOT NULL COMMENT '版本号，初始版本为1',
  `version_type` varchar(16) COLLATE utf8mb4_bin NOT NULL DEFAULT 'uploaded' COMMENT '版本类型：initial/uploaded',
  `file_name` varchar(255) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '展示文件名',
  `file_path` varchar(1024) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '服务端文件路径',
  `file_size` bigint(20) NOT NULL DEFAULT '0' COMMENT '文件大小',
  `audit_status` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'pending' COMMENT '最新审核状态',
  `uploader` varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT '未知用户' COMMENT '上传人',
  `source` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'upload' COMMENT '来源：batch/upload',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `uk_report_version` (`report_id`, `version_no`) USING BTREE,
  KEY `idx_report_latest` (`report_id`, `create_time`) USING BTREE,
  KEY `idx_audit_status` (`audit_status`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告版本';

CREATE TABLE IF NOT EXISTS `capability_report_audit` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '审核记录ID',
  `report_id` int(11) NOT NULL COMMENT '报告主记录ID',
  `version_id` bigint(20) NOT NULL COMMENT '报告版本ID',
  `status` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'pending' COMMENT '审核状态',
  `summary` json DEFAULT NULL COMMENT '审核总结',
  `result_data` json DEFAULT NULL COMMENT '审核检查点结果',
  `prompt_id` bigint(20) DEFAULT NULL COMMENT '提示词ID',
  `prompt_version` int(11) DEFAULT NULL COMMENT '提示词版本',
  `model_name` varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '模型名称',
  `error_message` text COLLATE utf8mb4_bin COMMENT '错误信息',
  `started_at` datetime(3) DEFAULT NULL COMMENT '开始时间',
  `finished_at` datetime(3) DEFAULT NULL COMMENT '完成时间',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_report_version` (`report_id`, `version_id`) USING BTREE,
  KEY `idx_status` (`status`) USING BTREE,
  KEY `idx_create_time` (`create_time`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告AI审核记录';

CREATE TABLE IF NOT EXISTS `capability_report_audit_prompt` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '提示词ID',
  `name` varchar(128) COLLATE utf8mb4_bin NOT NULL DEFAULT '默认审核提示词' COMMENT '提示词名称',
  `prompt_content` text COLLATE utf8mb4_bin NOT NULL COMMENT '提示词内容',
  `version` int(11) NOT NULL DEFAULT '1' COMMENT '提示词版本',
  `enabled` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否启用',
  `model_name` varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT 'ark-code-latest' COMMENT '模型名称',
  `api_url` varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT 'https://ark.cn-beijing.volces.com/api/coding/v3' COMMENT '大模型API地址',
  `api_key` varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '大模型API Key',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `uk_prompt_version` (`name`, `version`) USING BTREE,
  KEY `idx_enabled` (`enabled`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告AI审核提示词';

DROP PROCEDURE IF EXISTS ensure_report_log_indexes;
DELIMITER $$
CREATE PROCEDURE ensure_report_log_indexes()
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND index_name = 'idx_systemId'
  ) THEN
    ALTER TABLE capability_report_log DROP KEY idx_systemId;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND index_name = 'uk_report_identity'
  ) THEN
    ALTER TABLE capability_report_log
      ADD UNIQUE KEY uk_report_identity (`systemId`, `title`, `report_month`) USING BTREE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_log'
      AND index_name = 'idx_report_month'
  ) THEN
    ALTER TABLE capability_report_log
      ADD KEY idx_report_month (`report_month`) USING BTREE;
  END IF;
END$$
DELIMITER ;
CALL ensure_report_log_indexes();
DROP PROCEDURE ensure_report_log_indexes;

INSERT INTO capability_report_audit_prompt
  (`name`, `prompt_content`, `version`, `enabled`, `model_name`, `api_url`, `api_key`)
SELECT
  '默认审核提示词',
  '你是性能容量报告审核助手。请根据输入的 DOCX 文本、表格、章节结构和审核检查点，审核报告是否满足性能容量报告质量要求。只审核文档标题和章节结构、正文文字、表格内容，以及能从文字或表格中明确读取到的指标、数量、结论和建议。不要审核图片、截图、图表图片或无法从文本中读取的视觉语义。如果无法判断某个检查点，不要编造结论，应明确说明缺少依据。使用清晰、专业的中文给出审核总结、发现的问题和修改建议。',
  1,
  1,
  'ark-code-latest',
  'https://ark.cn-beijing.volces.com/api/coding/v3',
  ''
FROM DUAL
WHERE NOT EXISTS (
  SELECT 1 FROM capability_report_audit_prompt
  WHERE name = '默认审核提示词'
    AND version = 1
);

INSERT INTO capability_report_version
  (`report_id`, `version_no`, `version_type`, `file_name`, `file_path`, `file_size`, `audit_status`, `uploader`, `source`, `create_time`)
SELECT
  report.id,
  1,
  'initial',
  SUBSTRING_INDEX(JSON_UNQUOTE(JSON_EXTRACT(report.report_data, '$.data')), '/', -1),
  JSON_UNQUOTE(JSON_EXTRACT(report.report_data, '$.data')),
  0,
  'pending',
  '批次任务',
  'batch',
  report.create_time
FROM capability_report_log report
WHERE JSON_UNQUOTE(JSON_EXTRACT(report.report_data, '$.data')) IS NOT NULL
  AND JSON_UNQUOTE(JSON_EXTRACT(report.report_data, '$.data')) <> ''
  AND NOT EXISTS (
    SELECT 1 FROM capability_report_version version
    WHERE version.report_id = report.id
      AND version.version_no = 1
  );

INSERT INTO capability_report_audit
  (`report_id`, `version_id`, `status`, `summary`, `result_data`, `create_time`)
SELECT
  version.report_id,
  version.id,
  'pending',
  NULL,
  NULL,
  version.create_time
FROM capability_report_version version
WHERE version.version_no = 1
  AND version.version_type = 'initial'
  AND NOT EXISTS (
    SELECT 1 FROM capability_report_audit audit
    WHERE audit.version_id = version.id
  );

SELECT
  (SELECT COUNT(*) FROM capability_report_version) AS version_rows,
  (SELECT COUNT(*) FROM capability_report_audit) AS audit_rows,
  (SELECT COUNT(*) FROM capability_report_audit_prompt WHERE enabled = 1) AS enabled_prompt_rows;
