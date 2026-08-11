import request from '@/utils/request'

export function listReports(query) {
  return request({
    url: '/report-management-api/reports',
    method: 'get',
    params: query
  })
}

export function getReport(reportId) {
  return request({
    url: `/report-management-api/reports/${reportId}`,
    method: 'get'
  })
}

export function registerInitialReport(data) {
  return request({
    url: '/report-management-api/reports/register',
    method: 'post',
    data
  })
}

export function uploadReportVersion(reportId, data) {
  return request({
    url: `/report-management-api/reports/${reportId}/versions`,
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function getAudit(auditId) {
  return request({
    url: `/report-management-api/audits/${auditId}`,
    method: 'get'
  })
}

export function previewUrl(versionId) {
  return `${process.env.VUE_APP_BASE_API}/report-management-api/versions/${versionId}/preview`
}

export function downloadUrl(versionId) {
  return `${process.env.VUE_APP_BASE_API}/report-management-api/versions/${versionId}/download`
}
