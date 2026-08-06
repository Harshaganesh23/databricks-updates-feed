<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="utf-8" doctype-system="about:legacy-compat"/>
<xsl:template match="/">
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Databricks Updates — RSS Feed</title>
<style>
:root {
  --bg: #12181b;
  --surface: #1b2a30;
  --border: #2d454d;
  --text: #f3f1ea;
  --text-dim: #b7c4c7;
  --text-faint: #7c9096;
  --accent: #ff5f46;
  --accent-soft: #3a1f1c;
  --radius: 14px;
  --mono: "SF Mono", Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f9f7f4;
    --surface: #ffffff;
    --border: #e2dfd7;
    --text: #1b3139;
    --text-dim: #5a6b72;
    --text-faint: #8c9aa0;
    --accent: #ff3621;
    --accent-soft: #faecec;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  padding: 40px 20px;
  -webkit-font-smoothing: antialiased;
}
.container { max-width: 720px; margin: 0 auto; }
.header {
  text-align: center;
  margin-bottom: 36px;
  padding: 32px 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.header h1 {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 8px;
}
.header p {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 18px;
}
.feed-url-box {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 14px;
}
.feed-url {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  color: var(--text-dim);
  word-break: break-all;
  max-width: 100%;
}
.cta {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  padding: 10px 18px;
  border-radius: 8px;
  text-decoration: none;
  border: none;
  cursor: pointer;
  transition: opacity .15s;
}
.cta:hover { opacity: 0.9; }
.cta.copied { background: #3e7a5e; }
.instructions {
  font-size: 13px;
  color: var(--text-faint);
  margin-top: 12px;
  line-height: 1.6;
}
.items { display: flex; flex-direction: column; gap: 2px; }
.item {
  padding: 16px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
}
.item-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 6px;
}
.item-title a {
  color: var(--text);
  text-decoration: none;
}
.item-title a:hover { color: var(--accent); }
.item-date {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-faint);
  margin-bottom: 6px;
}
.item-desc {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
  margin-bottom: 20px;
}
.back-link:hover { text-decoration: underline; }
@media (max-width: 600px) {
  body { padding: 20px 12px; }
  .header { padding: 24px 16px; }
  .header h1 { font-size: 20px; }
  .feed-url { font-size: 11px; padding: 8px 10px; }
}
</style>
</head>
<body>
<div class="container">
  <a class="back-link" href="./">&#8592; Back to Dashboard</a>
  <div class="header">
    <h1>&#x1F4E1; Databricks Updates RSS Feed</h1>
    <p>This is an RSS feed. Subscribe with your favorite reader to get automatic updates when new Databricks posts, release notes, or GitHub releases are published.</p>
    <div class="feed-url-box">
      <span class="feed-url" id="feedUrl"></span>
      <button class="cta" id="copyBtn" onclick="copyFeedUrl()">Copy URL</button>
    </div>
    <p class="instructions" style="margin-top:14px">
      Paste this URL into any RSS reader: Feedly, Inoreader, Thunderbird, Outlook, Slack, Notion, NetNewsWire
    </p>
  </div>
  <div class="items">
    <xsl:for-each select="/rss/channel/item">
      <div class="item">
        <div class="item-date"><xsl:value-of select="pubDate"/></div>
        <div class="item-title"><a href="{link}" target="_blank" rel="noopener"><xsl:value-of select="title"/></a></div>
        <xsl:if test="description">
          <div class="item-desc"><xsl:value-of select="description"/></div>
        </xsl:if>
      </div>
    </xsl:for-each>
  </div>
</div>
<script>
(function() {
  var feedUrl = window.location.href;
  document.getElementById('feedUrl').textContent = feedUrl;
})();
function copyFeedUrl() {
  var url = window.location.href;
  var btn = document.getElementById('copyBtn');
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(function() {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function() { btn.textContent = 'Copy URL'; btn.classList.remove('copied'); }, 2000);
    });
  } else {
    var ta = document.createElement('textarea');
    ta.value = url; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy URL'; btn.classList.remove('copied'); }, 2000);
  }
}
</script>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
