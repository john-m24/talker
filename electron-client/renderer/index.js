/* global window, fetch */
(function () {
	// Read API base from preload (context-bridged); fallback to default port
	const API_BASE = (window.cfg && window.cfg.apiBase) || 'http://127.0.0.1:8770'

	const q = document.getElementById('q')
	const list = document.getElementById('list')
	const submitBtn = document.getElementById('submitBtn')
	const closeBtn = document.getElementById('closeBtn')
	let suggestions = []
	let activeIndex = -1
	let debounceTimer = null

	function render() {
		if (!suggestions || suggestions.length === 0) {
			list.innerHTML = '<div class="placeholder">Start typing to see suggestions</div>'
			list.hidden = false
			return
		}
		list.hidden = false
		list.innerHTML = suggestions
			.map((s, i) => `<div class="item ${i === activeIndex ? 'active' : ''}" data-idx="${i}">${escapeHtml(s)}</div>`)
			.join('')
	}

	function escapeHtml(str) {
		return String(str).replace(/[&<>"']/g, function (m) {
			return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]
		})
	}

	async function fetchSuggestions(text) {
		try {
			const res = await fetch(`${API_BASE}/suggest?text=${encodeURIComponent(text)}`)
			if (!res.ok) return
			const data = await res.json()
			suggestions = Array.isArray(data.suggestions) ? data.suggestions : []
			if (activeIndex >= suggestions.length) activeIndex = suggestions.length - 1
			render()
		} catch (e) {
			console.error('suggest error', e)
		}
	}

	async function submitCommand(text) {
		const payload = { command: String(text || '').trim() }
		if (!payload.command) return
		try {
			const res = await fetch(`${API_BASE}/submit`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			})
			if (!res.ok) {
				console.error('submit failed', res.status)
			}
			// hide window
			if (window.palette && window.palette.hide) {
				window.palette.hide()
			}
		} catch (e) {
			console.error('submit error', e)
		}
	}

	function chooseActive() {
		let text = q.value.trim()
		if (activeIndex >= 0 && activeIndex < suggestions.length) {
			text = suggestions[activeIndex]
		}
		submitCommand(text)
	}

	q.addEventListener('input', () => {
		activeIndex = -1
		const text = q.value
		clearTimeout(debounceTimer)
		debounceTimer = setTimeout(() => fetchSuggestions(text), 150)
	})

	q.addEventListener('keydown', (e) => {
		if (e.key === 'ArrowDown') {
			e.preventDefault()
			if (!suggestions.length) return
			activeIndex = (activeIndex + 1) % suggestions.length
			render()
		} else if (e.key === 'ArrowUp') {
			e.preventDefault()
			if (!suggestions.length) return
			activeIndex = (activeIndex - 1 + suggestions.length) % suggestions.length
			render()
		} else if (e.key === 'Enter') {
			e.preventDefault()
			chooseActive()
		} else if (e.key === 'Escape') {
			if (window.palette && window.palette.hide) {
				window.palette.hide()
			}
		}
	})

	list.addEventListener('click', (e) => {
		const item = e.target.closest('.item')
		if (!item) return
		const idx = parseInt(item.getAttribute('data-idx'), 10)
		if (!isNaN(idx) && idx >= 0 && idx < suggestions.length) {
			activeIndex = idx
			chooseActive()
		}
	})

	// Buttons
	if (submitBtn) {
		submitBtn.addEventListener('click', () => chooseActive())
	}
	if (closeBtn) {
		closeBtn.addEventListener('click', () => {
			if (window.palette && window.palette.hide) {
				window.palette.hide()
			}
		})
	}

	// Focus and clear on show
	if (window.palette && window.palette.onShow) {
		window.palette.onShow(() => {
			q.value = ''
			suggestions = []
			activeIndex = -1
			render()
			setTimeout(() => q.focus(), 0)
		})
	}

	// Initial render
	render()
})()


