<script setup lang="ts">
import { reactive, watch } from "vue";
import type { EnvConfig } from "@/types";

const props = defineProps<{
  visible: boolean;
  value: EnvConfig;
}>();

const emit = defineEmits<{
  close: [];
  submit: [value: EnvConfig];
}>();

const form = reactive<EnvConfig>({
  envName: "DEV",
  labelu: { url: "", username: "", password: "" },
  ssh: { host: "", username: "", password: "" },
});

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    form.envName = props.value.envName;
    form.labelu = { ...props.value.labelu };
    form.ssh = { ...props.value.ssh };
  },
  { immediate: true },
);
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    width="780px"
    align-center
    class="glass-dialog"
    @close="emit('close')"
  >
    <template #header>
      <div class="dialog-header">
        <p class="dialog-header__eyebrow">Environment Matrix</p>
        <h3>环境配置</h3>
      </div>
    </template>

    <div class="env-dialog__grid">
      <section class="surface env-dialog__card">
        <h4>基础环境</h4>
        <el-form label-position="top">
          <el-form-item label="环境名称">
            <el-select v-model="form.envName">
              <el-option label="DEV" value="DEV" />
              <el-option label="TEST" value="TEST" />
              <el-option label="PROD" value="PROD" />
            </el-select>
          </el-form-item>
        </el-form>
      </section>

      <section class="surface env-dialog__card">
        <h4>LabelU 配置</h4>
        <el-form label-position="top">
          <el-form-item label="LabelU 地址">
            <el-input v-model="form.labelu.url" placeholder="http://127.0.0.1:8080" />
          </el-form-item>
          <el-form-item label="LabelU 账号">
            <el-input v-model="form.labelu.username" placeholder="请输入账号" />
          </el-form-item>
          <el-form-item label="LabelU 密码">
            <el-input v-model="form.labelu.password" type="password" show-password placeholder="请输入密码" />
          </el-form-item>
        </el-form>
      </section>

      <section class="surface env-dialog__card">
        <h4>SSH 配置</h4>
        <el-form label-position="top">
          <el-form-item label="SSH 地址">
            <el-input v-model="form.ssh.host" placeholder="192.168.1.100:22" />
          </el-form-item>
          <el-form-item label="SSH 账号">
            <el-input v-model="form.ssh.username" placeholder="root" />
          </el-form-item>
          <el-form-item label="SSH 密码">
            <el-input v-model="form.ssh.password" type="password" show-password placeholder="请输入密码" />
          </el-form-item>
        </el-form>
      </section>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('close')">取消</el-button>
        <el-button type="primary" @click="emit('submit', { ...form, labelu: { ...form.labelu }, ssh: { ...form.ssh } })">
          保存配置
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
