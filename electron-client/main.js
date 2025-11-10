const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron')
const path = require('path')

let win

function createWindow() {
	win = new BrowserWindow({
		width: 700,
		height: 200,
		frame: false,
		show: false,
		resizable: false,
		movable: true,
		alwaysOnTop: true,
		skipTaskbar: true,
		focusable: true,
		webPreferences: {
			preload: path.join(__dirname, 'preload.js')
		}
	})

	win.loadFile(path.join(__dirname, 'renderer', 'index.html'))
}

function showPalette() {
	if (!win) return
	try {
		if (win.setVisibleOnAllWorkspaces) {
			win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
		}
		if (win.setAlwaysOnTop) {
			win.setAlwaysOnTop(true, 'screen-saver')
		}
		win.setFocusable(true)
		win.show()
		win.focus()
		if (win.moveTop) {
			win.moveTop()
		}
		win.webContents.send('palette:show')
	} catch (e) {
		// no-op
	}
}

app.whenReady().then(() => {
	createWindow()

	const hotkey = process.env.VOICE_AGENT_ELECTRON_HOTKEY || 'Control+Alt+Space'
	globalShortcut.register(hotkey, () => {
		showPalette()
	})

	app.on('activate', function () {
		if (BrowserWindow.getAllWindows().length === 0) createWindow()
	})
})

app.on('will-quit', () => {
	globalShortcut.unregisterAll()
})

ipcMain.on('palette:hide', () => {
	if (win) {
		win.hide()
	}
})


