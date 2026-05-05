const API_BASE = "http://192.168.54.120:8787";
const ENV_CONFIG_KEY = "tool_platform_env_config";
let tools = [];
let activeTool = null;
let activeGroup = "全部";
let queueMap = {};
const histories = [];

const groupListEl = document.getElementById("groupList");
const toolGridEl = document.getElementById("toolGrid");
const searchInputEl = document.getElementById("searchInput");
const statusFilterEl = document.getElementById("statusFilter");
const queueListEl = document.getElementById("queueList");
const historyListEl = document.getElementById("historyList");
const detailDialog = document.getElementById("detailDialog");
const detailTitle = document.getElementById("detailTitle");
const detailDesc = document.getElementById("detailDesc");
const detailMeta = document.getElementById("detailMeta");
const runDialog = document.getElementById("runDialog");
const runDialogTitle = document.getElementById("runDialogTitle");
const runForm = document.getElementById("runForm");
const runFormFields = document.getElementById("runFormFields");
const cancelRunBtn = document.getElementById("cancelRunBtn");
const resultDialog = document.getElementById("resultDialog");
const resultDialogTitle = document.getElementById("resultDialogTitle");
const resultStatusLine = document.getElementById("resultStatusLine");
const resultStdout = document.getElementById("resultStdout");
const resultStderrBlock = document.getElementById("resultStderrBlock");
const resultStderr = document.getElementById("resultStderr");
const resultArtifactsBlock = document.getElementById("resultArtifactsBlock");
const resultArtifactsList = document.getElementById("resultArtifactsList");
const resultMetaLine = document.getElementById("resultMetaLine");
const copyResultBtn = document.getElementById("copyResultBtn");

let lastResultClipboardText = "";

const importPluginBtn = document.getElementById("importPluginBtn");
const importDialog = document.getElementById("importDialog");
const importForm = document.getElementById("importForm");
const importTypeEl = document.getElementById("importType");
const importLocalPathEl = document.getElementById("importLocalPath");
const importZipPathEl = document.getElementById("importZipPath");
const importGitRepoEl = document.getElementById("importGitRepo");
const importGitRefEl = document.getElementById("importGitRef");
const importOverwriteEl = document.getElementById("importOverwrite");
const importRunInstallEl = document.getElementById("importRunInstall");
const importLocalPathRow = document.getElementById("importLocalPathRow");
const importZipPathRow = document.getElementById("importZipPathRow");
const importGitRepoRow = document.getElementById("importGitRepoRow");
const importGitRefRow = document.getElementById("importGitRefRow");
const cancelImportBtn = document.getElementById("cancelImportBtn");

const envConfigBtn = document.getElementById("envConfigBtn");
const envDialog = document.getElementById("envDialog");
const envForm = document.getElementById("envForm");
const cancelEnvBtn = document.getElementById("cancelEnvBtn");
const envNameEl = document.getElementById("envName");
const labeluUrlEl = document.getElementById("labeluUrl");
const labeluUserEl = document.getElementById("labeluUser");
const labeluPasswordEl = document.getElementById("labeluPassword");
const sshHostEl = document.getElementById("sshHost");
const sshUserEl = document.getElementById("sshUser");
const sshPasswordEl = document.getElementById("sshPassword");

function defaultEnvConfig() {
  return { envName: "DEV", labelu: { url: "", username: "", password: "" }, ssh: { host: "", username: "", password: "" } };
}

function loadEnvConfig() {
  const raw = localStorage.getItem(ENV_CONFIG_KEY);
  if (!raw) return defaultEnvConfig();
  try {
    const parsed = JSON.parse(raw);
    return {
      ...defaultEnvConfig(),
      ...parsed,
      labelu: { ...defaultEnvConfig().labelu, ...(parsed.labelu || {}) },
      ssh: { ...defaultEnvConfig().ssh, ...(parsed.ssh || {}) },
    };
  } catch (error) {
    return defaultEnvConfig();
  }
}

function saveEnvConfig(config) {
  localStorage.setItem(ENV_CONFIG_KEY, JSON.stringify(config));
}

function updateEnvBadge(envName) {
  envConfigBtn.textContent = `环境：${envName}`;
}

function fillEnvForm(config) {
  envNameEl.value = config.envName;
  labeluUrlEl.value = config.labelu.url;
  labeluUserEl.value = config.labelu.username;
  labeluPasswordEl.value = config.labelu.password;
  sshHostEl.value = config.ssh.host;
  sshUserEl.value = config.ssh.username;
  sshPasswordEl.value = config.ssh.password;
}

