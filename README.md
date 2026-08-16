# AI Stock Analysis Agent — Setup Guide

A two-agent CrewAI pipeline (Researcher → Analyst) that uses Firecrawl to get
around anti-bot walls on financial sites, then writes a structured stock
report. Now with a web frontend: a short executive summary by default, with
a "View full report" toggle for the complete detailed analysis.

## 1. Get your two API keys (do this first — everything else depends on it)

- **Gemini key**: Google AI Studio (aistudio.google.com) → Create API key.
  The free tier is generous enough to get this running and tested.
- **Firecrawl key**: firecrawl.dev → sign up → Dashboard → API key.
  Firecrawl has a free tier that's enough to get this running and tested.

## 2. Set up a clean Python environment

```bash
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Add your keys

Copy `.env.example` to `.env` and paste your real keys in:

```bash
cp .env.example .env
```

`.env` should look like:
```
GEMINI_API_KEY=AIza...
FIRECRAWL_API_KEY=fc-...
```

## 4. Run it

### Option A — Web UI (new)

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. Type a ticker or
company name, hit Analyze, and wait — a single run makes two live LLM calls
plus a web search, so it typically takes 30–90 seconds. You'll see:

- A **sentiment gauge** (Bullish / Neutral / Bearish)
- A **short executive summary** (3–5 sentences)
- A **"View full report"** toggle that expands into the complete detailed
  Markdown report (price action, sentiment reasoning, risks & red flags)

### Option B — Command line (original)

```bash
python stock_agent.py
```

You'll be prompted for a ticker or company name (e.g. `TCS`, `INFY`, `AAPL`).
With `verbose=True` on both agents, you'll see their reasoning and tool calls
printed live in the terminal — useful for the first few runs so you can see
what's actually happening under the hood, not just the final report.

## 5. What's happening, step by step

1. **Researcher agent** calls the `search_and_scrape_stock` tool, which hits
   Firecrawl's `/search` endpoint. Firecrawl does the actual browsing —
   it handles JS-heavy pages and anti-bot walls (Cloudflare etc.) that a plain
   `requests`/`BeautifulSoup` scraper would get blocked on, and returns clean
   Markdown instead of raw HTML.
2. That Markdown is handed to the **Analyst agent**, which has no tools of its
   own — it just reasons over the text it's given. It now returns a
   **structured `StockReport` object** (ticker, sentiment, short summary,
   full report) instead of one undifferentiated Markdown blob — that's what
   lets the frontend show a compressed answer with an option to expand.
3. `Process.sequential` in the `Crew` is what enforces "research first, then
   analysis" — the analyst's task only starts once the researcher's task
   output exists.
4. **`app.py`** is a thin Flask layer: `GET /` serves the page
   (`templates/index.html`), `POST /api/analyze` runs
   `run_stock_analysis(ticker)` from `stock_agent.py` and returns the
   `StockReport` fields as JSON. `static/script.js` calls that endpoint,
   animates the gauge, and renders the full report's Markdown client-side
   with marked.js.

## 6. Project structure

```
.
├── app.py              # Flask backend (new)
├── stock_agent.py       # CrewAI pipeline — now returns summary + full_report
├── templates/
│   └── index.html       # Page shell
├── static/
│   ├── style.css         # Dark trading-terminal styling
│   └── script.js         # Fetches /api/analyze, renders gauge + report
├── requirements.txt
├── .env.example
└── README.md
```
