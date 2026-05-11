const SERVER_URL = 'http://localhost:8765';

/**
 * Check whether a page (identified by its URL) has already been saved.
 */
async function checkSaved(url) {
  const source = `chrome:${url}`;
  try {
    const resp = await fetch(
      `${SERVER_URL}/check?source=${encodeURIComponent(source)}`
    );
    if (!resp.ok) return { exists: false };
    return await resp.json();
  } catch (err) {
    console.error('GMind check failed:', err);
    return { exists: false, offline: true };
  }
}

/**
 * Extract article from the given tab and POST it to the GMind server.
 */
async function savePage({ tabId, title, url }) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { action: 'extract' }, async (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response || !response.success) {
        reject(new Error(response?.error || 'Extraction failed'));
        return;
      }
      const data = response.data;
      if (!data) {
        reject(new Error('No readable content found on this page'));
        return;
      }

      const source = `chrome:${url}`;
      const payload = {
        title: data.title || title || 'Untitled',
        content: data.markdown,
        type: 'source',
        source: source,
      };

      try {
        const resp = await fetch(`${SERVER_URL}/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (!resp.ok || result.status === 'error') {
          reject(new Error(result.message || `HTTP ${resp.status}`));
        } else {
          resolve(result);
        }
      } catch (err) {
        reject(err);
      }
    });
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'check') {
    checkSaved(request.url)
      .then(sendResponse)
      .catch(() => sendResponse({ exists: false }));
    return true; // keep channel open for async
  }

  if (request.action === 'saveTab') {
    savePage({
      tabId: request.tabId,
      title: request.title,
      url: request.url,
    })
      .then(sendResponse)
      .catch((err) => {
        sendResponse({ status: 'error', error: err.message });
      });
    return true;
  }
});
