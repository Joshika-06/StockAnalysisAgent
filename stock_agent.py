"""
AI Stock Analysis Agent
------------------------
Two-agent CrewAI pipeline:
  1. Researcher -> uses Firecrawl to search + scrape live financial data
  2. Analyst    -> turns that raw data into a structured investment brief,
                    returned as BOTH a short executive summary and the full
                    detailed report (so a UI can show one and let the user
                    expand into the other).

Usage:
    CLI:      python stock_agent.py
    Imported: from stock_agent import run_stock_analysis
              result = run_stock_analysis("TCS")   # -> dict, see bottom of file
"""

import os
import sys
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

# ---------------------------------------------------------------------------
# 1. Load API keys from a .env file (never hardcode keys in the script itself)
# ---------------------------------------------------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")


def _check_keys():
    """Raise a clear error instead of letting the app half-start with no keys."""
    if not GEMINI_API_KEY or not FIRECRAWL_API_KEY:
        raise RuntimeError(
            "Missing API key(s). Copy .env.example to .env and fill in "
            "GEMINI_API_KEY and FIRECRAWL_API_KEY before running this."
        )


if GEMINI_API_KEY:
    # CrewAI/LiteLLM reads the Gemini key from this environment variable
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Native Gemini LLM for CrewAI - swap the model name if you want pro instead of flash
gemini_llm = LLM(model="gemini/gemini-2.5-flash", temperature=0.5)

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY) if FIRECRAWL_API_KEY else None


# ---------------------------------------------------------------------------
# 2. Tool: search + scrape financial data for a given query
# ---------------------------------------------------------------------------
@tool("Stock Search and Scrape Tool")
def search_and_scrape_stock(stock_query: str) -> str:
    """Searches the web for the latest stock updates and returns clean markdown."""
    try:
        search_result = firecrawl.search(
            query=f"latest stock price analysis financial updates {stock_query}",
            limit=5,
            scrape_options=ScrapeOptions(formats=["markdown"]),
        )
    except Exception as e:
        return f"TOOL_ERROR: {str(e)}"

    results = getattr(search_result, "web", None) or []
    if not results:
        return "TOOL_ERROR: No search results found for this query. Try a more specific term (e.g. add the exchange, like 'TCS NSE')."

    chunks = []
    for item in results:
        # Some results come back without a scraped body (e.g. the page failed
        # to scrape) - metadata/markdown may be missing, so guard every access.
        metadata = getattr(item, "metadata", None)
        title = (
            getattr(metadata, "title", None)
            or getattr(item, "title", None)
            or "Untitled"
        )
        url = getattr(metadata, "url", None) or getattr(item, "url", None) or ""
        markdown = (
            getattr(item, "markdown", None) or getattr(item, "description", None) or ""
        )[:2000]
        chunks.append(f"### {title}\nSource: {url}\n\n{markdown}")

    return "\n\n---\n\n".join(chunks)


# ---------------------------------------------------------------------------
# 3. Structured output model for the Analyst
#
# The old version just returned one big Markdown blob. A UI needs something
# short to show by default plus the full detail behind a "view full report"
# toggle, so the Analyst now returns both pieces in one structured object
# instead of us trying to truncate the Markdown after the fact.
# ---------------------------------------------------------------------------
class StockReport(BaseModel):
    ticker: str = Field(description="The ticker or company name that was analyzed")
    sentiment: str = Field(
        description="A single word verdict: Bullish, Bearish, or Neutral"
    )
    summary: str = Field(
        description=(
            "A tight 3-5 sentence executive summary in plain prose (no markdown "
            "headers, no bullet points): the current price action, the single "
            "biggest catalyst driving it, and the top risk to watch."
        )
    )
    full_report: str = Field(
        description=(
            "The complete, detailed investment report in Markdown, including "
            "these sections: '## Executive Summary' (recent price action & "
            "immediate catalysts), '## Core Sentiment Analysis' (is the "
            "current web narrative bullish or bearish, and why), and "
            "'## Risks & Red Flags' (discovered in recent press releases or "
            "articles). This should be thorough - the summary field above is "
            "the short version, this field is the long version."
        )
    )


# ---------------------------------------------------------------------------
# 4. Agents
# ---------------------------------------------------------------------------
researcher = Agent(
    role="Senior Financial Web Researcher",
    goal="Extract the latest news, regulatory updates, and raw financial metrics for a given stock.",
    backstory=(
        "An expert in navigating complex financial web layouts. You bypass noise "
        "to extract hard data points, breaking news, corporate announcements, and sector headwinds."
    ),
    tools=[search_and_scrape_stock],
    llm=gemini_llm,
    verbose=True,
    memory=True,
)

