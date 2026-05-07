import { computed, ref } from "vue";
import type { EnvConfig } from "@/types";

const ENV_CONFIG_KEY = "tool_platform_env_config";

function defaultEnvConfig(): EnvConfig {
  return {
    envName: "DEV",
    labelu: { url: "", username: "", password: "" },
    ssh: { host: "", username: "", password: "" },
  };
}

function loadEnvConfig(): EnvConfig {
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
  } catch {
    return defaultEnvConfig();
  }
}

export function useEnvironment() {
  const envConfig = ref<EnvConfig>(loadEnvConfig());

  function save(config: EnvConfig) {
    envConfig.value = config;
    localStorage.setItem(ENV_CONFIG_KEY, JSON.stringify(config));
  }

  const envLabel = computed(() => envConfig.value.envName || "DEV");

  return {
    envConfig,
    envLabel,
    save,
    defaultEnvConfig,
  };
}