function bindEnvEvents() {
  envConfigBtn.addEventListener("click", () => {
    fillEnvForm(loadEnvConfig());
    envDialog.showModal();
  });
  cancelEnvBtn.addEventListener("click", () => envDialog.close());
  envForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const config = {
      envName: envNameEl.value,
      labelu: { url: labeluUrlEl.value.trim(), username: labeluUserEl.value.trim(), password: labeluPasswordEl.value },
      ssh: { host: sshHostEl.value.trim(), username: sshUserEl.value.trim(), password: sshPasswordEl.value },
    };
    saveEnvConfig(config);
    updateEnvBadge(config.envName);
    envDialog.close();
  });
}

function statusText(status) {
  if (status === "ready") return "可用";
  if (status === "draft") return "草稿";
  if (status === "running") return "运行中";
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  if (status === "timeout") return "超时";
  return "停用";
}

async function requestJson(url, init = {}) {
  const resp = await fetch(url, init);
  const data = await resp.json();
  if (!data.ok) throw new Error(data.message || "请求失败");
  return data.data;
}

async function fetchTools() {
  const data = await requestJson(`${API_BASE}/api/tools`);
  return data.tools || [];
}

function normalizeValue(value) {
  const text = String(value || "").trim();
  if (text.length >= 2 && text[0] === text[text.length - 1] && (text[0] === "\"" || text[0] === "'")) {
    return text.slice(1, -1).trim();
  }
  return text;
}

function renderGroups() {
  const names = ["全部", ...new Set(tools.map((item) => item.group || "未分组"))];
  if (!names.includes(activeGroup)) activeGroup = "全部";
  groupListEl.innerHTML = "";
  names.forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    if (name === activeGroup) li.classList.add("active");
    li.addEventListener("click", () => {
      activeGroup = name;
      renderGroups();
      renderTools();
    });
    groupListEl.appendChild(li);
  });
}

function buildUsageDoc(tool) {
  if (tool.usage && String(tool.usage).trim()) return String(tool.usage).trim();
  const lines = (tool.params || []).map((param) => `- ${param.label || param.key}（${param.required ? "必填" : "可选"}）`);
  return [`工具名称：${tool.name}`, "", "用途：", tool.desc || "暂无描述", "", "参数：", lines.join("\n") || "无"].join("\n");
}

function renderTools() {
  const keyword = searchInputEl.value.trim().toLowerCase();
  const status = statusFilterEl.value;
  const filtered = tools.filter((tool) => {
    const groupOk = activeGroup === "全部" || tool.group === activeGroup;
    const statusOk = status === "all" || tool.status === status;
    const merged = `${tool.name || ""} ${tool.desc || ""} ${(tool.tags || []).join(" ")}`.toLowerCase();
    const searchOk = !keyword || merged.includes(keyword);
    return groupOk && statusOk && searchOk;
  });

  toolGridEl.innerHTML = "";
  if (filtered.length === 0) {
    toolGridEl.innerHTML = `<div class="card muted">没有匹配的工具。</div>`;
    return;
  }

  filtered.forEach((tool) => {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.innerHTML = `
      <h3>${tool.name || tool.id}</h3>
      <p>${tool.desc || "暂无描述"}</p>
      <div class="meta">
        <span class="status-${tool.status || "ready"}">${statusText(tool.status || "ready")}</span>
        <span>${tool.version || "-"}</span>
      </div>
      <div style="margin-top:10px;">
        <button class="btn detail-btn">使用说明</button>
        <button class="btn btn-primary run-btn">运行工具</button>
      </div>
    `;
    card.querySelector(".detail-btn").addEventListener("click", () => {
      detailTitle.textContent = `使用说明：${tool.name}`;
      detailDesc.textContent = buildUsageDoc(tool);
      detailMeta.textContent = `分组：${tool.group || "-"} ｜ 状态：${statusText(tool.status || "ready")} ｜ 运行时：${tool.runtime || "-"}`;
      detailDialog.showModal();
    });
    card.querySelector(".run-btn").addEventListener("click", () => openRunDialog(tool));
    toolGridEl.appendChild(card);
  });
}

