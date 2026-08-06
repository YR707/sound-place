<script setup lang="ts">
// 关于页面
</script>

<template>
  <div class="about-page">
    <h3>SoundPlace</h3>

    <div class="info-block">
      <div class="info-row">
        <span class="label">版本:</span>
        <span class="value">0.1.0</span>
      </div>
      <div class="info-row">
        <span class="label">许可证:</span>
        <span class="value">MIT License</span>
      </div>
      <div class="info-row">
        <span class="label">开源地址:</span>
        <a href="https://github.com/YR707/sound-place" target="_blank">
          github.com/YR707/sound-place
        </a>
      </div>
    </div>

    <section>
      <h4>软件简介</h4>
      <p>
        SoundPlace 是一个游戏声音方位分析学习工具, 通过分析系统音频输出
        (WASAPI loopback) 实时检测游戏中的瞬态声音事件(脚步、枪声、载具等),
        估算声音来源的水平方位, 在屏幕准星左右以波纹条形式可视化显示,
        帮助用户训练对声音方位的感知能力。
      </p>
    </section>

    <section>
      <h4>技术栈</h4>
      <ul>
        <li>后端: Rust + Tauri 2</li>
        <li>音频捕获: WASAPI loopback (windows-sys + wasapi crate)</li>
        <li>信号处理: realfft + rustfft (FFT / GCC-PHAT 互相关)</li>
        <li>前端: Vue 3 + TypeScript + Vite</li>
        <li>渲染: Canvas 2D</li>
      </ul>
    </section>

    <section>
      <h4>免责声明</h4>
      <p>
        本软件基于立体声音频分析, 受物理原理限制, <strong>无法区分声音的前后方位</strong>,
        软件假设声音来自玩家正前方, 仅显示水平左右方位。
      </p>
      <p>
        本软件<strong>不读取游戏内存</strong>, <strong>不挂钩图形 API</strong>,
        <strong>不注入游戏进程</strong>, <strong>不修改游戏数据</strong>,
        仅分析系统音频输出, 行为与 OBS 录屏捕获音频相同。
      </p>
      <p>
        但部分游戏的反作弊系统可能将任何 overlay 视为违规,
        <strong>使用本软件导致的封号或其他任何后果由用户自行承担</strong>,
        软件开发者不承担任何责任。
      </p>
      <p>
        本软件为开源项目(MIT License), 源代码完全公开, 可自行审计与修改。
      </p>
    </section>

    <section>
      <h4>鸣谢</h4>
      <ul>
        <li>realfft / rustfft — FFT 计算</li>
        <li>wasapi-rs — WASAPI Rust 封装</li>
        <li>Tauri — 跨平台桌面应用框架</li>
        <li>Vue.js — 渐进式前端框架</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.about-page {
  color: #ddd;
  font-size: 14px;
  line-height: 1.7;
  max-width: 700px;
}

h3 {
  margin: 0 0 16px;
  color: #fff;
  font-size: 22px;
}

.info-block {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.info-row {
  margin: 6px 0;
}

.label {
  color: #888;
  margin-right: 8px;
}

.value {
  color: #ddd;
}

a {
  color: #44a4ff;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

section {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

h4 {
  margin: 0 0 10px;
  color: #ff9d4d;
  font-size: 15px;
}

ul {
  margin: 6px 0;
  padding-left: 20px;
}

li {
  margin: 4px 0;
}
</style>
