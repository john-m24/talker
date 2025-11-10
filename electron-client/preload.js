const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('palette', {
	onShow: (cb) => ipcRenderer.on('palette:show', cb),
	hide: () => ipcRenderer.send('palette:hide')
})

// Expose configuration (e.g., API base) to the renderer safely
contextBridge.exposeInMainWorld('cfg', {
	apiBase: `http://127.0.0.1:${process.env.VOICE_AGENT_API_PORT || '8770'}`
})


