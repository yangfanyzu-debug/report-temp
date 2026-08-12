-- Persist incremental AI audit progress for polling and recovery.

CREATE TABLE IF NOT EXISTS `capability_report_audit_event` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '审核事件ID',
  `audit_id` bigint(20) NOT NULL COMMENT '审核记录ID',
  `event_type` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'system' COMMENT '事件类型：system/model/result/error',
  `phase` varchar(32) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '审核阶段',
  `content` mediumtext COLLATE utf8mb4_bin NOT NULL COMMENT '事件内容',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_audit_event` (`audit_id`, `id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告AI审核过程事件';

INSERT INTO capability_report_audit_event (`audit_id`, `event_type`, `phase`, `content`, `create_time`)
SELECT audit.id, 'system', 'queued', '报告已登记，等待AI审核', audit.create_time
FROM capability_report_audit audit
WHERE audit.status = 'pending'
  AND NOT EXISTS (
    SELECT 1
    FROM capability_report_audit_event event
    WHERE event.audit_id = audit.id
  );

SELECT COUNT(*) AS audit_event_rows FROM capability_report_audit_event;
