document.addEventListener('DOMContentLoaded', async () => {
  const saveBtn = document.getElementById('saveBtn');
  const statusEl = document.getElementById('status');
  const titleEl = document.getElementById('pageTitle');

  // Get the active tab in the current window.
  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (e) {
    statusEl.textContent = 'Unable to read active tab.';
    statusEl.classList.add('error');
    saveBtn.disabled = true;
    return;
  }

  if (!tab || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('file://')) {
    titleEl.textContent = tab?.url || '—';
    statusEl.textContent = 'This page cannot be saved.';
    statusEl.classList.add('error');
    saveBtn.disabled = true;
    return;
  }

  titleEl.textContent = tab.title || tab.url;

  // Check whether this URL has already been saved.
  try {
    const check = await chrome.runtime.sendMessage({ action: 'check', url: tab.url });
    if (check.exists) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saved';
      statusEl.textContent = `Already saved as [[${check.slug}]]`;
      return;
    }
  } catch (err) {
    console.error('Check failed:', err);
  }

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    statusEl.textContent = 'Extracting & saving…';
    statusEl.classList.remove('error');

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'saveTab',
        tabId: tab.id,
        title: tab.title,
        url: tab.url,
      });

      if (result && result.status === 'ok') {
        saveBtn.textContent = 'Saved';
        statusEl.textContent = `Saved as [[${result.slug}]]`;
      } else if (result && result.error) {
        throw new Error(result.error);
      } else {
        throw new Error('Unknown response from server');
      }
    } catch (err) {
      saveBtn.disabled = false;
      statusEl.textContent = `Error: ${err.message}`;
      statusEl.classList.add('error');
    }
  });
});
