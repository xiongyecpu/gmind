document.addEventListener('DOMContentLoaded', async () => {
  const previewEl = document.getElementById('preview');
  const saveBtn = document.getElementById('saveBtn');
  const statusEl = document.getElementById('status');
  const titleEl = document.getElementById('pageTitle');

  let extractedData = null;

  // Get the active tab.
  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (e) {
    titleEl.textContent = 'Unable to read active tab';
    previewEl.textContent = '';
    saveBtn.disabled = true;
    return;
  }

  if (!tab || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('file://')) {
    titleEl.textContent = tab?.url || '—';
    previewEl.textContent = 'This page cannot be saved.';
    previewEl.classList.add('error');
    saveBtn.disabled = true;
    return;
  }

  titleEl.textContent = tab.title || tab.url;

  // 1. Auto-extract article content via content script.
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
    if (!response || !response.success) {
      throw new Error(response?.error || 'Extraction failed');
    }
    extractedData = response.data;
    if (!extractedData) {
      throw new Error('No readable content found on this page');
    }
    previewEl.textContent = extractedData.markdown || '(empty)';
  } catch (err) {
    previewEl.textContent = `Error: ${err.message}`;
    previewEl.classList.add('error');
    saveBtn.disabled = true;
    return;
  }

  // 2. Check whether already saved.
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

  // 3. Save button handler.
  saveBtn.addEventListener('click', async () => {
    if (!extractedData) return;
    saveBtn.disabled = true;
    statusEl.textContent = 'Saving…';
    statusEl.classList.remove('error');

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'saveData',
        title: extractedData.title || tab.title,
        content: extractedData.markdown,
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
