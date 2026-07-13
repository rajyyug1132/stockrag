"""Custom /docs page: Swagger UI engine with a StockRAG visual theme.

Same swagger-ui-dist assets FastAPI would load, but BaseLayout (no topbar)
plus our own header and stylesheet on top.
"""

DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StockRAG API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<style>
:root {
  --bg: oklch(0.985 0 0);
  --surface: oklch(1 0 0);
  --ink: oklch(0.24 0.01 260);
  --ink-soft: oklch(0.45 0.015 260);
  --line: oklch(0.9 0.005 260);
  --accent: oklch(0.42 0.11 255);      /* primary action */
  --get: oklch(0.46 0.1 255);
  --get-bg: oklch(0.97 0.012 255);
  --post: oklch(0.46 0.09 165);
  --post-bg: oklch(0.97 0.014 165);
  --mono: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

body { margin: 0; background: var(--bg); }

/* ---- brand header ---- */
.srg-header {
  display: flex; align-items: baseline; gap: 12px;
  padding: 18px 24px; border-bottom: 1px solid var(--line);
  background: var(--surface); font-family: var(--sans);
}
.srg-header .name { font-size: 17px; font-weight: 650; color: var(--ink); letter-spacing: -0.01em; }
.srg-header .name .mark { color: var(--accent); }
.srg-header .tag { font-size: 13px; color: var(--ink-soft); }
.srg-header a {
  margin-left: auto; font-size: 13px; color: var(--accent);
  text-decoration: none; align-self: center;
}
.srg-header a:hover { text-decoration: underline; }

/* ---- swagger overrides ---- */
.swagger-ui, .swagger-ui .opblock-summary-path, .swagger-ui .info .title { font-family: var(--sans); }
.swagger-ui .wrapper { max-width: 980px; }

.swagger-ui .info { margin: 28px 0 12px; }
.swagger-ui .info .title { font-size: 26px; font-weight: 650; color: var(--ink); letter-spacing: -0.02em; }
.swagger-ui .info .title small.version-stamp { background: var(--accent); }
.swagger-ui .info hgroup.main a { display: none; }        /* /openapi.json link */
.swagger-ui .scheme-container { display: none; }          /* empty schemes bar */

/* one full hairline border + method-tinted fill; no left color stripes */
.swagger-ui .opblock {
  border: 1px solid var(--line); border-radius: 8px;
  box-shadow: none; margin-bottom: 10px; background: var(--surface);
}
.swagger-ui .opblock .opblock-summary { border: none; padding: 6px 12px; }
.swagger-ui .opblock.opblock-get { border-color: color-mix(in oklch, var(--get) 25%, white); background: var(--get-bg); }
.swagger-ui .opblock.opblock-post { border-color: color-mix(in oklch, var(--post) 25%, white); background: var(--post-bg); }

.swagger-ui .opblock .opblock-summary-method {
  border-radius: 6px; font-family: var(--mono); font-weight: 700; font-size: 12px;
  min-width: 64px; padding: 7px 0; text-shadow: none;
}
.swagger-ui .opblock.opblock-get .opblock-summary-method { background: var(--get); }
.swagger-ui .opblock.opblock-post .opblock-summary-method { background: var(--post); }

.swagger-ui .opblock .opblock-summary-path { font-family: var(--mono); font-size: 14.5px; color: var(--ink); }
.swagger-ui .opblock .opblock-summary-description { color: var(--ink-soft); font-size: 13px; }

.swagger-ui .opblock-tag {
  font-size: 15px; font-weight: 650; color: var(--ink);
  border-bottom: 1px solid var(--line); padding: 8px 0;
}

.swagger-ui .btn { border-radius: 6px; font-family: var(--sans); box-shadow: none; }
.swagger-ui .btn.execute { background: var(--accent); border-color: var(--accent); }
.swagger-ui .btn.try-out__btn { border-color: var(--line); color: var(--ink-soft); }

.swagger-ui select, .swagger-ui input[type=text] {
  border: 1px solid var(--line); border-radius: 6px; box-shadow: none;
}
.swagger-ui .parameter__name { font-family: var(--mono); color: var(--ink); }

.swagger-ui section.models { border: 1px solid var(--line); border-radius: 8px; }
.swagger-ui section.models h4 { font-size: 14px; color: var(--ink-soft); }
.swagger-ui section.models .model-container { background: var(--surface); border-radius: 6px; }

.swagger-ui .responses-inner h4, .swagger-ui .responses-inner h5 { color: var(--ink); }
.swagger-ui .response-col_status { font-family: var(--mono); }

@media (prefers-reduced-motion: reduce) {
  .swagger-ui * { transition: none !important; animation: none !important; }
}
</style>
</head>
<body>
<header class="srg-header">
  <span class="name">Stock<span class="mark">RAG</span> API</span>
  <span class="tag">SEC filings — factor reports &amp; cited answers</span>
  <a href="https://github.com/rajyyug1132/stockrag">GitHub</a>
</header>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  presets: [SwaggerUIBundle.presets.apis],
  layout: "BaseLayout",
  docExpansion: "list",
  defaultModelsExpandDepth: 0,
});
</script>
</body>
</html>"""
