const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  onVoiceStart: (callback) => ipcRenderer.on('voice-start', callback),
  onVoiceStop: (callback) => ipcRenderer.on('voice-stop', callback),
  onNavigate: (callback) => ipcRenderer.on('navigate', (event, path) => callback(path)),
})
