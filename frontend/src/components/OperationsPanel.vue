<script setup lang="ts">
import { RefreshRight } from "@element-plus/icons-vue";
import type { HistoryItem, QueueItem } from "@/types";
import { percentByStatus, statusText } from "@/utils/format";

defineProps<{
  queueItems: QueueItem[];
  historyItems: HistoryItem[];
}>();
</script>

<template>
  <aside class="operations-shell">
    <section class="surface ops-card">
      <div class="ops-card__head">
        <div>
          <p class="panel-heading__eyebrow">Live State</p>
          <h2>运行队列</h2>
        </div>
        <el-button text>
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </div>

      <div v-if="queueItems.length" class="ops-list">
        <article v-for="item in queueItems" :key="item.taskId" class="ops-list__item">
          <div class="ops-list__summary">
            <strong>{{ item.toolName }}</strong>
            <span>{{ statusText(item.status) }}</span>
          </div>
          <small>#{{ item.taskId }}</small>
          <el-progress
            v-if="percentByStatus(item.status) !== null"
            :percentage="percentByStatus(item.status) || 0"
            :show-text="false"
            :stroke-width="6"
          />
        </article>
      </div>
      <div v-else class="ops-empty">暂无运行中的任务</div>
    </section>

    <section class="surface ops-card">
      <div class="ops-card__head">
        <div>
          <p class="panel-heading__eyebrow">Recent Trails</p>
          <h2>最近执行</h2>
        </div>
      </div>

      <div v-if="historyItems.length" class="ops-list ops-list--history">
        <article v-for="item in historyItems" :key="item.id" class="ops-list__item">
          <div class="ops-list__summary">
            <strong>{{ item.toolName }}</strong>
            <span>{{ statusText(item.status) }}</span>
          </div>
          <p>{{ item.summary }}</p>
        </article>
      </div>
      <div v-else class="ops-empty">暂无执行记录</div>
    </section>
  </aside>
</template>
