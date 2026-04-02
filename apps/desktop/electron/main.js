const { app, BrowserWindow, Tray, Menu, ipcMain, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow
let tray
let jarvisProcess

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#FFFFFF',  // Match V2 White Knight theme
    show: false,
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

function createTray() {
  const fs = require('fs')
  const trayIconPath = path.join(__dirname, '../public/jarvis-tray.png')
  
  // Check if tray icon exists, skip tray creation if not
  if (!fs.existsSync(trayIconPath)) {
    console.log('Tray icon not found, skipping tray creation')
    return
  }
  
  try {
    tray = new Tray(trayIconPath)
    
    const contextMenu = Menu.buildFromTemplate([
      { label: 'Open Jarvis', click: () => mainWindow.show() },
      { type: 'separator' },
      { label: 'Start Listening', click: () => startListening() },
      { label: 'Stop Listening', click: () => stopListening() },
      { type: 'separator' },
      { label: 'Settings', click: () => { mainWindow.show(); mainWindow.webContents.send('navigate', '/settings') } },
      { type: 'separator' },
      { label: 'Quit Jarvis', click: () => { app.isQuitting = true; app.quit() } },
    ])

    tray.setToolTip('Jarvis AI Assistant')
    tray.setContextMenu(contextMenu)

    tray.on('click', () => {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()
    })
  } catch (err) {
    console.error('Failed to create tray:', err)
  }
}

function getPythonPath() {
  // Cross-platform Python path detection
  const isWin = process.platform === 'win32'
  const isMac = process.platform === 'darwin'

  // Try common venv locations
  const venvPaths = isWin
    ? [
        path.join(__dirname, '../../venv/Scripts/python.exe'),
        path.join(__dirname, '../../.venv/Scripts/python.exe'),
        path.join(__dirname, '../../venv311/Scripts/python.exe'),
        'python',  // Fallback to system Python
      ]
    : [
        path.join(__dirname, '../../venv/bin/python'),
        path.join(__dirname, '../../.venv/bin/python'),
        path.join(__dirname, '../../venv311/bin/python'),
        '/usr/bin/python3',
        'python3',  // Fallback to system Python
      ]

  const fs = require('fs')
  for (const p of venvPaths) {
    if (p.startsWith('/') || p.includes(':')) {
      // Absolute path - check if exists
      if (fs.existsSync(p)) {
        return p
      }
    } else {
      // Relative/system path - return as-is
      return p
    }
  }

  return isWin ? 'python' : 'python3'
}

function startJarvisBackend() {
  const pythonPath = getPythonPath()
  const projectRoot = path.join(__dirname, '../..')

  console.log(`Starting Jarvis backend with Python: ${pythonPath}`)

  // Start the API server
  jarvisProcess = spawn(pythonPath, ['-m', 'core.api_server'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: projectRoot,
      PYTHONUNBUFFERED: '1',
    },
    shell: process.platform === 'win32',  // Use shell on Windows for better path handling
  })

  jarvisProcess.stdout.on('data', (data) => {
    console.log(`Jarvis: ${data}`)
    // Send to renderer for status updates
    if (mainWindow) {
      mainWindow.webContents.send('jarvis-log', data.toString())
    }
  })

  jarvisProcess.stderr.on('data', (data) => {
    console.error(`Jarvis Error: ${data}`)
    if (mainWindow) {
      mainWindow.webContents.send('jarvis-error', data.toString())
    }
  })

  jarvisProcess.on('error', (err) => {
    console.error('Failed to start Jarvis backend:', err)
    if (mainWindow) {
      mainWindow.webContents.send('jarvis-error', `Failed to start: ${err.message}`)
    }
  })

  jarvisProcess.on('close', (code) => {
    console.log(`Jarvis process exited with code ${code}`)
    if (mainWindow) {
      mainWindow.webContents.send('jarvis-exit', code)
    }
  })
}

function startListening() {
  if (mainWindow) {
    mainWindow.webContents.send('voice-start')
  }
}

function stopListening() {
  if (mainWindow) {
    mainWindow.webContents.send('voice-stop')
  }
}

app.whenReady().then(() => {
  createWindow()
  createTray()
  
  // Start Jarvis backend if not in dev mode
  if (!isDev) {
    startJarvisBackend()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    } else {
      mainWindow.show()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  app.isQuitting = true
  if (jarvisProcess) {
    jarvisProcess.kill()
  }
})

// IPC handlers
ipcMain.handle('get-app-path', () => app.getPath('userData'))
ipcMain.handle('open-external', (event, url) => shell.openExternal(url))
ipcMain.handle('get-version', () => app.getVersion())

// Backend control
ipcMain.handle('start-backend', () => {
  if (!jarvisProcess) {
    startJarvisBackend()
    return { success: true, message: 'Backend started' }
  }
  return { success: false, message: 'Backend already running' }
})

ipcMain.handle('stop-backend', () => {
  if (jarvisProcess) {
    jarvisProcess.kill()
    jarvisProcess = null
    return { success: true, message: 'Backend stopped' }
  }
  return { success: false, message: 'Backend not running' }
})

ipcMain.handle('restart-backend', async () => {
  if (jarvisProcess) {
    jarvisProcess.kill()
    jarvisProcess = null
  }
  await new Promise(resolve => setTimeout(resolve, 1000))
  startJarvisBackend()
  return { success: true, message: 'Backend restarted' }
})

ipcMain.handle('get-backend-status', () => {
  return {
    running: jarvisProcess !== null,
    pid: jarvisProcess?.pid || null,
  }
})

// Window control
ipcMain.handle('minimize', () => {
  if (mainWindow) mainWindow.minimize()
})

ipcMain.handle('maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow.maximize()
    }
  }
})

ipcMain.handle('close', () => {
  if (mainWindow) mainWindow.hide()
})

// Notifications
ipcMain.handle('show-notification', (event, { title, body }) => {
  const { Notification } = require('electron')
  if (Notification.isSupported()) {
    new Notification({ title, body }).show()
  }
})

// Settings persistence using electron-store pattern
const Store = require('electron-store') || { prototype: {} }
let store
try {
  store = new Store()
} catch {
  // Fallback if electron-store not installed
  store = {
    get: (key, defaultValue) => defaultValue,
    set: (key, value) => {},
  }
}

ipcMain.handle('get-setting', (event, key) => {
  return store.get(key)
})

ipcMain.handle('set-setting', (event, key, value) => {
  store.set(key, value)
  return true
})

// Telegram integration
ipcMain.handle('send-telegram', async (event, message) => {
  try {
    const https = require('https')
    const botToken = process.env.TELEGRAM_BOT_TOKEN
    const chatId = process.env.TELEGRAM_BUY_BOT_CHAT_ID

    if (!botToken || !chatId) {
      return { success: false, error: 'Telegram not configured' }
    }

    const url = `https://api.telegram.org/bot${botToken}/sendMessage`
    const data = JSON.stringify({
      chat_id: chatId,
      text: message,
      parse_mode: 'HTML',
    })

    return new Promise((resolve) => {
      const req = https.request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } }, (res) => {
        let body = ''
        res.on('data', chunk => body += chunk)
        res.on('end', () => {
          try {
            const result = JSON.parse(body)
            resolve({ success: result.ok, result })
          } catch {
            resolve({ success: false, error: 'Parse error' })
          }
        })
      })
      req.on('error', (err) => resolve({ success: false, error: err.message }))
      req.write(data)
      req.end()
    })
  } catch (err) {
    return { success: false, error: err.message }
  }
})
