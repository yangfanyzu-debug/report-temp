<template>
  <div class="app-container report-detail-page">
    <el-page-header content="报告详情" @back="goBack" />

    <el-descriptions class="detail-block" :column="2" border>
      <el-descriptions-item label="系统编码">{{ report.systemId }}</el-descriptions-item>
      <el-descriptions-item label="报表月份">{{ report.reportMonth }}</el-descriptions-item>
      <el-descriptions-item label="报告标题" :span="2">{{ report.title }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ report.createTime }}</el-descriptions-item>
    </el-descriptions>

    <el-table v-loading="loading" :data="report.versions || []" border>
      <el-table-column label="版本" prop="versionNo" width="90">
        <template slot-scope="scope">
          <el-tag size="mini">v{{ scope.row.versionNo }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类型" prop="versionType" width="110">
        <template slot-scope="scope">
          {{ scope.row.versionType === 'initial' ? '初始版本' : '上传版本' }}
        </template>
      </el-table-column>
      <el-table-column label="文件名" prop="fileName" min-width="260" show-overflow-tooltip />
      <el-table-column label="文件大小" prop="fileSize" width="110">
        <template slot-scope="scope">{{ formatSize(scope.row.fileSize) }}</template>
      </el-table-column>
      <el-table-column label="审核状态" prop="auditStatus" width="120">
        <template slot-scope="scope">
          <el-tag :type="statusType(scope.row.auditStatus)" size="mini">
            {{ statusLabel(scope.row.auditStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核结论" prop="latestAuditConclusion" width="120" show-overflow-tooltip />
      <el-table-column label="上传人" prop="uploader" width="120" show-overflow-tooltip />
      <el-table-column label="创建时间" prop="createTime" width="170" />
      <el-table-column label="操作" width="260" fixed="right">
        <template slot-scope="scope">
          <el-button size="mini" type="text" icon="el-icon-document" @click="openPreview(scope.row.id)">预览</el-button>
          <el-button size="mini" type="text" icon="el-icon-download" @click="downloadVersion(scope.row.id)">下载</el-button>
          <el-button
            size="mini"
            type="text"
            icon="el-icon-reading"
            :disabled="!scope.row.latestAuditId"
            @click="openAudit(scope.row.latestAuditId)"
          >审核</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog title="审核详情" :visible.sync="auditDialogVisible" width="760px" append-to-body>
      <el-descriptions v-if="audit.id" :column="2" border>
        <el-descriptions-item label="审核状态">{{ statusLabel(audit.status) }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ audit.modelName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提示词版本">v{{ audit.promptVersion || '-' }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ audit.finishedAt || '-' }}</el-descriptions-item>
        <el-descriptions-item label="结论">{{ audit.summary && audit.summary['结论'] }}</el-descriptions-item>
        <el-descriptions-item label="问题数量">{{ audit.summary && audit.summary['问题数量'] }}</el-descriptions-item>
        <el-descriptions-item label="建议" :span="2">{{ audit.summary && audit.summary['建议'] }}</el-descriptions-item>
        <el-descriptions-item v-if="audit.errorMessage" label="错误" :span="2">{{ audit.errorMessage }}</el-descriptions-item>
      </el-descriptions>

      <el-table class="audit-table" :data="auditRows" border>
        <el-table-column label="检查点" prop="检查点" min-width="260" show-overflow-tooltip />
        <el-table-column label="分析结果" prop="分析结果" min-width="360" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script>
import { downloadUrl, getAudit, getReport } from '@/api/report-management/report'

export default {
  name: 'ReportManagementDetail',
  data() {
    return {
      loading: false,
      report: {},
      auditDialogVisible: false,
      audit: {}
    }
  },
  computed: {
    auditRows() {
      return (this.audit.resultData && this.audit.resultData.data) || []
    }
  },
  created() {
    this.getDetail()
  },
  methods: {
    getDetail() {
      this.loading = true
      getReport(this.$route.params.id).then(response => {
        this.report = response
      }).finally(() => {
        this.loading = false
      })
    },
    goBack() {
      this.$router.push({ path: '/report-management/reports' })
    },
    openPreview(versionId) {
      const route = this.$router.resolve({ path: `/report-management/preview/${versionId}` })
      window.open(route.href, '_blank')
    },
    downloadVersion(versionId) {
      window.open(downloadUrl(versionId), '_blank')
    },
    openAudit(auditId) {
      getAudit(auditId).then(response => {
        this.audit = response
        this.auditDialogVisible = true
      })
    },
    formatSize(size) {
      if (!size) return '0 B'
      if (size < 1024) return `${size} B`
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
      return `${(size / 1024 / 1024).toFixed(1)} MB`
    },
    statusLabel(status) {
      return {
        pending: '待审核',
        running: '审核中',
        passed: '审核通过',
        failed: '审核不通过',
        error: '审核失败'
      }[status] || '待审核'
    },
    statusType(status) {
      return {
        pending: 'info',
        running: 'warning',
        passed: 'success',
        failed: 'danger',
        error: 'danger'
      }[status] || 'info'
    }
  }
}
</script>

<style scoped>
.detail-block {
  margin: 18px 0;
}

.audit-table {
  margin-top: 16px;
}
</style>
