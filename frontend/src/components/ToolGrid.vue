<script setup lang="ts">
import { Search } from "@element-plus/icons-vue";
import type { ToolItem } from "@/types";
import ToolCard from "./ToolCard.vue";

const props = defineProps<{
  tools: ToolItem[];
  keyword: string;
  statusFilter: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  "update:keyword": [value: string];
  "update:statusFilter": [value: string];
  usage: [tool: ToolItem];
  run: [tool: ToolItem];
}>();
</script>

<template>
  <section class="content-shell">
    <div class="surface filter-shell">
      <div class="filter-shell__search">
        <el-input
          :model-value="props.keyword"
          size="large"
          placeholder="搜索工具名称 / 描述 / 标签"
          @update:model-value="emit('update:keyword', String($event || ''))"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <el-segmented
        :model-value="props.statusFilter"
        :options="[
          { label: '全部', value: 'all' },
          { label: '可用', value: 'ready' },
          { label: '草稿', value: 'draft' },
          { label: '停用', value: 'offline' }
        ]"
        @change="emit('update:statusFilter', String($event))"
      />
    </div>

    <div v-if="props.loading" class="tool-grid tool-grid--loading">
      <div v-for="item in 6" :key="item" class="surface skeleton-card"></div>
    </div>

    <div v-else-if="!props.tools.length" class="surface empty-state">
      <p class="empty-state__eyebrow">No Match</p>
      <h3>没有匹配的工具</h3>
      <p>尝试切换分组、清空搜索词，或检查当前状态筛选。</p>
    </div>

    <div v-else class="tool-grid">
      <ToolCard
        v-for="tool in props.tools"
        :key="tool.id"
        :tool="tool"
        @usage="emit('usage', $event)"
        @run="emit('run', $event)"
      />
    </div>
  </section>
</template>
