-- RuoYi menu draft. Review parent_id and permission names before running.

SET @parent_id = 3;

INSERT INTO sys_menu
  (menu_name, parent_id, order_num, path, component, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES
  ('报告管理', @parent_id, 10, 'report-management/reports', 'report-management/report/index', 1, 0, 'C', '0', '0', 'report:management:list', 'documentation', 'admin', NOW(), '报告管理菜单'),
  ('审核提示词', @parent_id, 11, 'report-management/audit-prompts', 'report-management/audit-prompt/index', 1, 0, 'C', '0', '0', 'report:prompt:list', 'edit', 'admin', NOW(), '审核提示词菜单');
