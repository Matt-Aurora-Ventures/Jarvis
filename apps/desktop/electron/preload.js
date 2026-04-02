const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  getPlatform: () => process.platform,
  getVersion: () => ipcRenderer.invoke('get-version'),

  // External links
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Voice control
  onVoiceStart: (callback) => ipcRenderer.on('voice-start', callback),
  onVoiceStop: (callback) => ipcRenderer.on('voice-stop', callback),

  // Navigation
  onNavigate: (callback) => ipcRenderer.on('navigate', (event, path) => callback(path)),

  // Jarvis backend events
  onJarvisLog: (callback) => ipcRenderer.on('jarvis-log', (event, data) => callback(data)),
  onJarvisError: (callback) => ipcRenderer.on('jarvis-error', (event, data) => callback(data)),
  onJarvisExit: (callback) => ipcRenderer.on('jarvis-exit', (event, code) => callback(code)),

  // Backend control
  startBackend: () => ipcRenderer.invoke('start-backend'),
  stopBackend: () => ipcRenderer.invoke('stop-backend'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),

  // Telegram integration
  sendTelegramMessage: (message) => ipcRenderer.invoke('send-telegram', message),

  // Settings
  getSetting: (key) => ipcRenderer.invoke('get-setting', key),
  setSetting: (key, value) => ipcRenderer.invoke('set-setting', key, value),

  // Window control
  minimize: () => ipcRenderer.invoke('minimize'),
  maximize: () => ipcRenderer.invoke('maximize'),
  close: () => ipcRenderer.invoke('close'),

  // System tray
  showNotification: (title, body) => ipcRenderer.invoke('show-notification', { title, body }),

  // Auto-update
  checkForUpdates: () => ipcRenderer.invoke('check-updates'),
  onUpdateAvailable: (callback) => ipcRenderer.on('update-available', (event, info) => callback(info)),
  onUpdateDownloaded: (callback) => ipcRenderer.on('update-downloaded', (event, info) => callback(info)),
  installUpdate: () => ipcRenderer.invoke('install-update'),

  // Cleanup listeners
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
})
