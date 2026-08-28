-- Add shared model configuration and explicit initial/revision audit types.
-- Compatible with MySQL 5.7 and safe to re-run.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS capability_report_ai_config (
  id bigint(20) NOT NULL AUTO_INCREMENT,
  api_url varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '',
  model_name varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT 'ark-code-latest',
  api_key varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '',
  create_time datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

DROP PROCEDURE IF EXISTS ensure_dual_audit_type_columns_and_indexes;
DELIMITER $$
CREATE PROCEDURE ensure_dual_audit_type_columns_and_indexes()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
      AND column_name = 'audit_type'
  ) THEN
    ALTER TABLE capability_report_audit_prompt
      ADD COLUMN `audit_type` ENUM('initial', 'revision') COLLATE utf8mb4_bin NOT NULL DEFAULT 'revision' COMMENT '审核类型：initial/revision'
      AFTER `enabled`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit'
      AND column_name = 'audit_type'
  ) THEN
    ALTER TABLE capability_report_audit
      ADD COLUMN `audit_type` ENUM('initial', 'revision') COLLATE utf8mb4_bin NOT NULL DEFAULT 'revision' COMMENT '审核类型：initial/revision'
      AFTER `status`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
      AND index_name = 'idx_audit_prompt_type_enabled'
  ) THEN
    ALTER TABLE capability_report_audit_prompt
      ADD KEY `idx_audit_prompt_type_enabled` (`audit_type`, `enabled`, `id`) USING BTREE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit'
      AND index_name = 'idx_audit_pending_type'
  ) THEN
    ALTER TABLE capability_report_audit
      ADD KEY `idx_audit_pending_type` (`status`, `audit_type`, `create_time`, `id`) USING BTREE;
  END IF;
END$$
DELIMITER ;
CALL ensure_dual_audit_type_columns_and_indexes();
DROP PROCEDURE ensure_dual_audit_type_columns_and_indexes;

-- Normalize pre-006 varchar values before converting existing columns to ENUM.
UPDATE capability_report_audit_prompt
SET audit_type = 'revision'
WHERE audit_type IS NULL
   OR audit_type = ''
   OR audit_type NOT IN ('initial', 'revision');

UPDATE capability_report_audit
SET audit_type = 'revision'
WHERE audit_type IS NULL
   OR audit_type = ''
   OR audit_type NOT IN ('initial', 'revision');

DROP PROCEDURE IF EXISTS ensure_dual_audit_type_enum_values;
DELIMITER $$
CREATE PROCEDURE ensure_dual_audit_type_enum_values()
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit_prompt'
      AND column_name = 'audit_type'
      AND LOWER(REPLACE(column_type, ' ', '')) <> 'enum(''initial'',''revision'')'
  ) THEN
    ALTER TABLE capability_report_audit_prompt
      MODIFY COLUMN `audit_type` ENUM('initial', 'revision') COLLATE utf8mb4_bin NOT NULL DEFAULT 'revision' COMMENT '审核类型：initial/revision'
      AFTER `enabled`;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'capability_report_audit'
      AND column_name = 'audit_type'
      AND LOWER(REPLACE(column_type, ' ', '')) <> 'enum(''initial'',''revision'')'
  ) THEN
    ALTER TABLE capability_report_audit
      MODIFY COLUMN `audit_type` ENUM('initial', 'revision') COLLATE utf8mb4_bin NOT NULL DEFAULT 'revision' COMMENT '审核类型：initial/revision'
      AFTER `status`;
  END IF;
END$$
DELIMITER ;
CALL ensure_dual_audit_type_enum_values();
DROP PROCEDURE ensure_dual_audit_type_enum_values;

SET @dual_audit_types_first_run := (
  SELECT COUNT(*) = 0 FROM capability_report_ai_config
);

INSERT INTO capability_report_ai_config
  (`api_url`, `model_name`, `api_key`)
SELECT
  COALESCE((
    SELECT prompt.api_url
    FROM capability_report_audit_prompt prompt
    WHERE prompt.enabled = 1
    ORDER BY prompt.id DESC
    LIMIT 1
  ), ''),
  COALESCE(NULLIF((
    SELECT prompt.model_name
    FROM capability_report_audit_prompt prompt
    WHERE prompt.enabled = 1
    ORDER BY prompt.id DESC
    LIMIT 1
  ), ''), 'ark-code-latest'),
  COALESCE((
    SELECT prompt.api_key
    FROM capability_report_audit_prompt prompt
    WHERE prompt.enabled = 1
    ORDER BY prompt.id DESC
    LIMIT 1
  ), '')
FROM DUAL
WHERE NOT EXISTS (
  SELECT 1 FROM capability_report_ai_config
);

UPDATE capability_report_audit_prompt
SET enabled = 0
WHERE @dual_audit_types_first_run = 1
  AND enabled = 1;

INSERT INTO capability_report_audit_prompt
  (`name`, `prompt_content`, `version`, `enabled`, `audit_type`, `model_name`, `api_url`, `api_key`)
SELECT
  '初始审核提示词',
  '你是性能容量报告的初始质量审核助手。你只审核批次生成的初始 DOCX 报告，目标是发现基础文字和文档结构问题。

