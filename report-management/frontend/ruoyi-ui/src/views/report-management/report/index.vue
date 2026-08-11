<template>
  <div class="app-container report-page">
    <el-form ref="queryForm" :model="queryParams" size="small" :inline="true" label-width="80px">
      <el-form-item label="系统编码" prop="systemId">
        <el-input
          v-model="queryParams.systemId"
          placeholder="请输入系统编码"
          clearable
          @keyup.enter.native="handleQuery"
        />
      </el-form-item>
      <el-form-item label="报告标题" prop="title">
        <el-input
          v-model="queryParams.title"
          placeholder="请输入报告标题"
          clearable
          @keyup.enter.native="handleQuery"
        />
      </el-form-item>
      <el-form-item label="报表月份" prop="reportMonth">
        <el-date-picker
          v-model="reportMonthValue"
          type="month"
          value-format="yyyy年MM月"
          placeholder="请选择月份"
          clearable
          @change="handleMonthChange"
        />
      </el-form-item>
      <el-form-item label="审核状态" prop="auditStatus">
        <el-select v-model="queryParams.auditStatus" placeholder="请选择状态" clearable>
          <el-option label="待审核" value="pending" />
          <el-option label="审核中" value="running" />
          <el-option label="审核通过" value="passed" />
          <el-option label="审核不通过" value="failed" />
          <el-option label="审核失败" value="error" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-search" size="mini" @click="handleQuery">搜索</el-button>
        <el-button icon="el-icon-refresh" size="mini" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="reportList" border>
      <el-table-column label="系统编码" prop="systemId" min-width="150" show-overflow-tooltip />
      <el-table-column label="报告标题" prop="title" min-width="260" show-overflow-tooltip />
      <el-table-column label="报表月份" prop="reportMonth" width="120" />
      <el-table-column label="最新版本" prop="latestVersionNo" width="100">
        <template slot-scope="scope">
          <el-tag v-if="scope.row.latestVersionNo" size="mini">v{{ scope.row.latestVersionNo }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="审核状态" prop="latestAuditStatus" width="120">
        <template slot-scope="scope">
          <el-tag :type="statusType(scope.row.latestAuditStatus)" size="mini">
            {{ statusLabel(scope.row.latestAuditStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核结论" prop="latestAuditConclusion" width="120" show-overflow-tooltip />
      <el-table-column label="审核建议" prop="latestAuditSuggestion" min-width="240" show-overflow-tooltip />
      <el-table-column label="创建时间" prop="createTime" width="170" />
      <el-table-column label="操作" width="320" fixed="right">
        <template slot-scope="scope">
          <el-button size="mini" type="text" icon="el-icon-view" @click="openDetail(scope.row)">详情</el-button>
          <el-button
            size="mini"
            type="text"
            icon="el-icon-document"
            :disabled="!scope.row.latestVersionId"
            @click="openPreview(scope.row.latestVersionId)"
          >预览</el-button>
          <el-button
            size="mini"
            type="text"
            icon="el-icon-download"
            :disabled="!scope.row.latestVersionId"
            @click="downloadVersion(scope.row.latestVersionId)"
          >下载</el-button>
          <el-button size="mini" type="text" icon="el-icon-upload2" @click="openUpload(scope.row)">上传</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      :page.sync="queryParams.pageNum"
      :limit.sync="queryParams.pageSize"
      @pagination="getList"
    />

    <el-dialog title="上传新版本" :visible.sync="uploadDialogVisible" width="480px" append-to-body>
      <el-form label-width="80px" size="small">
        <el-form-item label="报告标题">
          <el-input :value="currentReport.title" disabled />
        </el-form-item>
        <el-form-item label="上传人">
          <el-input v-model="uploadForm.uploader" placeholder="请输入上传人" />
        </el-form-item>
        <el-form-item label="DOCX文件">
          <el-upload
            ref="upload"
            :auto-upload="false"
            :limit="1"
            accept=".docx"
            action=""
            :http-request="submitUploadRequest"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button size="small" type="primary" icon="el-icon-folder-opened">选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">确定</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { downloadUrl, listReports, previewUrl, uploadReportVersion } from '@/api/report-management/report'

export default {
  name: 'ReportManagement',
  data() {
    return {
      loading: false,
      uploading: false,
      total: 0,
      reportList: [],
      reportMonthValue: '',
      queryParams: {
        pageNum: 1,
        pageSize: 10,
        systemId: '',
        title: '',
        reportMonth: '',
        auditStatus: ''
      },
      uploadDialogVisible: false,
      currentReport: {},
      uploadForm: {
        uploader: '',
        file: null
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      this.loading = true
      listReports(this.queryParams).then(response => {
        this.reportList = response.rows || []
        this.total = response.total || 0
      }).finally(() => {
        this.loading = false
      })
    },
    handleQuery() {
      this.queryParams.pageNum = 1
      this.getList()
    },
    resetQuery() {
      this.reportMonthValue = ''
      this.resetForm('queryForm')
      this.queryParams.reportMonth = ''
      this.handleQuery()
    },
    handleMonthChange(value) {
      this.queryParams.reportMonth = value || ''
    },
    openDetail(row) {
      this.$router.push({ path: `/report-management/reports/${row.id}` })
    },
    openPreview(versionId) {
      const route = this.$router.resolve({ path: `/report-management/preview/${versionId}` })
      window.open(route.href, '_blank')
    },
    downloadVersion(versionId) {
      window.open(downloadUrl(versionId), '_blank')
    },
    openUpload(row) {
      this.currentReport = row
      this.uploadForm = { uploader: '', file: null }
      this.uploadDialogVisible = true
      this.$nextTick(() => {
        if (this.$refs.upload) this.$refs.upload.clearFiles()
      })
    },
    handleFileChange(file) {
      this.uploadForm.file = file.raw
    },
    handleFileRemove() {
      this.uploadForm.file = null
    },
    submitUploadRequest() {},
    submitUpload() {
      if (!this.uploadForm.file) {
        this.$modal.msgWarning('请选择DOCX文件')
        return
      }
      const formData = new FormData()
      formData.append('file', this.uploadForm.file)
      formData.append('uploader', this.uploadForm.uploader || '未知用户')
      this.uploading = true
      uploadReportVersion(this.currentReport.id, formData).then(() => {
        this.$modal.msgSuccess('已上传新版本，AI审核中')
        this.uploadDialogVisible = false
        this.getList()
      }).finally(() => {
        this.uploading = false
      })
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
.report-page .el-table {
  margin-top: 10px;
}
</style>
