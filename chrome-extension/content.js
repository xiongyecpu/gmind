/**
 * Content script — runs in an isolated world on every matched page.
 * Exposes article extraction via Readability + Turndown.
 */

function extractArticle() {
  // Clone the document so Readability doesn't mutate the live DOM.
  const documentClone = document.cloneNode(true);
  const reader = new Readability(documentClone);
  const article = reader.parse();

  if (!article) {
    return null;
  }

  const turndownService = new TurndownService({
    headingStyle: 'atx',
    bulletListMarker: '-',
    codeBlockStyle: 'fenced',
  });

  const markdown = turndownService.turndown(article.content);

  return {
    title: article.title,
    markdown: markdown,
    url: location.href,
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract') {
    // Defer to next tick so the message port stays open for async response.
    setTimeout(() => {
      try {
        const result = extractArticle();
        sendResponse({ success: true, data: result });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    }, 0);
    return true; // keep channel open
  }
});
