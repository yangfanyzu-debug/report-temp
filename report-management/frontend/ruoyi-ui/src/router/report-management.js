export default [
  {
    path: '/report-management/reports',
    component: () => import('@/views/report-management/report/index'),
    name: 'ReportManagement',
    meta: { title: '报告管理', icon: 'documentation' }
  },
  {
    path: '/report-management/reports/:id',
    component: () => import('@/views/report-management/report/detail'),
    name: 'ReportManagementDetail',
    hidden: true,
    meta: { title: '报告详情', activeMenu: '/report-management/reports' }
  },
  {
    path: '/report-management/preview/:versionId',
    component: () => import('@/views/report-management/preview/index'),
    name: 'ReportManagementPreview',
    hidden: true,
    meta: { title: 'DOCX预览' }
  },
  {
    path: '/report-management/audit-prompts',
    component: () => import('@/views/report-management/audit-prompt/index'),
    name: 'ReportAuditPrompt',
    meta: { title: '审核提示词', icon: 'edit' }
  }
]
