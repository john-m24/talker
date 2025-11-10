/* global window, fetch */
(function () {
	// Read API base from preload (context-bridged); fallback to default port
	const API_BASE = (window.cfg && window.cfg.apiBase) || 'http://127.0.0.1:8770'

	const q = document.getElementById('q')
	const list = document.getElementById('list')
	const results = document.getElementById('results')
	const submitBtn = document.getElementById('submitBtn')
	const closeBtn = document.getElementById('closeBtn')
	let suggestions = []
	let activeIndex = -1
	let debounceTimer = null
	let resultsPollInterval = null
	let resultsPollAttempts = 0
	const MAX_RESULT_POLL_ATTEMPTS = 15 // 3 seconds (15 * 200ms)

	function render() {
		if (!suggestions || suggestions.length === 0) {
			list.innerHTML = '<div class="placeholder">Start typing to see suggestions</div>'
			list.hidden = false
			return
		}
		list.hidden = false
		list.innerHTML = suggestions
			.map((s, i) => {
				const label = (s && typeof s === 'object') ? (s.display || s.text || '') : String(s)
				return `<div class="item ${i === activeIndex ? 'active' : ''}" data-idx="${i}">${escapeHtml(label)}</div>`
			})
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

	function displayResults(data) {
		if (!data) {
			results.classList.remove('show')
			results.innerHTML = ''
			return
		}

		if (data.error) {
			results.innerHTML = `<div class="results-error">${escapeHtml(data.error)}</div>`
			results.classList.add('show')
			return
		}

		if (data.title && data.items) {
			let html = `<div class="results-title">${escapeHtml(data.title)}</div>`
			data.items.forEach(item => {
				html += `<div class="results-item">${escapeHtml(item)}</div>`
			})
			results.innerHTML = html
			results.classList.add('show')
		}
	}

	function stopResultsPolling() {
		if (resultsPollInterval) {
			clearInterval(resultsPollInterval)
			resultsPollInterval = null
		}
		resultsPollAttempts = 0
	}

	function startResultsPolling() {
		stopResultsPolling()
		resultsPollAttempts = 0

		resultsPollInterval = setInterval(async () => {
			resultsPollAttempts++

			if (resultsPollAttempts >= MAX_RESULT_POLL_ATTEMPTS) {
				stopResultsPolling()
				// No results after timeout - auto-close
				if (window.palette && window.palette.hide) {
					window.palette.hide()
				}
				return
			}

			try {
				const res = await fetch(`${API_BASE}/get-results`)
				if (!res.ok) return
				const data = await res.json()
				if (data.results) {
					// Check if it's an empty result (signals "done, close")
					if (data.results.title === "" && (!data.results.items || data.results.items.length === 0)) {
						// Empty result - command done, close immediately
						stopResultsPolling()
						if (window.palette && window.palette.hide) {
							window.palette.hide()
						}
						return
					}
					// Results received - display and keep open
					displayResults(data.results)
					stopResultsPolling()
					// Keep client open, focus input for follow-up
					setTimeout(() => q.focus(), 0)
				}
			} catch (e) {
				// Ignore errors
			}
		}, 200) // Poll every 200ms
	}

	async function submitCommand(text) {
		const payload = { command: String(text || '').trim() }
		if (!payload.command) return
		
		// Clear previous results
		displayResults(null)
		
		try {
			const res = await fetch(`${API_BASE}/submit`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			})
			if (!res.ok) {
				console.error('submit failed', res.status)
				displayResults({ error: 'Failed to submit command' })
				return
			}
			// Start polling for results
			startResultsPolling()
		} catch (e) {
			console.error('submit error', e)
			displayResults({ error: 'Error submitting command' })
		}
	}

	function chooseActive() {
		let text = q.value.trim()
		if (activeIndex >= 0 && activeIndex < suggestions.length) {
			const sel = suggestions[activeIndex]
			text = (sel && typeof sel === 'object') ? String(sel.text || '') : String(sel || '')
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
			displayResults(null) // Clear results
			stopResultsPolling()
			render()
			setTimeout(() => q.focus(), 0)
		})
	}

	// Initial render
	render()
})()