function renderField(param) {
  const key = param.key;
  const label = `${param.label || key}${param.required ? " *" : ""}`;
  const requiredAttr = param.required ? "required" : "";
  const defaultValue = param.default === undefined ? "" : String(param.default);
  if (param.type === "textarea" || param.type === "filelist") {
    return `<label>${label}<textarea name="${key}" rows="4" ${requiredAttr} placeholder="${key}">${defaultValue}</textarea></label>`;
  }
  if (param.type === "select") {
    const options = (param.options || []).map((opt) => `<option value="${opt}" ${String(opt) === defaultValue ? "selected" : ""}>${opt}</option>`).join("");
    return `<label>${label}<select name="${key}" ${requiredAttr}>${options}</select></label>`;
  }
  if (param.type === "boolean") {
    const checked = defaultValue.toLowerCase() === "true" ? "checked" : "";
    return `<label>${label}<select name="${key}"><option value="true" ${checked ? "selected" : ""}>true</option><option value="false" ${checked ? "" : "selected"}>false</option></select></label>`;
  }
  const type = param.type === "password" ? "password" : "text";
  return `<label>${label}<input name="${key}" type="${type}" ${requiredAttr} value="${defaultValue}" placeholder="${key}" /></label>`;
}

function openRunDialog(tool) {
  activeTool = tool;
  runDialogTitle.textContent = `运行工具：${tool.name}`;
  runFormFields.innerHTML = (tool.params || []).map(renderField).join("");
  runDialog.showModal();
}

function renderLists() {
  const queueItems = Object.values(queueMap);
  queueListEl.innerHTML = queueItems.length ? queueItems.map((item) => `<li>${item}</li>`).join("") : "<li>暂无运行中的任务</li>";
  historyListEl.innerHTML = histories.length ? histories.map((item) => `<li>${item}</li>`).join("") : "<li>暂无执行记录</li>";
}

function normalizeOutputText(text) {
  return String(text || "").replace(/\r\n/g, "\n").trimEnd();
}

function formatBytes(bytes) {
  const n = Number(bytes || 0);
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function renderArtifacts(items) {
  if (!items || !items.length) {
    resultArtifactsBlock.style.display = "none";
    resultArtifactsList.innerHTML = "";
    return;
  }
  const priority = {
    ".html": 1,
    ".htm": 1,
    ".pdf": 2,
    ".docx": 3,
    ".md": 4,
    ".json": 5,
  };
  const sortedItems = [...items].sort((a, b) => {
    const pa = priority[String(a.ext || "").toLowerCase()] || 99;
    const pb = priority[String(b.ext || "").toLowerCase()] || 99;
    if (pa !== pb) return pa - pb;
    return String(a.name || "").localeCompare(String(b.name || ""), "zh-CN");
  });
  resultArtifactsBlock.style.display = "block";
  resultArtifactsList.innerHTML = sortedItems
    .map((item) => {
      const viewUrl = `${API_BASE}${item.viewUrl}`;
      const downloadUrl = `${API_BASE}${item.downloadUrl}`;
      return `<li>${item.name}（${formatBytes(item.size)}）
        <a class="btn" href="${viewUrl}" target="_blank" rel="noreferrer noopener" style="margin-left:8px;">查看</a>
        <a class="btn btn-primary" href="${downloadUrl}" target="_blank" rel="noreferrer noopener" style="margin-left:6px;">下载</a>
      </li>`;
    })
    .join("");
}

async function openExecutionResultDialog(toolName, task) {
  const st = task.status || "";
  resultDialogTitle.textContent = `执行结果：${toolName}`;
  resultStatusLine.textContent = `状态：${statusText(st)}`;

  const out = normalizeOutputText(task.stdout);
  const err = normalizeOutputText(task.stderr);

  if (st === "success") {
    resultStdout.textContent =
      out ||
      "（暂无标准输出。若插件未向标准输出写入内容则此处为空；可查看下方日志文件到 data/logs 目录打开完整日志。）";
    if (err) {
      resultStderrBlock.style.display = "block";
      resultStderr.textContent = err;
    } else {
      resultStderrBlock.style.display = "none";
      resultStderr.textContent = "";
    }
    lastResultClipboardText = out;
  } else {
    resultStdout.textContent = out || "（标准输出为空）";
    resultStderrBlock.style.display = "block";
    resultStderr.textContent = err || "（错误输出为空，请查看日志）";
    lastResultClipboardText = [out, err].filter(Boolean).join("\n\n--- stderr ---\n\n") || err || "";
  }

  resultMetaLine.textContent = [
    task.taskId ? `任务 ID：${task.taskId}` : "",
    task.logFile ? `日志文件：${task.logFile}` : "",
    task.returnCode !== undefined && task.returnCode !== null ? `退出码：${task.returnCode}` : "",
  ]
    .filter(Boolean)
    .join(" ｜ ");

  try {
    const artifactsData = await requestJson(`${API_BASE}/api/tasks/${task.taskId}/artifacts`);
    renderArtifacts((artifactsData && artifactsData.items) || []);
  } catch (_) {
    renderArtifacts([]);
  }

  resultDialog.showModal();
}

async function copyExecutionResult() {
  const text = lastResultClipboardText;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const prev = copyResultBtn.textContent;
    copyResultBtn.textContent = "已复制";
    setTimeout(() => {
      copyResultBtn.textContent = prev;
    }, 1600);
  } catch (_) {
    histories.unshift(`复制输出失败（浏览器权限）：请手动框选对话框内文本`);
    renderLists();
  }
}

