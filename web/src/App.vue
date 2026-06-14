<template>
  <div class="app">
    <header class="header">
      <h1>⚡ MCP Tool Hub</h1>
      <div class="header-info">
        <span :class="['status-dot', connected ? 'online' : 'offline']"></span>
        <span v-if="status">{{ status.plugins_loaded }}/{{ status.plugins_total }} 插件</span>
      </div>
    </header>

    <nav class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab', { active: currentTab === tab.key }]"
        @click="currentTab = tab.key"
      >{{ tab.label }}</button>
    </nav>

    <!-- 插件列表 -->
    <section v-if="currentTab === 'plugins'" class="section">
      <div class="toolbar">
        <button class="btn btn-primary" @click="reloadServer" :disabled="reloading">
          {{ reloading ? '重载中...' : '🔄 重载服务' }}
        </button>
      </div>
      <div class="plugin-grid">
        <div v-for="p in plugins" :key="p.name" class="plugin-card">
          <div class="plugin-header">
            <div class="plugin-header-left">
              <span :class="['status-dot', p.status]" :title="p.status"></span>
              <span class="plugin-name">{{ p.display_name }}</span>
            </div>
            <button class="btn btn-sm btn-icon" @click="openReadme(p)" title="查看说明">📖 说明</button>
          </div>
          <div class="plugin-meta">
            <span>v{{ p.version }}</span>
            <span>{{ p.tool_count }} 工具</span>
          </div>
          <div class="plugin-actions">
            <div class="switch-group">
              <label class="switch" title="启用/禁用插件">
                <input type="checkbox" :checked="p.enabled" @change="toggleEnable(p)" />
                <span class="slider"></span>
              </label>
              <span class="switch-label">{{ p.enabled ? '已启用' : '已禁用' }}</span>
            </div>
            <div class="switch-group">
              <label class="switch" title="MCP 开关">
                <input type="checkbox" :checked="p.mcp_enabled" @change="toggleMcp(p)" />
                <span class="slider slider-green"></span>
              </label>
              <span class="switch-label">{{ p.mcp_enabled ? 'MCP ON' : 'MCP OFF' }}</span>
            </div>
            <div class="plugin-actions-spacer"></div>
            <button v-if="p.has_config" class="btn btn-sm" @click="openConfig(p)">⚙️ 设置</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 日志 -->
    <section v-if="currentTab === 'logs'" class="section">
      <div class="toolbar">
        <select v-model="logFilter" @change="fetchLogs">
          <option value="">全部插件</option>
          <option v-for="p in plugins" :key="p.name" :value="p.name">{{ p.display_name }}</option>
        </select>
        <button class="btn" @click="fetchLogs">🔄 刷新</button>
        <button class="btn btn-danger" @click="clearLogs">🗑 清空</button>
        <button class="btn" @click="pruneLogs">🧹 清理过期</button>
      </div>
      <div class="log-list">
        <div v-for="log in logs" :key="log.id" class="log-item">
          <span class="log-time">{{ log.created_at }}</span>
          <span :class="['log-level', log.level?.toLowerCase()]">{{ log.level }}</span>
          <span class="log-plugin" v-if="log.plugin">[{{ log.plugin }}]</span>
          <span class="log-msg">{{ log.message?.replace(/\n/g, ' ') }}</span>
        </div>
        <div v-if="!logs.length" class="empty">暂无日志</div>
      </div>
    </section>

    <!-- 配置弹窗 -->
    <div v-if="showConfigModal" class="modal-overlay" @click.self="showConfigModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>⚙️ {{ selectedPlugin?.display_name }} 设置</h3>
          <button class="btn btn-sm" @click="showConfigModal = false">✕</button>
        </div>
        <div v-if="!configSchema || !Object.keys(configSchema).length" class="empty">该插件无可配置项</div>
        <form v-else class="config-form" @submit.prevent="saveConfig">
          <div v-for="(field, key) in configSchema" :key="key" class="form-group">
            <label>{{ field.label || key }}</label>
            <span v-if="field.description" class="hint">{{ field.description }}</span>
            <select v-if="field.choices" v-model="configData[key]">
              <option v-for="c in field.choices" :key="c" :value="c">{{ c }}</option>
            </select>
            <input v-else-if="field.type === 'boolean'" type="checkbox" v-model="configData[key]" />
            <input v-else-if="field.type === 'number' || field.type === 'integer'" type="number" v-model.number="configData[key]" />
            <textarea v-else-if="field.type === 'text'" v-model="configData[key]" rows="3"></textarea>
            <input v-else type="text" v-model="configData[key]" />
          </div>
          <div class="modal-actions">
            <button type="button" class="btn" @click="showConfigModal = false">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="saving">{{ saving ? '保存中...' : '💾 保存' }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- README 弹窗 -->
    <div v-if="showReadmeModal" class="modal-overlay" @click.self="showReadmeModal = false">
      <div class="modal modal-wide">
        <div class="modal-header">
          <h3>📖 {{ selectedPlugin?.display_name }} 说明</h3>
          <button class="btn btn-sm" @click="showReadmeModal = false">✕</button>
        </div>
        <div class="readme-content" v-html="pluginReadme"></div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" :class="['toast', toast.type]">{{ toast.msg }}</div>
  </div>
</template>

<script>
import api from './api'
import { marked } from 'marked'

export default {
  data() {
    return {
      connected: false,
      status: null,
      plugins: [],
      currentTab: 'plugins',
      tabs: [
        { key: 'plugins', label: '📦 插件' },
        { key: 'logs', label: '📋 日志' },
      ],
      reloading: false,
      selectedPlugin: null,
      showConfigModal: false,
      showReadmeModal: false,
      pluginReadme: '',
      configSchema: {},
      configData: {},
      saving: false,
      logs: [],
      logFilter: '',
      toast: null,
    }
  },
  async mounted() {
    await this.checkHealth()
    if (this.connected) {
      await Promise.all([this.fetchStatus(), this.fetchPlugins()])
    }
  },
  methods: {
    async checkHealth() {
      try {
        await api.health()
        this.connected = true
      } catch {
        this.connected = false
      }
    },
    async fetchStatus() {
      const { data } = await api.serverStatus()
      this.status = data
    },
    async fetchPlugins() {
      const { data } = await api.listPlugins()
      this.plugins = data.plugins
    },
    async reloadServer() {
      this.reloading = true
      try {
        await api.serverReload()
        await Promise.all([this.fetchStatus(), this.fetchPlugins()])
        this.showToast('重载完成', 'success')
      } catch (e) {
        this.showToast('重载失败: ' + (e.response?.data?.detail || e.message), 'error')
      } finally {
        this.reloading = false
      }
    },
    async toggleEnable(plugin) {
      try {
        if (plugin.enabled) {
          await api.disablePlugin(plugin.name)
        } else {
          await api.enablePlugin(plugin.name)
        }
        await this.fetchPlugins()
        this.showToast(`${plugin.display_name} 已${plugin.enabled ? '禁用' : '启用'}`, 'success')
      } catch (e) {
        this.showToast('操作失败: ' + (e.response?.data?.detail || e.message), 'error')
      }
    },
    async toggleMcp(plugin) {
      try {
        await api.togglePluginMcp(plugin.name, !plugin.mcp_enabled)
        await this.fetchPlugins()
        this.showToast(`${plugin.display_name} MCP 已${plugin.mcp_enabled ? '关闭' : '开启'}`, 'success')
      } catch (e) {
        this.showToast('操作失败: ' + (e.response?.data?.detail || e.message), 'error')
      }
    },
    async openConfig(plugin) {
      this.selectedPlugin = plugin
      this.showConfigModal = true
      try {
        const { data } = await api.getPluginConfig(plugin.name)
        this.configSchema = data.schema_info || {}
        this.configData = { ...data.config } || {}
      } catch {
        this.configSchema = {}
        this.configData = {}
      }
    },
    async openReadme(plugin) {
      this.selectedPlugin = plugin
      this.showReadmeModal = true
      try {
        const { data } = await api.getPlugin(plugin.name)
        this.pluginReadme = marked(data.readme || '暂无说明')
      } catch {
        this.pluginReadme = '无法加载说明'
      }
    },
    async saveConfig() {
      this.saving = true
      try {
        await api.updatePluginConfig(this.selectedPlugin.name, this.configData)
        this.showToast('配置已保存', 'success')
        this.showConfigModal = false
      } catch (e) {
        this.showToast('保存失败: ' + (e.response?.data?.detail || e.message), 'error')
      } finally {
        this.saving = false
      }
    },
    async fetchLogs() {
      try {
        const params = { limit: 200 }
        if (this.logFilter) params.plugin = this.logFilter
        const { data } = await api.getLogs(params)
        this.logs = data.logs
      } catch {
        this.logs = []
      }
    },
    async clearLogs() {
      try {
        const { data } = await api.clearLogs(this.logFilter || undefined)
        this.showToast(`已删除 ${data.deleted} 条日志`, 'success')
        await this.fetchLogs()
      } catch (e) {
        this.showToast('清空失败', 'error')
      }
    },
    async pruneLogs() {
      try {
        const { data } = await api.pruneLogs()
        this.showToast(`已清理 ${data.deleted} 条过期日志`, 'success')
        await this.fetchLogs()
      } catch (e) {
        this.showToast('清理失败', 'error')
      }
    },
    showToast(msg, type = 'info') {
      this.toast = { msg, type }
      setTimeout(() => { this.toast = null }, 3000)
    },
  },
  watch: {
    currentTab(tab) {
      if (tab === 'logs') this.fetchLogs()
    },
  },
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f0f; color: #e0e0e0; }

.app { max-width: 960px; margin: 0 auto; padding: 20px; }

.header { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid #2a2a2a; }
.header h1 { font-size: 1.5rem; font-weight: 600; }
.header-info { display: flex; align-items: center; gap: 8px; color: #999; font-size: 0.9rem; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: #4caf50; box-shadow: 0 0 6px #4caf50; }
.status-dot.offline { background: #f44336; }

.tabs { display: flex; gap: 4px; margin: 16px 0; background: #1a1a1a; border-radius: 8px; padding: 4px; }
.tab { flex: 1; padding: 10px; border: none; background: transparent; color: #999; cursor: pointer; border-radius: 6px; font-size: 0.95rem; transition: all 0.2s; }
.tab.active { background: #2a2a2a; color: #fff; }
.tab:hover { color: #ddd; }

.section { padding: 8px 0; }

.toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }

.plugin-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.plugin-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 16px; cursor: pointer; transition: border-color 0.2s; }
.plugin-card:hover { border-color: #444; }

.plugin-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.plugin-header-left { display: flex; align-items: center; gap: 8px; }
.plugin-name { font-weight: 600; font-size: 1rem; }
.plugin-meta { color: #777; font-size: 0.8rem; display: flex; gap: 12px; margin-bottom: 12px; }
.plugin-actions { display: flex; gap: 16px; align-items: center; }
.plugin-actions-spacer { flex: 1; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.status-dot.loaded { background: #4caf50; }
.status-dot.unloaded { background: #78909c; }
.status-dot.error { background: #f44336; }

/* Switch */
.switch { position: relative; width: 36px; height: 20px; display: inline-block; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; inset: 0; background: #333; border-radius: 20px; cursor: pointer; transition: 0.3s; }
.slider::before { content: ''; position: absolute; height: 14px; width: 14px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: 0.3s; }
.switch input:checked + .slider { background: #1976d2; }
.slider-green { position: absolute; inset: 0; background: #333; border-radius: 20px; cursor: pointer; transition: 0.3s; }
.slider-green::before { content: ''; position: absolute; height: 14px; width: 14px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: 0.3s; }
.switch input:checked + .slider-green { background: #388e3c; }
.switch input:checked + .slider::before { transform: translateX(16px); }

/* Config */
.config-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.config-form { display: flex; flex-direction: column; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label { font-weight: 500; font-size: 0.9rem; }
.hint { font-size: 0.8rem; color: #888; }
.form-group input[type="text"],
.form-group input[type="number"],
.form-group select,
.form-group textarea {
  background: #1a1a1a; border: 1px solid #333; border-radius: 6px;
  padding: 8px 12px; color: #e0e0e0; font-size: 0.9rem; outline: none;
}
.form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: #1976d2; }
.form-group input[type="checkbox"] { width: 18px; height: 18px; }

/* Logs */
.log-list { display: flex; flex-direction: column; gap: 2px; max-height: 600px; overflow-y: auto; }
.log-item { display: flex; gap: 8px; padding: 6px 8px; font-size: 0.82rem; font-family: 'Cascadia Code', 'Fira Code', monospace; background: #1a1a1a; border-radius: 4px; }
.log-time { color: #666; white-space: nowrap; }
.log-level { font-weight: 600; min-width: 48px; }
.log-level.info { color: #42a5f5; }
.log-level.warning { color: #ffa726; }
.log-level.error { color: #ef5350; }
.log-level.debug { color: #666; }
.log-plugin { color: #ab47bc; min-width: 80px; }
.log-msg { color: #ccc; word-break: break-all; }

/* Buttons */
.btn { padding: 8px 16px; border: 1px solid #333; border-radius: 6px; background: #1a1a1a; color: #ddd; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
.btn:hover { background: #2a2a2a; border-color: #555; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1565c0; border-color: #1565c0; color: #fff; }
.btn-primary:hover { background: #1976d2; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }
.btn-danger { border-color: #c62828; color: #ef5350; }
.btn-danger:hover { background: #b71c1c; color: #fff; }

select { background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 8px 12px; color: #e0e0e0; font-size: 0.85rem; outline: none; }

.empty { text-align: center; padding: 40px; color: #666; font-size: 0.95rem; }

/* Toast */
.toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 8px; font-size: 0.9rem; animation: fadeIn 0.3s; z-index: 100; }
.toast.success { background: #1b5e20; color: #a5d6a7; }
.toast.error { background: #b71c1c; color: #ef9a9a; }
.toast.info { background: #0d47a1; color: #90caf9; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 20px; width: 90%; max-width: 480px; max-height: 80vh; overflow-y: auto; }
.modal-wide { max-width: 720px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal-header h3 { font-size: 1.1rem; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.readme-content { font-size: 0.9rem; line-height: 1.6; color: #ccc; max-height: 60vh; overflow-y: auto; }
.readme-content h1, .readme-content h2, .readme-content h3 { color: #fff; margin: 16px 0 8px; }
.readme-content code { background: #2a2a2a; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
.readme-content pre { background: #2a2a2a; padding: 12px; border-radius: 6px; overflow-x: auto; }
.readme-content table { border-collapse: collapse; width: 100%; margin: 8px 0; }
.readme-content th, .readme-content td { border: 1px solid #333; padding: 6px 10px; text-align: left; }
.readme-content th { background: #2a2a2a; }
.readme-content ul, .readme-content ol { padding-left: 20px; }
.readme-content li { margin: 4px 0; }

/* Switch with label */
.switch-group { display: flex; align-items: center; gap: 6px; }
.switch-label { font-size: 0.75rem; color: #888; white-space: nowrap; }

/* Icon button */
.btn-icon { padding: 4px 8px; font-size: 0.9rem; }
</style>
