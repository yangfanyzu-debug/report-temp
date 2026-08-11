-- Report management schema draft for MySQL 5.7 / ry-cloud.
-- Prefer migrations/001_precheck_report_management.sql and migrations/001_apply_report_management.sql for execution.

ALTER TABLE `capability_report_log`
  DROP KEY `idx_systemId`,
  ADD UNIQUE KEY `uk_report_identity` (`systemId`, `title`, `report_month`),
  ADD KEY `idx_report_month` (`report_month`);

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