async function pollTask(taskId, toolName) {
  const start = Date.now();
  while (true) {
    const task = await requestJson(`${API_BASE}/api/tasks/${taskId}`);
    queueMap[taskId] = `${toolName} - ${statusText(task.status)}`;
    renderLists();
    if (["success", "failed", "timeout"].includes(task.status)) {
      delete queueMap[taskId];
      await openExecutionResultDialog(toolName, task);
      const msg = `${toolName} ${statusText(task.status)}：task=${taskId}${task.logFile ? `，日志：${task.logFile}` : ""}`;
      histories.unshift(msg);
      if (histories.length > 30) histories.pop();
      renderLists();
      return;
    }
    if (Date.now() - start > 1000 * 1800) {
      delete queueMap[taskId];
      histories.unshift(`${toolName} 轮询超时：task=${taskId}`);
      renderLists();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

async function runTool(event) {
  event.preventDefault();
  if (!activeTool) return;
  const formData = new FormData(runForm);
  const params = {};
  for (const [key, value] of formData.entries()) params[key] = normalizeValue(value);
  try {
    const result = await requestJson(`${API_BASE}/api/tools/${activeTool.id}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params }),
    });
    queueMap[result.taskId] = `${activeTool.name} - 等待执行`;
    renderLists();
    runDialog.close();
    await pollTask(result.taskId, activeTool.name);
  } catch (error) {
    histories.unshift(`${activeTool.name} 提交失败：${error.message}`);
    renderLists();
  }
}

function updateImportFormByType() {
  const mode = importTypeEl.value;
  importLocalPathRow.style.display = mode === "local" ? "grid" : "none";
  importZipPathRow.style.display = mode === "zip" ? "grid" : "none";
  importGitRepoRow.style.display = mode === "git" ? "grid" : "none";
  importGitRefRow.style.display = mode === "git" ? "grid" : "none";
}

async function submitImport(event) {
  event.preventDefault();
  const mode = importTypeEl.value;
  const overwrite = importOverwriteEl.checked;
  const runInstall = importRunInstallEl ? importRunInstallEl.checked : true;
  let url = "";
  let payload = { overwrite, run_install: runInstall };
  if (mode === "local") {
    url = `${API_BASE}/api/plugins/register-local`;
    payload.path = importLocalPathEl.value.trim();
  } else if (mode === "zip") {
    url = `${API_BASE}/api/plugins/upload`;
    payload.zip_path = importZipPathEl.value.trim();
  } else {
    url = `${API_BASE}/api/plugins/import-git`;
    payload.repo_url = importGitRepoEl.value.trim();
    payload.ref = importGitRefEl.value.trim();
  }

  try {
    const result = await requestJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const plugin = result.plugin || {};
    const installSteps = (result.install && result.install.steps) || [];
    const installMsg = installSteps.length ? `，安装步骤：${installSteps.length}` : "";
    histories.unshift(`插件导入成功：${plugin.name || "-"} (${plugin.id || "-"})${installMsg}`);
    importDialog.close();
    await bootstrapTools();
  } catch (error) {
    histories.unshift(`插件导入失败：${error.message}`);
  }
  renderLists();
}

async function bootstrapTools() {
  try {
    tools = await fetchTools();
    renderGroups();
    renderTools();
  } catch (error) {
    toolGridEl.innerHTML = `<div class="card muted">加载工具失败：${error.message}</div>`;
  }
}

searchInputEl.addEventListener("input", renderTools);
statusFilterEl.addEventListener("change", renderTools);
runForm.addEventListener("submit", runTool);
cancelRunBtn.addEventListener("click", () => runDialog.close());
copyResultBtn.addEventListener("click", () => {
  copyExecutionResult();
});
importPluginBtn.addEventListener("click", () => importDialog.showModal());
cancelImportBtn.addEventListener("click", () => importDialog.close());
importTypeEl.addEventListener("change", updateImportFormByType);
importForm.addEventListener("submit", submitImport);

bootstrapTools();
renderLists();
updateEnvBadge(loadEnvConfig().envName);
bindEnvEvents();
updateImportFormByType();
