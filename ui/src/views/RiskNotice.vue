<script setup lang="ts">
// 风险告知弹窗
// 首次启动强制显示, 用户必须勾选"我已知晓风险"才能继续

import { ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';

const emit = defineEmits<{ (e: 'accepted'): void }>();

const checked = ref(false);
const saving = ref(false);

async function confirm() {
  if (!checked.value || saving.value) return;
  saving.value = true;
  try {
    await invoke('accept_risk');
    emit('accepted');
  } catch (e) {
    console.error('接受风险失败', e);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="risk-notice-overlay">
    <div class="risk-notice-card">
      <h2>使用前风险告知</h2>

      <section>
        <h3>1. 立体声定位的物理限制</h3>
        <p>
          本软件基于<strong>立体声音频</strong>分析声音方位, 这是物理层面的限制:
          <strong>无法区分声音来自前方还是后方</strong>。
          软件假设声音来自玩家正前方, 仅显示水平左右方位 (-90° 到 +90°)。
          游戏中如果敌人在身后, 软件仍会在前方雷达上显示, 请以游戏内实际为准。
        </p>
      </section>

      <section>
        <h3>2. 反作弊风险分级</h3>
        <table class="risk-table">
          <thead>
            <tr><th>等级</th><th>游戏示例</th><th>说明</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><span class="risk-high">高风险</span></td>
              <td>Valorant (Vanguard)、Apex (EAC 内核)</td>
              <td>内核级反作弊, 理论上可能检测到任何叠加层。强烈建议不要使用</td>
            </tr>
            <tr>
              <td><span class="risk-medium">中等风险</span></td>
              <td>猎杀对决 (EAC)、彩六 (BattlEye)、PUBG (BattlEye)</td>
              <td>用户态反作弊, 通常不拦截透明 overlay, 但不保证</td>
            </tr>
            <tr>
              <td><span class="risk-low">低风险</span></td>
              <td>单机游戏、自建学习样本库</td>
              <td>无反作弊, 完全安全</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h3>3. 合规声明</h3>
        <p>
          本软件<strong>不读取游戏内存</strong>, <strong>不挂钩图形 API</strong>,
          <strong>不注入游戏进程</strong>, <strong>不修改游戏数据</strong>。
          仅分析系统音频输出 (WASAPI loopback), 与 OBS 录屏捕获音频的行为相同。
        </p>
        <p>
          但部分游戏的反作弊系统可能将任何 overlay 视为违规,
          <strong>使用本软件导致的封号后果由用户自行承担</strong>,
          开发者不承担任何责任。
        </p>
      </section>

      <label class="check-row">
        <input type="checkbox" v-model="checked" />
        <span>我已知晓上述风险, 理解软件的物理限制与合规边界, 愿意自行承担使用风险</span>
      </label>

      <div class="button-row">
        <button class="confirm-btn" :disabled="!checked || saving" @click="confirm">
          {{ saving ? '保存中...' : '确认继续' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-notice-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.risk-notice-card {
  background: #1e1e1e;
  border: 1px solid #444;
  border-radius: 8px;
  padding: 24px;
  max-width: 720px;
  max-height: 90vh;
  overflow-y: auto;
  color: #ddd;
  font-size: 14px;
  line-height: 1.6;
}

.risk-notice-card h2 {
  margin: 0 0 16px;
  color: #fff;
  font-size: 20px;
}

.risk-notice-card h3 {
  margin: 20px 0 8px;
  color: #ff9d4d;
  font-size: 15px;
}

.risk-notice-card p {
  margin: 8px 0;
}

.risk-table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.risk-table th,
.risk-table td {
  border: 1px solid #444;
  padding: 6px 10px;
  text-align: left;
  font-size: 13px;
}

.risk-table th {
  background: #2a2a2a;
}

.risk-high { color: #ef476f; font-weight: bold; }
.risk-medium { color: #ffd166; font-weight: bold; }
.risk-low { color: #06d6a0; font-weight: bold; }

.check-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 20px 0;
  padding: 12px;
  background: #2a2a2a;
  border-radius: 4px;
  cursor: pointer;
}

.check-row input {
  margin-top: 3px;
}

.button-row {
  display: flex;
  justify-content: flex-end;
}

.confirm-btn {
  background: #44a4ff;
  color: white;
  border: none;
  padding: 8px 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.confirm-btn:disabled {
  background: #555;
  cursor: not-allowed;
}
</style>
