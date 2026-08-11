<template>
  <div class="preview-page">
    <div class="preview-toolbar">
      <span class="preview-title">DOCX预览</span>
      <el-button size="mini" icon="el-icon-download" @click="downloadFile">下载</el-button>
    </div>
    <div v-loading="loading" class="preview-body">
      <vue-office-docx
        v-if="docx"
        :src="docx"
        @rendered="loading = false"
        @error="handleError"
      />
      <el-empty v-if="loadError" description="预览失败" />
    </div>
  </div>
</template>

<script>
import VueOfficeDocx from '@vue-office/docx'
import '@vue-office/docx/lib/index.css'
import { downloadUrl, previewUrl } from '@/api/report-management/report'

export default {
  name: 'ReportManagementPreview',
  components: { VueOfficeDocx },
  data() {
    return {
      loading: true,
      loadError: false,
      docx: ''
    }
  },
  created() {
    this.docx = previewUrl(this.$route.params.versionId)
  },
  methods: {
    downloadFile() {
      window.open(downloadUrl(this.$route.params.versionId), '_blank')
    },
    handleError() {
      this.loading = false
      this.loadError = true
    }
  }
}
</script>

<style scoped>
.preview-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.preview-toolbar {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #dcdfe6;
}

.preview-title {
  font-weight: 600;
  color: #303133;
}

.preview-body {
  min-height: calc(100vh - 48px);
  padding: 16px;
}
</style>
