<script setup lang="ts">
defineProps<{
  visible: boolean;
  title: string;
  body: string;
  meta: string;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="visible"
    width="760px"
    align-center
    class="glass-dialog"
    @close="emit('close')"
  >
    <template #header>
      <div class="dialog-header">
        <p class="dialog-header__eyebrow">Tool Brief</p>
        <h3>{{ title }}</h3>
      </div>
    </template>

    <div class="usage-dialog__body">
      <pre>{{ body }}</pre>
      <p>{{ meta }}</p>
    </div>
  </el-dialog>
</template>