analyst = Agent(
    role="Lead Equity Analyst",
    goal="Synthesize raw web data into professional, actionable investment summaries.",
    backstory=(
        "A sharp Wall Street veteran. You take messy web text, spot technical or fundamental "
        "trends, gauge market sentiment, and build clear, concise structural reports with data-backed conclusions."
    ),
    llm=gemini_llm,
    verbose=True,
)


# ---------------------------------------------------------------------------
# 5. Tasks + Crew orchestration
# ---------------------------------------------------------------------------
def run_stock_analysis(ticker: str, verbose: bool = True) -> dict:
    """
    Runs the full research -> analysis pipeline for `ticker`.

    Always returns a dict shaped like:
        {
            "ok": bool,
            "ticker": str,
            "sentiment": str | None,   # "Bullish" / "Bearish" / "Neutral"
            "summary": str | None,     # short version
            "full_report": str | None, # long version (Markdown)
            "error": str | None,       # set only when ok is False
        }
    This shape is what the Flask API (app.py) hands straight to the frontend.
    """
    _check_keys()

    researcher.verbose = verbose
    analyst.verbose = verbose

    # --- Phase 1: research only ---
    research_task = Task(
        description=(
            f"Search and extract the absolute latest financial updates, stock price trends, "
            f"and notable news for ticker: {ticker}. Focus on gathering raw numbers, recent earnings data, "
            f"or management changes from authoritative financial websites."
        ),
        expected_output="A comprehensive Markdown document compiling raw data, news snippets, and financial metrics.",
        agent=researcher,
    )
    research_crew = Crew(
        agents=[researcher], tasks=[research_task], process=Process.sequential
    )
    research_output = str(research_crew.kickoff())

    # Hard stop here: if the tool failed, don't let the Analyst improvise a
    # "report" out of nothing. Fail loudly and clearly instead.
    if "TOOL_ERROR" in research_output:
        return {
            "ok": False,
            "ticker": ticker,
            "sentiment": None,
            "summary": None,
            "full_report": None,
            "error": (
                "Research step failed - stopping before analysis so the Analyst "
                f"doesn't fabricate a report from missing data.\n\nDetails:\n{research_output}"
            ),
        }

    # --- Phase 2: analysis, only runs if research actually returned data ---
    analysis_task = Task(
        description=(
            f"Using the research findings below, create a detailed stock analysis report for {ticker}.\n\n"
            f"RESEARCH FINDINGS:\n{research_output}\n\n"
            "Return BOTH a short executive summary and the full detailed report - see the "
            "required output fields."
        ),
        expected_output=(
            "A StockReport object with: ticker, sentiment (Bullish/Bearish/Neutral), "
            "a short plain-prose summary, and the full Markdown report covering "
            "Executive Summary, Core Sentiment Analysis, and Risks & Red Flags."
        ),
        agent=analyst,
        output_pydantic=StockReport,
    )
    analysis_crew = Crew(
        agents=[analyst], tasks=[analysis_task], process=Process.sequential
    )
    result = analysis_crew.kickoff()

    parsed: StockReport | None = getattr(result, "pydantic", None)
    if parsed is None:
        # Structured parsing failed for some reason - fall back to raw text
        # rather than losing the run entirely.
        raw = str(result)
        return {
            "ok": True,
            "ticker": ticker,
            "sentiment": "Neutral",
            "summary": raw[:400] + ("..." if len(raw) > 400 else ""),
            "full_report": raw,
            "error": None,
        }

    return {
        "ok": True,
        "ticker": parsed.ticker or ticker,
        "sentiment": parsed.sentiment,
        "summary": parsed.summary,
        "full_report": parsed.full_report,
        "error": None,
    }


if __name__ == "__main__":
    try:
        _check_keys()
    except RuntimeError as e:
        sys.exit(str(e))

    target_stock = input("Enter the stock ticker/name to analyze: ").strip()
    if not target_stock:
        sys.exit("Please provide a ticker or company name.")

    print(f"\n🚀 Activating agents to analyze {target_stock}...\n")
    report = run_stock_analysis(target_stock)

    print("\n================ FINAL REPORT ================\n")
    if not report["ok"]:
        print(f"❌ {report['error']}")
    else:
        print(f"Ticker: {report['ticker']}")
        print(f"Sentiment: {report['sentiment']}\n")
        print("--- Summary ---")
        print(report["summary"])
        print("\n--- Full Report ---")
        print(report["full_report"])
