import type { ToolItem, ToolStatus } from "@/types";

export function getApiBase(): string {
  const envBase = import.meta.env.VITE_API_BASE as string | undefined;
  if (envBase && envBase.trim()) {
    return envBase.trim().replace(/\/$/, "");
  }
  const protocol = window.location.protocol || "http:";
  const hostname = window.location.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:8787`;
}

export function statusText(status?: string): string {
  switch (status) {
    case "ready":
      return "可用";
    case "draft":
      return "草稿";
    case "offline":
      return "停用";
    case "running":
      return "运行中";
    case "success":
      return "成功";
    case "failed":
      return "失败";
    case "timeout":
      return "超时";
    default:
      return "未知";
  }
}

export function statusTone(status?: string): "success" | "warning" | "danger" | "info" {
  switch (status) {
    case "ready":
    case "success":
      return "success";
    case "draft":
      return "warning";
    case "failed":
    case "offline":
      return "danger";
    default:
      return "info";
  }
}

export function normalizeValue(value: unknown): string {
  const text = String(value ?? "").trim();
  const firstChar = text.charAt(0);
  const lastChar = text.charAt(text.length - 1);
  if (text.length >= 2 && firstChar === lastChar && ['"', "'"].includes(firstChar)) {
    return text.slice(1, -1).trim();
  }
  return text;
}

export function normalizeOutputText(text?: string): string {
  return String(text ?? "").replace(/\r\n/g, "\n").trimEnd();
}

export function formatBytes(bytes?: number): string {
  const value = Number(bytes || 0);
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function iconSeed(tool: ToolItem): string {
  return (tool.name || tool.id || "?").trim().slice(0, 1).toUpperCase();
}

export function buildUsageDoc(tool: ToolItem): string {
  if (tool.usage?.trim()) return tool.usage.trim();
  const params = (tool.params || []).map((item) => `- ${item.label || item.key}（${item.required ? "必填" : "可选"}）`);
  return [`工具名称：${tool.name}`, "", "用途：", tool.desc || "暂无描述", "", "参数：", params.join("\n") || "无"].join("\n");
}

export function artifactPriority(ext?: string): number {
  const value = String(ext || "").toLowerCase();
  if (value === ".html" || value === ".htm") return 1;
  if (value === ".pdf") return 2;
  if (value === ".docx") return 3;
  if (value === ".md") return 4;
  if (value === ".json") return 5;
  return 99;
}

export function sortArtifacts<T extends { ext?: string; name: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const priorityDiff = artifactPriority(a.ext) - artifactPriority(b.ext);
    if (priorityDiff !== 0) return priorityDiff;
    return a.name.localeCompare(b.name, "zh-CN");
  });
}

export function toolMatches(tool: ToolItem, group: string, keyword: string, status: string): boolean {
  const inGroup = group === "全部工具" || (tool.group || "未分组") === group;
  const inStatus = status === "all" || (tool.status || "ready") === status;
  const searchable = `${tool.name || ""} ${tool.desc || ""} ${(tool.tags || []).join(" ")}`.toLowerCase();
  const inKeyword = !keyword || searchable.includes(keyword.toLowerCase());
  return inGroup && inStatus && inKeyword;
}

export function percentByStatus(status: ToolStatus | string): number | null {
  if (status === "running") return 52;
  if (status === "success") return 100;
  if (status === "pending") return 12;
  return null;
}