审核范围仅包括系统提供的报告基本信息、正文文字、标题层级、可读取的目录条目和表格文字。不要判断图片、截图或图表图片的视觉语义，不要声称检查了字体、颜色、分页、对齐等未提供的版式信息。

请检查：
1. 报告标题、系统名称、报告月份等基本信息是否前后一致。
2. 可读取的目录条目与正文标题是否存在缺失、多余、顺序错误或编号不一致。
3. 章节和子章节是否缺失、重复、为空或只有标题没有正文。
4. 正文是否存在明显错别字、病句、标点错误、术语混用或同一名称前后不一致。
5. 表格标题、表头、单位和单元格内容是否存在明显缺失或前后不一致。
6. 文档中是否存在明显占位符、测试文字、未替换模板内容或无法解释的空值。

只根据输入中可读取的内容判断。证据不足时明确说明无法判断，不得编造文档内容。发现问题时指出原文位置或相关章节，并给出可执行的修改建议。',
  1,
  1,
  'initial',
  config.model_name,
  config.api_url,
  config.api_key
FROM capability_report_ai_config config
WHERE config.id = (
  SELECT id FROM capability_report_ai_config ORDER BY id ASC LIMIT 1
)
  AND NOT EXISTS (
    SELECT 1 FROM capability_report_audit_prompt
    WHERE name = '初始审核提示词'
      AND version = 1
      AND audit_type = 'initial'
  );

INSERT INTO capability_report_audit_prompt
  (`name`, `prompt_content`, `version`, `enabled`, `audit_type`, `model_name`, `api_url`, `api_key`)
SELECT
  '修订审核提示词',
  '你是性能容量报告的修订审核助手。你只审核用户上传的修订版本，目标是判断性能容量分析、数据结论和治理建议是否合理。不要重复执行错别字、目录一致性等初始质量检查。

审核范围仅包括系统提供的报告基本信息、正文文字、表格数据和标题结构。不要判断图片、截图或图表图片的视觉语义。

请检查：
1. 性能指标、容量指标、阈值、统计周期和单位是否明确，最小值、最大值、平均值或关键指标为 0 时是否有合理解释。
2. 系统概述、组件清单、服务器数量、性能分析小结和结论中的数量是否前后一致。
3. 各组件是否都有对应的性能或容量分析，是否存在只有数据没有分析、只有结论没有依据的情况。
4. 报告结论是否能由正文或表格中的数据支撑，是否存在数据与结论矛盾、统计口径不一致或推导跳跃。
5. 是否识别容量瓶颈、资源风险、趋势变化和影响范围，风险等级是否与证据匹配。
6. 扩容、优化或治理建议是否具体可执行，是否包含对象、依据、优先级或验证方式。
只根据输入中可读取的内容判断。证据不足时明确说明无法判断，不得编造指标、服务器数量或图表结论。发现问题时引用相关章节或表格依据，并给出可执行的修改建议。',
  1,
  1,
  'revision',
  config.model_name,
  config.api_url,
  config.api_key
FROM capability_report_ai_config config
WHERE config.id = (
  SELECT id FROM capability_report_ai_config ORDER BY id ASC LIMIT 1
)
  AND NOT EXISTS (
    SELECT 1 FROM capability_report_audit_prompt
    WHERE name = '修订审核提示词'
      AND version = 1
      AND audit_type = 'revision'
  );

UPDATE capability_report_audit_prompt seed
LEFT JOIN capability_report_audit_prompt active
  ON active.audit_type = seed.audit_type
 AND active.enabled = 1
 AND active.id <> seed.id
SET seed.enabled = 1
WHERE seed.name = '初始审核提示词'
  AND seed.version = 1
  AND seed.audit_type = 'initial'
  AND active.id IS NULL;

UPDATE capability_report_audit_prompt seed
LEFT JOIN capability_report_audit_prompt active
  ON active.audit_type = seed.audit_type
 AND active.enabled = 1
 AND active.id <> seed.id
SET seed.enabled = 1
WHERE seed.name = '修订审核提示词'
  AND seed.version = 1
  AND seed.audit_type = 'revision'
  AND active.id IS NULL;

UPDATE capability_report_audit audit
JOIN capability_report_version version ON version.id = audit.version_id
SET audit.audit_type = CASE
  WHEN version.version_type = 'initial' THEN 'initial'
  ELSE 'revision'
END
WHERE audit.audit_type IS NULL OR audit.audit_type = '';

-- A newly added NOT NULL column starts legacy rows at its revision default.
UPDATE capability_report_audit audit
JOIN capability_report_version version ON version.id = audit.version_id
SET audit.audit_type = 'initial'
WHERE version.version_type = 'initial'
  AND audit.audit_type = 'revision';

UPDATE capability_report_audit
SET audit_type = 'revision'
WHERE audit_type IS NULL OR audit_type = '';

SELECT
  (SELECT COUNT(*) FROM capability_report_ai_config) AS ai_config_rows,
  (SELECT COUNT(*) FROM capability_report_audit_prompt WHERE audit_type = 'initial' AND enabled = 1) AS active_initial_prompt_rows,
  (SELECT COUNT(*) FROM capability_report_audit_prompt WHERE audit_type = 'revision' AND enabled = 1) AS active_revision_prompt_rows,
  (SELECT COUNT(*) FROM capability_report_audit WHERE audit_type IS NULL OR audit_type = '') AS blank_audit_type_rows;
