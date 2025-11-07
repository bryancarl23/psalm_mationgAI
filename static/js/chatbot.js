 (function () {
 	const toggleBtn = document.getElementById('streambot-toggle');
 	const windowEl = document.getElementById('streambot-window');
 	const closeBtn = document.getElementById('streambot-close');
 	const form = document.getElementById('streambot-form');
 	const input = document.getElementById('streambot-input');
 	const messages = document.getElementById('streambot-messages');

 	if (!toggleBtn) return;

 	function scrollToBottom() {
 		messages.scrollTop = messages.scrollHeight;
 	}

	function escapeHtml(str) {
		return str
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	}

	function renderMessage(text) {
		return escapeHtml(text).replace(/\n/g, "<br>");
	}

 	function addMessage(text, role) {
 		const wrap = document.createElement('div');
 		wrap.className = 'mb-3';

 		const badge = document.createElement('div');
		badge.className = 'badge app-badge';
 		badge.textContent = role === 'user' ? 'You' : 'StreamBot';

 		const bubble = document.createElement('div');
		bubble.className = 'mt-2 p-3 border rounded-3 ' + (role === 'user' ? 'msg-user' : 'msg-bot');
		bubble.innerHTML = renderMessage(text);

 		wrap.appendChild(badge);
 		wrap.appendChild(bubble);
 		messages.appendChild(wrap);
 		scrollToBottom();
 	}

 	toggleBtn.addEventListener('click', () => {
 		windowEl.classList.toggle('d-none');
 		if (!windowEl.classList.contains('d-none')) {
 			input.focus();
 		}
 	});

 	closeBtn.addEventListener('click', () => windowEl.classList.add('d-none'));

 	form.addEventListener('submit', async (e) => {
 		e.preventDefault();
 		const text = input.value.trim();
 		if (!text) return;
 		addMessage(text, 'user');
 		input.value = '';

		try {
			const res = await fetch('/chatbot/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': window.CSRF_TOKEN || ''
				},
				body: JSON.stringify({ message: text })
			});

			if (!res.ok) {
				let msg = 'Sorry, something went wrong. Please try again.';
				try { msg = await res.text(); } catch (_) {}
				addMessage(msg, 'bot');
				return;
			}

			let data;
			try { data = await res.json(); }
			catch (_) { data = { reply: 'Sorry, I could not parse the server response.' }; }

			addMessage(data.reply || 'Sorry, no response.', 'bot');
		} catch (err) {
			addMessage('Sorry, something went wrong. Please try again.', 'bot');
		}
 	});
 })();



