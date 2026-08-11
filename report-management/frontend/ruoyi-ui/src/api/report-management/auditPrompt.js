import request from '@/utils/request'

export function getActivePrompt() {
  return request({
    url: '/report-management-api/audit-prompts/active',
    method: 'get'
  })
}

export function createPromptVersion(data) {
  return request({
    url: '/report-management-api/audit-prompts',
    method: 'post',
    data
  })
}
