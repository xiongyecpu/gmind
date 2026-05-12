/**
 * Content script — runs in an isolated world on every matched page.
 * Uses Defuddle for content extraction + Turndown for Markdown conversion.
 */

function extractArticle() {
  // Defuddle clones internally, so we can pass the live document.
  const defuddle = new Defuddle(document, {
    removeHiddenElements: true,
    removeLowScoring: true,
    standardize: true,
  });

  const result = defuddle.parse();

  if (!result || !result.content) {
    return null;
  }

  // Convert Defuddle's standardized HTML to Markdown with Turndown.
  const turndownService = new TurndownService({
    headingStyle: 'atx',
    bulletListMarker: '-',
    codeBlockStyle: 'fenced',
  });

  const markdown = turndownService.turndown(result.content);

  return {
    title: result.title,
    markdown: markdown,
    url: location.href,
    // enriched metadata from Defuddle
    author: result.author,
    description: result.description,
    published: result.published,
    site: result.site,
    domain: result.domain,
    language: result.language,
    wordCount: result.wordCount,
    image: result.image,
    favicon: result.favicon,
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract') {
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
