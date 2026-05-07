import type { ArtifactItem, ImportFormState, TaskDetail, TaskRunResponse, ToolItem } from "@/types";
import { getApiBase } from "@/utils/format";

const API_BASE = getApiBase();

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "请求失败");
  }
  return payload.data as T;
}

export async function fetchTools(): Promise<ToolItem[]> {
  const data = await requestJson<{ tools: ToolItem[] }>("/api/tools");
  return data.tools || [];
}

export async function runTool(toolId: string, params: Record<string, string>): Promise<TaskRunResponse> {
  return requestJson<TaskRunResponse>(`/api/tools/${toolId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params }),
  });
}

export async function fetchTask(taskId: string): Promise<TaskDetail> {
  return requestJson<TaskDetail>(`/api/tasks/${taskId}`);
}

export async function fetchArtifacts(taskId: string): Promise<ArtifactItem[]> {
  const data = await requestJson<{ items: ArtifactItem[] }>(`/api/tasks/${taskId}/artifacts`);
  return data.items || [];
}

export async function importPlugin(form: ImportFormState): Promise<{ plugin?: ToolItem; install?: { steps?: unknown[] } }> {
  if (form.mode === "local") {
    return requestJson("/api/plugins/register-local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: form.localPath.trim(),
        overwrite: form.overwrite,
        run_install: form.runInstall,
      }),
    });
  }
  if (form.mode === "zip") {
    return requestJson("/api/plugins/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zip_path: form.zipPath.trim(),
        overwrite: form.overwrite,
        run_install: form.runInstall,
      }),
    });
  }
  return requestJson("/api/plugins/import-git", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: form.repoUrl.trim(),
      ref: form.ref.trim(),
      overwrite: form.overwrite,
      run_install: form.runInstall,
    }),
  });
}

export function buildApiUrl(relativePath: string): string {
  return `${API_BASE}${relativePath}`;
}
