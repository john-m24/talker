const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const http = require('http')

let win
const API_PORT = process.env.VOICE_AGENT_API_PORT || 8770
const API_BASE = `http://127.0.0.1:${API_PORT}`

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

	// Poll for show-palette signal from Python backend
	setInterval(() => {
		const req = http.get(`${API_BASE}/show-palette`, (res) => {
			let data = ''
			res.on('data', (chunk) => {
				data += chunk
			})
			res.on('end', () => {
				try {
					const json = JSON.parse(data)
					if (json.show === true) {
						showPalette()
					}
				} catch (e) {
					// Ignore parse errors
				}
			})
		})
		req.on('error', () => {
			// Ignore connection errors (backend may not be running)
		})
		req.setTimeout(1000)
		req.on('timeout', () => {
			req.destroy()
		})
	}, 100) // Poll every 100ms

	app.on('activate', function () {
		if (BrowserWindow.getAllWindows().length === 0) createWindow()
	})
})

app.on('will-quit', () => {
	// Cleanup if needed
})

ipcMain.on('palette:hide', () => {
	if (win) {
		win.hide()
	}
})


