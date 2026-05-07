<script setup lang="ts">
import { computed } from "vue";
import type { ArtifactItem, TaskDetail } from "@/types";
import { buildApiUrl } from "@/api/client";
import { formatBytes, sortArtifacts, statusText } from "@/utils/format";

const props = defineProps<{
  visible: boolean;
  toolName: string;
  task: TaskDetail | null;
  stdoutText: string;
  stderrText: string;
  clipboardText: string;
  artifacts: ArtifactItem[];
}>();

const emit = defineEmits<{
  close: [];
  copy: [];
}>();

const sortedArtifacts = computed(() => sortArtifacts(props.artifacts || []));
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    width="1080px"
    align-center
    class="glass-dialog result-dialog"
    @close="emit('close')"
  >
    <template #header>
      <div class="dialog-header">
        <p class="dialog-header__eyebrow">Execution Result</p>
        <h3>{{ props.toolName }}</h3>
        <small>状态：{{ statusText(props.task?.status) }}</small>
      </div>
    </template>

    <div v-if="props.task" class="result-dialog__layout">
      <section class="result-pane">
        <div class="result-pane__head">
          <h4>标准输出</h4>
          <el-button text @click="emit('copy')">复制输出</el-button>
        </div>
        <pre class="result-pane__content">{{ props.stdoutText || "（暂无标准输出）" }}</pre>

        <div class="result-pane__head result-pane__head--error">
          <h4>错误输出</h4>
        </div>
        <pre class="result-pane__content result-pane__content--error">{{ props.stderrText || "（错误输出为空）" }}</pre>
      </section>

      <aside class="result-side">
        <section class="surface result-side__card">
          <h4>任务信息</h4>
          <ul>
            <li><span>任务 ID</span><strong>{{ props.task.taskId }}</strong></li>
            <li><span>日志文件</span><strong>{{ props.task.logFile || "-" }}</strong></li>
            <li><span>退出码</span><strong>{{ props.task.returnCode ?? "-" }}</strong></li>
            <li><span>开始时间</span><strong>{{ props.task.startedAt || "-" }}</strong></li>
            <li><span>结束时间</span><strong>{{ props.task.endedAt || "-" }}</strong></li>
          </ul>
        </section>

        <section class="surface result-side__card">
          <h4>产出文件</h4>
          <div v-if="sortedArtifacts.length" class="artifact-list">
            <article v-for="item in sortedArtifacts" :key="`${item.name}-${item.viewUrl}`" class="artifact-list__item">
              <div>
                <strong>{{ item.name }}</strong>
                <small>{{ formatBytes(item.size) }}</small>
              </div>
              <div class="artifact-list__actions">
                <a :href="buildApiUrl(item.viewUrl)" target="_blank" rel="noreferrer noopener">查看</a>
                <a :href="buildApiUrl(item.downloadUrl)" target="_blank" rel="noreferrer noopener">下载</a>
              </div>
            </article>
          </div>
          <p v-else class="ops-empty">当前任务没有可展示的产出文件</p>
        </section>
      </aside>
    </div>
  </el-dialog>
</template>
