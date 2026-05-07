<script setup lang="ts">
import { reactive, watch } from "vue";
import type { ImportFormState } from "@/types";

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  close: [];
  submit: [form: ImportFormState];
}>();

const form = reactive<ImportFormState>({
  mode: "local",
  localPath: "",
  zipPath: "",
  repoUrl: "",
  ref: "",
  overwrite: false,
  runInstall: true,
});

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    form.mode = "local";
    form.localPath = "";
    form.zipPath = "";
    form.repoUrl = "";
    form.ref = "";
    form.overwrite = false;
    form.runInstall = true;
  },
);
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    width="700px"
    align-center
    class="glass-dialog"
    @close="emit('close')"
  >
    <template #header>
      <div class="dialog-header">
        <p class="dialog-header__eyebrow">Plugin Intake</p>
        <h3>导入插件</h3>
      </div>
    </template>

    <el-form label-position="top" class="stack-form">
      <el-form-item label="导入方式">
        <el-segmented
          v-model="form.mode"
          :options="[
            { label: '本地目录', value: 'local' },
            { label: 'ZIP 文件', value: 'zip' },
            { label: 'Git 仓库', value: 'git' }
          ]"
        />
      </el-form-item>

      <el-form-item v-if="form.mode === 'local'" label="本地目录路径">
        <el-input v-model="form.localPath" placeholder="D:\\tools\\my_plugin" />
      </el-form-item>

      <el-form-item v-if="form.mode === 'zip'" label="ZIP 文件路径">
        <el-input v-model="form.zipPath" placeholder="D:\\tools\\my_plugin.zip" />
      </el-form-item>

      <template v-if="form.mode === 'git'">
        <el-form-item label="Git 仓库地址">
          <el-input v-model="form.repoUrl" placeholder="https://github.com/xxx/your-plugin.git" />
        </el-form-item>
        <el-form-item label="分支 / Tag（可选）">
          <el-input v-model="form.ref" placeholder="main" />
        </el-form-item>
      </template>

      <el-form-item>
        <div class="stack-switches">
          <el-checkbox v-model="form.overwrite">允许覆盖同名插件</el-checkbox>
          <el-checkbox v-model="form.runInstall">导入后自动安装依赖</el-checkbox>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('close')">取消</el-button>
        <el-button type="primary" :loading="props.submitting" @click="emit('submit', { ...form })">开始导入</el-button>
      </div>
    </template>
  </el-dialog>
</template>
