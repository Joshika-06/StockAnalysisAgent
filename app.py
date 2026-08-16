"""
Flask backend for the AI Stock Analysis Agent frontend.

Serves:
  GET  /                -> the UI (templates/index.html)
  POST /api/analyze     -> runs the CrewAI pipeline for a ticker, returns JSON

Run:
    python app.py
Then open http://127.0.0.1:5000 in your browser.

Note: a single analysis run can take anywhere from ~20s to a couple of
minutes (two LLM agents + a live web search/scrape), so the frontend shows
a loading state and the fetch on the JS side has no artificial timeout.
"""

from flask import Flask, render_template, request, jsonify

from stock_agent import run_stock_analysis

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").strip()

    if not ticker:
        return jsonify({"ok": False, "error": "Please enter a ticker or company name."}), 400

    try:
        result = run_stock_analysis(ticker, verbose=True)
    except RuntimeError as e:
        # Missing API keys, etc.
        return jsonify({"ok": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unexpected error: {e}"}), 500

    status = 200 if result.get("ok") else 422
    return jsonify(result), status


if __name__ == "__main__":
    app.run(debug=True, port=5000)
