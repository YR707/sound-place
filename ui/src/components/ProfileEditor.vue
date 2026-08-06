<script setup lang="ts">
// Profile TOML 编辑器

defineProps<{
  profileId: string;
  content: string;
  error: string;
}>();

const emit = defineEmits<{
  'update:content': [value: string];
  save: [];
  cancel: [];
}>();
</script>

<template>
  <div class="profile-editor">
    <div class="editor-header">
      <h4>编辑: {{ profileId }}.toml</h4>
      <div class="editor-actions">
        <button @click="emit('save')">保存</button>
        <button class="btn-cancel" @click="emit('cancel')">取消</button>
      </div>
    </div>
    <textarea
      :value="content"
      @input="emit('update:content', ($event.target as HTMLTextAreaElement).value)"
      class="toml-editor"
    ></textarea>
    <div v-if="error" class="error-bar">{{ error }}</div>
  </div>
</template>

<style scoped>
.profile-editor {
  flex: 1;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.editor-header h4 {
  margin: 0;
  color: #fff;
  font-size: 14px;
}

.editor-actions {
  display: flex;
  gap: 6px;
}

.editor-header button {
  background: #44a4ff;
  color: white;
  border: none;
  padding: 4px 12px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.editor-header .btn-cancel {
  background: #333;
  border: 1px solid #444;
}

.toml-editor {
  flex: 1;
  background: #111;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 3px;
  padding: 8px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  resize: none;
}

.error-bar {
  background: #4a1f1f;
  color: #ff8888;
  padding: 8px 12px;
  border: 1px solid #5a2a2a;
  border-radius: 3px;
  font-size: 12px;
  margin-top: 8px;
}
</style>
