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
		minWidth: 500,
		minHeight: 150,
		maxHeight: 800,
		frame: false,
		show: false,
		resizable: true,
		movable: true,
		alwaysOnTop: true,
		skipTaskbar: true,
		focusable: true,
		webPreferences: {
			preload: path.join(__dirname, 'preload.js')
		}
	})

	win.loadFile(path.join(__dirname, 'renderer', 'index.html'))
	
	// Auto-resize window based on content
	win.webContents.on('did-finish-load', () => {
		resizeWindow()
	})
}

function resizeWindow() {
	if (!win) return
	win.webContents.executeJavaScript(`
		(function() {
			const container = document.querySelector('.container')
			if (!container) return { width: 700, height: 200 }
			const rect = container.getBoundingClientRect()
			const padding = 24 // 12px top + 12px bottom
			const height = Math.min(rect.height + padding, 800)
			return { width: 700, height: Math.max(height, 150) }
		})()
	`).then((size) => {
		if (size && size.width && size.height) {
			win.setSize(size.width, size.height, false)
		}
	}).catch(() => {
		// Ignore errors
	})
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

ipcMain.on('palette:resize', () => {
	if (win) {
		resizeWindow()
	}
})


