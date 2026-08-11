<template>
  <div class="app-container audit-prompt-page">
    <el-form ref="form" :model="form" :rules="rules" label-width="100px" size="small">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="名称" prop="name">
            <el-input v-model="form.name" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="模型" prop="modelName">
            <el-input v-model="form.modelName" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="当前版本">
            <el-input :value="form.version ? `v${form.version}` : '-'" disabled />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="提示词" prop="promptContent">
        <el-input
          v-model="form.promptContent"
          type="textarea"
          :rows="22"
          resize="vertical"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-check" :loading="saving" @click="submitForm">保存</el-button>
        <el-button icon="el-icon-refresh" @click="loadActivePrompt">刷新</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { createPromptVersion, getActivePrompt } from '@/api/report-management/auditPrompt'

export default {
  name: 'ReportAuditPrompt',
  data() {
    return {
      saving: false,
      form: {
        name: '默认审核提示词',
        promptContent: '',
        version: '',
        modelName: 'ark-code-latest'
      },
      rules: {
        name: [{ required: true, message: '名称不能为空', trigger: 'blur' }],
        modelName: [{ required: true, message: '模型不能为空', trigger: 'blur' }],
        promptContent: [{ required: true, message: '提示词不能为空', trigger: 'blur' }]
      }
    }
  },
  created() {
    this.loadActivePrompt()
  },
  methods: {
    loadActivePrompt() {
      getActivePrompt().then(response => {
        this.form = {
          name: response.name,
          promptContent: response.promptContent,
          version: response.version,
          modelName: response.modelName
        }
      }).catch(() => {
        this.form.modelName = this.form.modelName || 'ark-code-latest'
      })
    },
    submitForm() {
      this.$refs.form.validate(valid => {
        if (!valid) return
        this.saving = true
        createPromptVersion({
          name: this.form.name,
          promptContent: this.form.promptContent,
          modelName: this.form.modelName
        }).then(response => {
          this.$modal.msgSuccess(`已保存为 v${response.version}`)
          this.form.version = response.version
        }).finally(() => {
          this.saving = false
        })
      })
    }
  }
}
</script>
