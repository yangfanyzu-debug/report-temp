-- Persist multi-turn conversations between users and the report audit agent.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `capability_report_agent_message` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `report_id` int(11) NOT NULL COMMENT '报告ID',
  `version_id` bigint(20) NOT NULL COMMENT '报告版本ID',
  `reply_to_id` bigint(20) DEFAULT NULL COMMENT '回复的用户消息ID',
  `role` varchar(16) COLLATE utf8mb4_bin NOT NULL COMMENT '角色：user/assistant',
  `content` longtext COLLATE utf8mb4_bin COMMENT '消息内容',
  `status` varchar(16) COLLATE utf8mb4_bin NOT NULL DEFAULT 'completed' COMMENT '状态：pending/running/completed/error',
  `model_name` varchar(128) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '模型名称',
  `error_message` varchar(1000) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '错误信息',
  `create_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `finished_at` datetime(3) DEFAULT NULL COMMENT '完成时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_agent_message_version` (`report_id`, `version_id`, `id`) USING BTREE,
  KEY `idx_agent_message_pending` (`role`, `status`, `create_time`, `id`) USING BTREE,
  KEY `idx_agent_message_reply` (`reply_to_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='性能容量报告AI Agent对话消息';

SELECT COUNT(*) AS agent_message_rows FROM capability_report_agent_message;
