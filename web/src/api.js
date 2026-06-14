import axios from 'axios'

const http = axios.create({ baseURL: '' })

export default {
    // health
    health: () => http.get('/health'),

    // server
    serverStatus: () => http.get('/server/status'),
    serverReload: () => http.post('/server/reload'),

    // plugins
    listPlugins: () => http.get('/plugins'),
    getPlugin: (name) => http.get(`/plugins/${name}`),
    enablePlugin: (name) => http.put(`/plugins/${name}/enable`),
    disablePlugin: (name) => http.put(`/plugins/${name}/disable`),
    getPluginConfig: (name) => http.get(`/plugins/${name}/config`),
    updatePluginConfig: (name, config) => http.put(`/plugins/${name}/config`, { config }),
    togglePluginMcp: (name, enabled) => http.put(`/plugins/${name}/mcp`, { enabled }),

    // logs
    getLogs: (params) => http.get('/logs', { params }),
    clearLogs: (plugin) => http.delete('/logs', { params: { plugin } }),
    getLogConfig: () => http.get('/logs/config'),
    updateLogConfig: (data) => http.put('/logs/config', data),
    pruneLogs: () => http.post('/logs/prune'),
}
