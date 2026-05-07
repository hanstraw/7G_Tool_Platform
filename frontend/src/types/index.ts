export type ToolStatus = "ready" | "draft" | "offline" | "running" | "success" | "failed" | "timeout";

export interface ToolParam {
  key: string;
  label?: string;
  type?: string;
  required?: boolean;
  default?: string;
  options?: string[];
  cli_arg?: string;
}

export interface ToolItem {
  id: string;
  name: string;
  group?: string;
  desc?: string;
  status?: ToolStatus;
  version?: string;
  runtime?: string;
  tags?: string[];
  usage?: string;
  params?: ToolParam[];
}

export interface ArtifactItem {
  index?: number;
  name: string;
  size: number;
  ext?: string;
  viewUrl: string;
  downloadUrl: string;
}

export interface TaskRunResponse {
  taskId: string;
  status: string;
}

export interface TaskDetail {
  taskId: string;
  toolId?: string;
  toolName?: string;
  status: ToolStatus;
  params?: Record<string, string>;
  createdAt?: string;
  updatedAt?: string;
  startedAt?: string;
  endedAt?: string;
  returnCode?: number | null;
  stdout?: string;
  stderr?: string;
  command?: string;
  logFile?: string;
  artifacts?: ArtifactItem[];
}

export interface QueueItem {
  taskId: string;
  toolName: string;
  status: ToolStatus | string;
  progress?: number | null;
  createdAt: number;
}

export interface HistoryItem {
  id: string;
  toolName: string;
  summary: string;
  status: ToolStatus | string;
  timestamp: number;
}

export interface LabeluEnvConfig {
  url: string;
  username: string;
  password: string;
}

export interface SshEnvConfig {
  host: string;
  username: string;
  password: string;
}

export interface EnvConfig {
  envName: string;
  labelu: LabeluEnvConfig;
  ssh: SshEnvConfig;
}

export type ImportMode = "local" | "zip" | "git";

export interface ImportFormState {
  mode: ImportMode;
  localPath: string;
  zipPath: string;
  repoUrl: string;
  ref: string;
  overwrite: boolean;
  runInstall: boolean;
}
