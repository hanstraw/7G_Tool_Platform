<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import type { ToolItem } from "@/types";

const props = defineProps<{
  visible: boolean;
  tool: ToolItem | null;
  envLabel: string;
  submitting: boolean;
}>();

const emit = defineEmits<{
  close: [];
  submit: [values: Record<string, string>];
}>();

const formState = reactive<Record<string, string | boolean>>({});

watch(
  () => props.tool,
  (tool) => {
    Object.keys(formState).forEach((key) => delete formState[key]);
    (tool?.params || []).forEach((param) => {
      if (param.type === "boolean") {
        formState[param.key] = String(param.default || "").toLowerCase() === "true";
      } else {
        formState[param.key] = param.default || "";
      }
    });
  },
  { immediate: true },
);

const rules = computed(() => {
  const result: Record<string, Array<{ required?: boolean; message: string; trigger: string }>> = {};
  (props.tool?.params || []).forEach((param) => {
    if (param.required) {
      result[param.key] = [{ required: true, message: `请填写${param.label || param.key}`, trigger: "blur" }];
    }
  });
  return result;
});

function submit() {
  const values: Record<string, string> = {};
  (props.tool?.params || []).forEach((param) => {
    const currentValue = formState[param.key];
    if (param.type === "boolean") {
      values[param.key] = currentValue ? "true" : "false";
    } else {
      values[param.key] = String(currentValue ?? "");
    }
  });
  emit("submit", values);
}
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    width="920px"
    align-center
    class="glass-dialog run-dialog"
    @close="emit('close')"
  >
    <template #header>
      <div class="dialog-header">
        <p class="dialog-header__eyebrow">Execution Surface</p>
        <h3>运行工具 - {{ props.tool?.name || "未选择工具" }}</h3>
        <small>执行环境：{{ props.envLabel }}</small>
      </div>
    </template>

    <div v-if="props.tool" class="run-dialog__layout">
      <div class="run-dialog__summary">
        <h4>{{ props.tool.group || "未分组" }}</h4>
        <p>{{ props.tool.desc || "暂无描述" }}</p>
        <div class="run-dialog__summary-tags">
          <span v-for="tag in (props.tool.tags || []).slice(0, 4)" :key="tag">{{ tag }}</span>
        </div>
      </div>

      <el-form class="run-dialog__form" label-position="top" :rules="rules">
        <template v-for="param in props.tool.params || []" :key="param.key">
          <el-form-item :label="`${param.label || param.key}${param.required ? ' *' : ''}`">
            <el-input
              v-if="!param.type || ['text', 'path', 'password'].includes(param.type)"
              v-model="formState[param.key]"
              :type="param.type === 'password' ? 'password' : 'text'"
              :placeholder="param.label || param.key"
              show-password
            />

            <el-input
              v-else-if="['textarea', 'filelist'].includes(param.type)"
              v-model="formState[param.key]"
              type="textarea"
              :rows="4"
              :placeholder="param.label || param.key"
            />

            <el-select
              v-else-if="param.type === 'select'"
              v-model="formState[param.key]"
              :placeholder="param.label || param.key"
            >
              <el-option v-for="option in param.options || []" :key="option" :label="option" :value="option" />
            </el-select>

            <el-switch
              v-else-if="param.type === 'boolean'"
              v-model="formState[param.key]"
              inline-prompt
              active-text="开"
              inactive-text="关"
            />

            <el-input v-else v-model="formState[param.key]" :placeholder="param.label || param.key" />
          </el-form-item>
        </template>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('close')">取消</el-button>
        <el-button type="primary" :loading="props.submitting" @click="submit">开始执行</el-button>
      </div>
    </template>
  </el-dialog>
</template>
