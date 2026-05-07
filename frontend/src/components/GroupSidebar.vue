<script setup lang="ts">
import { Grid, Histogram, MagicStick, Management, Monitor, SetUp } from "@element-plus/icons-vue";

const props = defineProps<{
  groups: string[];
  activeGroup: string;
}>();

const emit = defineEmits<{
  select: [group: string];
}>();

const iconMap: Record<string, unknown> = {
  "全部工具": Grid,
  "LabelU 工具": MagicStick,
  "数据清洗": Management,
  "格式转换": SetUp,
  "统计分析": Histogram,
  "训练辅助": Monitor,
  "系统工具": SetUp,
};
</script>

<template>
  <aside class="surface sidebar-shell">
    <div class="panel-heading">
      <p class="panel-heading__eyebrow">Workspace</p>
      <h2>工具分组</h2>
    </div>

    <nav class="group-nav" aria-label="工具分组">
      <button
        v-for="group in props.groups"
        :key="group"
        type="button"
        :class="['group-nav__item', { 'is-active': group === props.activeGroup }]"
        @click="emit('select', group)"
      >
        <span class="group-nav__icon">
          <el-icon><component :is="iconMap[group] || Grid" /></el-icon>
        </span>
        <span>{{ group }}</span>
      </button>
    </nav>
  </aside>
</template>
