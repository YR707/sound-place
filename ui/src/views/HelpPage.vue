<script setup lang="ts">
// 帮助页面: 使用前提、游戏模式要求、Profile 说明、常见问题、风险告知复述
</script>

<template>
  <div class="help-page">
    <h3>使用帮助</h3>

    <section>
      <h4>1. 使用前提</h4>
      <ul>
        <li>Windows 10 1803 或更高版本(WASAPI loopback 需要)</li>
        <li>WebView2 Runtime(Win11 自带, Win10 可能需要单独安装)</li>
        <li>立体声音频输出(耳机或双声道音箱)</li>
        <li>游戏必须以"无边框窗口"模式运行(独占全屏会阻止 overlay 显示)</li>
      </ul>
    </section>

    <section>
      <h4>2. 游戏模式要求</h4>
      <p>
        <strong>必须使用无边框窗口模式</strong>, 不能用独占全屏。
        独占全屏模式下, Windows 不会渲染透明 overlay 窗口。
      </p>
      <p>
        在游戏设置中将显示模式改为"Borderless Windowed" / "无边框窗口" / "Windowed Fullscreen"。
      </p>
    </section>

    <section>
      <h4>3. Profile 配置说明</h4>
      <p>每个 Profile 描述一个游戏的检测参数, 字段含义:</p>
      <table class="config-table">
        <thead>
          <tr><th>字段</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>game_id</td><td>游戏唯一标识, 用于文件名</td></tr>
          <tr><td>name</td><td>显示名称</td></tr>
          <tr><td>process_names</td><td>游戏进程名列表(用于过滤, 空表示不过滤)</td></tr>
          <tr><td>anticheat_risk</td><td>反作弊风险等级: high / medium / low</td></tr>
          <tr><td>detection.fft_size</td><td>FFT 窗口大小(必须是 2 的幂, 建议 2048)</td></tr>
          <tr><td>detection.hop_size</td><td>FFT 跳跃长度(建议 fft_size 的一半)</td></tr>
          <tr><td>detection.onset_threshold</td><td>Onset 阈值倍数 k(阈值 = median + k*MAD)</td></tr>
          <tr><td>detection.min_event_interval_ms</td><td>最小事件间隔(去抖, 毫秒)</td></tr>
          <tr><td>sound_types[].freq_range</td><td>该声音类型的频段范围 [最低Hz, 最高Hz]</td></tr>
          <tr><td>sound_types[].min_energy_ratio</td><td>该频段最低能量占比(0.0-1.0)</td></tr>
        </tbody>
      </table>
    </section>

    <section>
      <h4>4. 快捷键</h4>
      <ul>
        <li><kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>S</kbd> — 切换覆盖显隐</li>
        <li><kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>E</kbd> — 进入编辑模式(调整位置)</li>
        <li>编辑模式下拖拽波纹组可移动位置, 点击"完成"退出</li>
      </ul>
    </section>

    <section>
      <h4>5. 常见问题</h4>

      <h5>Q: 启动捕获后没有反应?</h5>
      <p>
        A: 检查: ① 是否已启用覆盖; ② 游戏是否在播放声音; ③ profile 的 process_names
        是否匹配游戏进程名(可在任务管理器查看); ④ 游戏是否以独占全屏运行。
      </p>

      <h5>Q: 方位不准?</h5>
      <p>
        A: 立体声定位本身有局限: ① <strong>无法区分前后</strong>(声源在身后也会显示在前方雷达);
        ② 左右声道响度差小时误差大; ③ 建议使用耳机而非音箱(声道分离更清晰)。
      </p>

      <h5>Q: 会被封号吗?</h5>
      <p>
        A: 本软件不读取游戏内存、不注入进程、不修改数据, 仅分析系统音频输出(与 OBS
        录屏捕获音频行为相同)。但部分游戏的反作弊系统可能将任何 overlay 视为违规,
        <strong>使用风险由用户自行承担</strong>。建议:
      </p>
      <ul>
        <li>高风险游戏(Valorant/Vanguard)不要使用</li>
        <li>中风险游戏(猎杀对决/彩六/PUBG)谨慎使用</li>
        <li>优先用于学习样本库或单机游戏</li>
      </ul>

      <h5>Q: 配置文件在哪?</h5>
      <p>
        A: <code>%APPDATA%\sound-place\</code><br>
        - <code>settings.json</code> — 全局设置(风险标志/激活 profile/外观)<br>
        - <code>profiles\*.toml</code> — 各游戏的检测 profile
      </p>

      <h5>Q: 如何卸载?</h5>
      <p>
        A: 删除 exe 文件 + 删除 <code>%APPDATA%\sound-place\</code> 目录即可。
        软件不写注册表, 不留其他痕迹。
      </p>
    </section>

    <section>
      <h4>6. 风险告知复述</h4>
      <p>
        本软件基于立体声音频分析, <strong>无法区分声音前后方位</strong>。
        软件假设声音来自玩家正前方, 仅显示水平左右方位。
        部分游戏的反作弊系统可能将 overlay 视为违规,
        使用导致的封号后果由用户自行承担, 开发者不承担任何责任。
      </p>
    </section>
  </div>
</template>

<style scoped>
.help-page {
  color: #ddd;
  font-size: 14px;
  line-height: 1.7;
  max-width: 800px;
}

h3 {
  margin: 0 0 16px;
  color: #fff;
  font-size: 18px;
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

h5 {
  margin: 12px 0 6px;
  color: #44a4ff;
  font-size: 13px;
}

ul {
  margin: 6px 0;
  padding-left: 20px;
}

li {
  margin: 4px 0;
}

code {
  background: #111;
  color: #06d6a0;
  padding: 1px 6px;
  border-radius: 2px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
}

kbd {
  background: #333;
  border: 1px solid #555;
  border-radius: 3px;
  padding: 1px 6px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.config-table th,
.config-table td {
  border: 1px solid #333;
  padding: 6px 10px;
  text-align: left;
  font-size: 12px;
}

.config-table th {
  background: #2a2a2a;
}
</style>
