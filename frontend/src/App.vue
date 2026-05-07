<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { fetchArtifacts, fetchTask, fetchTools, importPlugin, runTool } from "@/api/client";
import AppTopbar from "@/components/AppTopbar.vue";
import EnvironmentDialog from "@/components/EnvironmentDialog.vue";
import GroupSidebar from "@/components/GroupSidebar.vue";
import ImportDialog from "@/components/ImportDialog.vue";
import OperationsPanel from "@/components/OperationsPanel.vue";
import ResultDialog from "@/components/ResultDialog.vue";
import RunDialog from "@/components/RunDialog.vue";
import ToolGrid from "@/components/ToolGrid.vue";
import UsageDialog from "@/components/UsageDialog.vue";
import { useEnvironment } from "@/composables/useEnvironment";
import type { ArtifactItem, HistoryItem, ImportFormState, QueueItem, TaskDetail, ToolItem } from "@/types";
import { buildUsageDoc, normalizeOutputText, normalizeValue, statusText, toolMatches } from "@/utils/format";

const tools = ref<ToolItem[]>([]);
const loading = ref(false);
const keyword = ref("");
const statusFilter = ref("all");
const activeGroup = ref("全部工具");

const activeTool = ref<ToolItem | null>(null);
const usageVisible = ref(false);
const runVisible = ref(false);
const resultVisible = ref(false);
const envVisible = ref(false);
const importVisible = ref(false);

const submittingRun = ref(false);
const submittingImport = ref(false);

const queueItems = ref<QueueItem[]>([]);
const historyItems = ref<HistoryItem[]>([]);
const resultTask = ref<TaskDetail | null>(null);
const resultArtifacts = ref<ArtifactItem[]>([]);
const clipboardText = ref("");

const { envConfig, envLabel, save: saveEnvironment } = useEnvironment();

const groups = computed(() => ["全部工具", ...new Set(tools.value.map((tool) => tool.group || "未分组"))]);

const filteredTools = computed(() =>
  tools.value.filter((tool) => toolMatches(tool, activeGroup.value, keyword.value, statusFilter.value)),
);

const usageTitle = computed(() => (activeTool.value ? `使用说明：${activeTool.value.name}` : ""));
const usageBody = computed(() => (activeTool.value ? buildUsageDoc(activeTool.value) : ""));
const usageMeta = computed(() =>
  activeTool.value
    ? `分组：${activeTool.value.group || "-"} ｜ 状态：${statusText(activeTool.value.status || "ready")} ｜ 运行时：${activeTool.value.runtime || "-"}`
    : "",
);

const stdoutText = computed(() => normalizeOutputText(resultTask.value?.stdout));
const stderrText = computed(() => normalizeOutputText(resultTask.value?.stderr));

function pushHistory(toolName: string, summary: string, status: string) {
  historyItems.value.unshift({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    toolName,
    summary,
    status,
    timestamp: Date.now(),
  });
  historyItems.value = historyItems.value.slice(0, 30);
}

async function bootstrapTools() {
  loading.value = true;
  try {
    tools.value = await fetchTools();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载工具失败");
  } finally {
    loading.value = false;
  }
}

function openUsage(tool: ToolItem) {
  activeTool.value = tool;
  usageVisible.value = true;
}

function openRun(tool: ToolItem) {
  activeTool.value = tool;
  runVisible.value = true;
}

