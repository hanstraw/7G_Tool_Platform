<script setup lang="ts">
import { ArrowRight, ChatLineSquare, Cpu, MagicStick, Operation, Pointer } from "@element-plus/icons-vue";
import { ElTag } from "element-plus";
import type { ToolItem } from "@/types";
import { iconSeed, statusText, statusTone } from "@/utils/format";

const props = defineProps<{
  tool: ToolItem;
}>();

const emit = defineEmits<{
  usage: [tool: ToolItem];
  run: [tool: ToolItem];
}>();

function pickIcon(group?: string) {
  if (String(group).includes("LabelU")) return MagicStick;
  if (String(group).includes("训练")) return Cpu;
  if (String(group).includes("统计")) return Operation;
  return Pointer;
}
</script>

<template>
  <article class="surface tool-card">
    <div class="tool-card__head">
      <div class="tool-card__icon">
        <el-icon><component :is="pickIcon(props.tool.group)" /></el-icon>
        <span>{{ iconSeed(props.tool) }}</span>
      </div>
      <div class="tool-card__identity">
        <h3>{{ props.tool.name || props.tool.id }}</h3>
        <p>{{ props.tool.desc || "暂无描述" }}</p>
      </div>
    </div>

    <div class="tool-card__meta">
      <el-tag :type="statusTone(props.tool.status)" effect="plain" round>
        {{ statusText(props.tool.status || "ready") }}
      </el-tag>
      <span class="tool-card__version">v{{ props.tool.version || "1.0.0" }}</span>
    </div>

    <div class="tool-card__tags">
      <span v-for="tag in (props.tool.tags || []).slice(0, 3)" :key="tag">{{ tag }}</span>
      <span v-if="!(props.tool.tags || []).length">{{ props.tool.group || "未分组" }}</span>
    </div>

    <div class="tool-card__actions">
      <el-button class="tool-card__secondary" @click="emit('usage', props.tool)">
        <el-icon><ChatLineSquare /></el-icon>
        使用说明
      </el-button>
      <el-button type="primary" class="tool-card__primary" @click="emit('run', props.tool)">
        运行工具
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </div>
  </article>
</template>
