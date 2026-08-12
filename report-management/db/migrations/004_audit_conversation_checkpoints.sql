-- Add natural-language audit results, checkpoint snapshots and configurable checkpoints.
-- Compatible with MySQL 5.7 and existing JSON audit records.

SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS ensure_report_audit_conversation_columns;
DELIMITER $$
CREATE PROCEDURE ensure_report_audit_conversation_columns()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'capability_report_audit' AND column_name = 'result_text'
  ) THEN
    ALTER TABLE capability_report_audit
      ADD COLUMN `result_text` LONGTEXT COLLATE utf8mb4_bin NULL COMMENT 'AI审核Markdown原文' AFTER `result_data`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'capability_report_audit' AND column_name = 'conclusion'
  ) THEN
    ALTER TABLE capability_report_audit
      ADD COLUMN `conclusion` varchar(32) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '审核结论：passed/failed/completed' AFTER `result_text`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'capability_report_audit' AND column_name = 'checkpoint_snapshot'
  ) THEN
    ALTER TABLE capability_report_audit
      ADD COLUMN `checkpoint_snapshot` json DEFAULT NULL COMMENT '本次审核使用的检查点快照' AFTER `conclusion`;
  END IF;
END$$
DELIMITER ;
CALL ensure_report_audit_conversation_columns();
DROP PROCEDURE ensure_report_audit_conversation_columns;

CREATE TABLE IF NOT EXISTS `capability_report_audit_checkpoint` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '检查点ID',
  `checkpoint_name` varchar(128) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '检查点名称',
  `checkpoint_content` text COLLATE utf8mb4_bin NOT NULL COMMENT '检查要求',
  `sort_order` int(11) NOT NULL DEFAULT '0' COMMENT '显示及审核顺序',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_checkpoint_enabled_sort` (`enabled`, `sort_order`, `id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告AI审核检查点';

INSERT INTO capability_report_audit_checkpoint
  (`checkpoint_name`, `checkpoint_content`, `sort_order`, `enabled`)
SELECT seed.checkpoint_name, seed.checkpoint_content, seed.sort_order, 1
FROM (
  SELECT '章节完整性' AS checkpoint_name, '检测章节应用指标统计与分析是否空缺' AS checkpoint_content, 10 AS sort_order
  UNION ALL SELECT '子章节内容', '检测应用指标统计与分析下是否有章节内容为空', 20
  UNION ALL SELECT '指标零值', '检测是否存在最小值、最大值或平均值为0的情况', 30
  UNION ALL SELECT '服务器数量一致性', '比对系统当前性能分析小结和系统概述中各组件的服务器数量，如果前者低于后者，则是异常', 40
  UNION ALL SELECT '组件数量一致性', '比对系统性能分析子标题数量和系统当前性能分析小结中的组件数，判断前后数量是否一致', 50
  UNION ALL SELECT '组件分析完整性', '检测系统当前性能分析小结中的组件分析是否存在空缺', 60
) seed
WHERE NOT EXISTS (SELECT 1 FROM capability_report_audit_checkpoint);

UPDATE capability_report_audit
SET conclusion = CASE
  WHEN status = 'passed' THEN 'passed'
  WHEN status = 'failed' THEN 'failed'
  WHEN status NOT IN ('pending', 'running', 'error') THEN 'completed'
  ELSE conclusion
END
WHERE conclusion IS NULL;

SELECT
  (SELECT COUNT(*) FROM capability_report_audit_checkpoint) AS checkpoint_rows,
  (SELECT COUNT(*) FROM capability_report_audit WHERE result_text IS NOT NULL) AS text_result_rows;
