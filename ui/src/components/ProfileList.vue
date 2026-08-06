<script setup lang="ts">
// Profile 列表展示与操作

import type { ProfileListItem } from '@/types/profile';

defineProps<{
  profiles: ProfileListItem[];
  activeProfileId: string;
}>();

const emit = defineEmits<{
  edit: [id: string];
  activate: [id: string];
}>();

const riskClass = (risk: string) => {
  if (risk === 'high') return 'risk-high';
  if (risk === 'medium') return 'risk-medium';
  return 'risk-low';
};
</script>

<template>
  <div class="profile-list">
    <h4>Profiles</h4>
    <div
      v-for="p in profiles"
      :key="p.game_id"
      class="profile-item"
      :class="{ active: p.game_id === activeProfileId }"
    >
      <div class="profile-info">
        <div class="profile-name">{{ p.name }}</div>
        <div class="profile-id">{{ p.game_id }}</div>
        <span class="risk-tag" :class="riskClass(p.anticheat_risk)">
          {{ p.anticheat_risk }}
        </span>
      </div>
      <div class="profile-actions">
        <button @click="emit('edit', p.game_id)">编辑</button>
        <button
          v-if="p.game_id !== activeProfileId"
          @click="emit('activate', p.game_id)"
        >激活</button>
        <span v-else class="active-tag">已激活</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-list {
  width: 280px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px;
  overflow-y: auto;
}

.profile-list h4 {
  margin: 0 0 10px;
  color: #fff;
  font-size: 14px;
}

.profile-item {
  padding: 8px;
  margin-bottom: 6px;
  background: #222;
  border-radius: 3px;
  cursor: pointer;
  border: 1px solid transparent;
}

.profile-item.active {
  border-color: #44a4ff;
}

.profile-info {
  margin-bottom: 6px;
}

.profile-name {
  color: #fff;
  font-size: 13px;
}

.profile-id {
  color: #888;
  font-size: 11px;
  font-family: monospace;
}

.risk-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 2px;
  font-size: 10px;
  margin-top: 2px;
}

.risk-high { background: #4a1f1f; color: #ef476f; }
.risk-medium { background: #4a401f; color: #ffd166; }
.risk-low { background: #1f4a2f; color: #06d6a0; }

.profile-actions {
  display: flex;
  gap: 6px;
}

.profile-actions button {
  background: #333;
  color: #ddd;
  border: 1px solid #444;
  padding: 3px 8px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 11px;
}

.active-tag {
  color: #06d6a0;
  font-size: 11px;
}
</style>