async function pollTask(taskId: string, toolName: string) {
  const startedAt = Date.now();
  while (true) {
    const task = await fetchTask(taskId);
    const current = queueItems.value.find((item) => item.taskId === taskId);
    if (current) {
      current.status = task.status;
    }

    if (["success", "failed", "timeout"].includes(task.status)) {
      queueItems.value = queueItems.value.filter((item) => item.taskId !== taskId);
      resultTask.value = task;
      resultArtifacts.value = await fetchArtifacts(taskId).catch(() => []);
      resultVisible.value = true;
      clipboardText.value = [normalizeOutputText(task.stdout), normalizeOutputText(task.stderr)]
        .filter(Boolean)
        .join("\n\n--- stderr ---\n\n");
      pushHistory(toolName, `${statusText(task.status)}：task=${taskId}${task.logFile ? `，日志：${task.logFile}` : ""}`, task.status);
      return;
    }

    if (Date.now() - startedAt > 1000 * 1800) {
      queueItems.value = queueItems.value.filter((item) => item.taskId !== taskId);
      pushHistory(toolName, `轮询超时：task=${taskId}`, "timeout");
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

async function submitRun(values: Record<string, string>) {
  if (!activeTool.value) return;
  const normalized: Record<string, string> = {};
  Object.entries(values).forEach(([key, value]) => {
    normalized[key] = normalizeValue(value);
  });

  submittingRun.value = true;
  try {
    const result = await runTool(activeTool.value.id, normalized);
    queueItems.value.unshift({
      taskId: result.taskId,
      toolName: activeTool.value.name,
      status: "pending",
      createdAt: Date.now(),
    });
    runVisible.value = false;
    void pollTask(result.taskId, activeTool.value.name);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交任务失败");
    pushHistory(activeTool.value.name, `提交失败：${error instanceof Error ? error.message : "未知错误"}`, "failed");
  } finally {
    submittingRun.value = false;
  }
}

async function submitImport(form: ImportFormState) {
  submittingImport.value = true;
  try {
    const result = await importPlugin(form);
    const pluginName = result.plugin?.name || result.plugin?.id || "未知插件";
    const installSteps = result.install?.steps?.length || 0;
    ElMessage.success(`插件导入成功：${pluginName}`);
    pushHistory(pluginName, `导入成功${installSteps ? `，安装步骤：${installSteps}` : ""}`, "success");
    importVisible.value = false;
    await bootstrapTools();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "插件导入失败");
  } finally {
    submittingImport.value = false;
  }
}

async function copyResult() {
  if (!clipboardText.value) return;
  try {
    await navigator.clipboard.writeText(clipboardText.value);
    ElMessage.success("输出已复制");
  } catch {
    ElMessage.warning("复制失败，请手动复制");
  }
}

bootstrapTools();
</script>

<template>
  <div class="app-shell">
    <div class="ambient-layer ambient-layer--a"></div>
    <div class="ambient-layer ambient-layer--b"></div>

    <AppTopbar :env-label="envLabel" @open-env="envVisible = true" @open-import="importVisible = true" />

    <main class="workspace-shell">
      <GroupSidebar :groups="groups" :active-group="activeGroup" @select="activeGroup = $event" />

      <ToolGrid
        :tools="filteredTools"
        :keyword="keyword"
        :status-filter="statusFilter"
        :loading="loading"
        @update:keyword="keyword = $event"
        @update:status-filter="statusFilter = $event"
        @usage="openUsage"
        @run="openRun"
      />

      <OperationsPanel :queue-items="queueItems" :history-items="historyItems" />
    </main>

    <UsageDialog
      :visible="usageVisible"
      :title="usageTitle"
      :body="usageBody"
      :meta="usageMeta"
      @close="usageVisible = false"
    />

    <RunDialog
      :visible="runVisible"
      :tool="activeTool"
      :env-label="envLabel"
      :submitting="submittingRun"
      @close="runVisible = false"
      @submit="submitRun"
    />

    <ResultDialog
      :visible="resultVisible"
      :tool-name="resultTask?.toolName || activeTool?.name || '执行结果'"
      :task="resultTask"
      :stdout-text="stdoutText"
      :stderr-text="stderrText"
      :clipboard-text="clipboardText"
      :artifacts="resultArtifacts"
      @close="resultVisible = false"
      @copy="copyResult"
    />

    <ImportDialog :visible="importVisible" :submitting="submittingImport" @close="importVisible = false" @submit="submitImport" />

    <EnvironmentDialog
      :visible="envVisible"
      :value="envConfig"
      @close="envVisible = false"
      @submit="
        (value) => {
          saveEnvironment(value);
          envVisible = false;
          ElMessage.success(`环境已保存：${value.envName}`);
        }
      "
    />
  </div>
</template>
