<script setup lang="ts">
import { Connection, Plus, Setting, Tools } from "@element-plus/icons-vue";

defineProps<{
  envLabel: string;
}>();

const emit = defineEmits<{
  openEnv: [];
  openImport: [];
}>();
</script>

<template>
  <header class="topbar-shell">
    <div class="brand-cluster">
      <div class="brand-mark">
        <span class="brand-mark__inner">7G</span>
      </div>
      <div class="brand-copy">
        <p class="brand-copy__eyebrow">Internal Operations Hub</p>
        <h1>7G Tool Platform</h1>
      </div>
    </div>

    <div class="environment-pill">
      <span class="environment-pill__dot"></span>
      <span class="environment-pill__label">当前环境</span>
      <strong>{{ envLabel }}</strong>
      <span class="environment-pill__divider"></span>
      <span class="environment-pill__mode">工具统一运行工作台</span>
    </div>

    <div class="topbar-actions">
      <el-button class="action-btn action-btn--soft" @click="emit('openEnv')">
        <el-icon><Setting /></el-icon>
        环境配置
      </el-button>
      <el-button type="primary" class="action-btn" @click="emit('openImport')">
        <el-icon><Plus /></el-icon>
        导入插件
      </el-button>
      <div class="operator-chip">
        <span class="operator-chip__avatar">
          <el-icon><Tools /></el-icon>
        </span>
        <div class="operator-chip__content">
          <span>Operator</span>
          <small><el-icon><Connection /></el-icon> Live</small>
        </div>
      </div>
    </div>
  </header>
</template>
