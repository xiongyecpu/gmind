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
 * Inject content scripts into a tab when they aren't already present.
 */
async function ensureContentScripts(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['lib/defuddle.js', 'lib/turndown.js', 'content.js'],
    });
  } catch (err) {
    console.error('Failed to inject content scripts:', err);
    throw err;
  }
}

/**
 * Extract article from the given tab and POST it to the GMind server.
 */
async function savePage({ tabId, title, url }) {
  const extract = () => new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { action: 'extract' }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response || !response.success) {
        reject(new Error(response?.error || 'Extraction failed'));
        return;
      }
      resolve(response.data);
    });
  });

  let data;
  try {
    data = await extract();
  } catch (err) {
    // Content scripts not injected (e.g. after extension reload). Inject and retry.
    if (err.message.includes('Receiving end does not exist')) {
      await ensureContentScripts(tabId);
      await new Promise(r => setTimeout(r, 100));
      data = await extract();
    } else {
      throw err;
    }
  }

  if (!data) {
    throw new Error('No readable content found on this page');
  }

  const source = `chrome:${url}`;

  // Build richer metadata from Defuddle output
  const metadata = {
    author: data.author,
    description: data.description,
    published: data.published,
    site: data.site,
    domain: data.domain,
    language: data.language,
    wordCount: data.wordCount,
    image: data.image,
    favicon: data.favicon,
  };

  // Strip undefined values
  Object.keys(metadata).forEach(key => {
    if (metadata[key] === undefined) delete metadata[key];
  });

  const payload = {
    title: data.title || title || 'Untitled',
    content: data.markdown,
    type: 'source',
    source: source,
    url: url,
    metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
  };

  const resp = await fetch(`${SERVER_URL}/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  if (!resp.ok || result.status === 'error') {
    throw new Error(result.message || `HTTP ${resp.status}`);
  }
  return result;
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
