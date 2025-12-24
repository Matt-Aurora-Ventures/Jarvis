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
    backgroundColor: '#0f172a',
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
  // For now, use a simple text icon. In production, use an actual icon file
  tray = new Tray(path.join(__dirname, '../public/jarvis-tray.png'))
  
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
}

function startJarvisBackend() {
  const lifeosBin = path.join(__dirname, '../../bin/lifeos')
  const pythonPath = path.join(__dirname, '../../venv/bin/python')
  
  // Start the API server
  jarvisProcess = spawn(pythonPath, ['-m', 'core.api_server'], {
    cwd: path.join(__dirname, '../..'),
    env: { ...process.env, PYTHONPATH: path.join(__dirname, '../..') },
  })

  jarvisProcess.stdout.on('data', (data) => {
    console.log(`Jarvis: ${data}`)
  })

  jarvisProcess.stderr.on('data', (data) => {
    console.error(`Jarvis Error: ${data}`)
  })

  jarvisProcess.on('close', (code) => {
    console.log(`Jarvis process exited with code ${code}`)
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
