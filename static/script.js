(function () {
  const input       = document.getElementById('ticker-input');
  const btn         = document.getElementById('analyze-btn');
  const errorBox    = document.getElementById('error-box');
  const loading     = document.getElementById('loading');
  const report      = document.getElementById('report');
  const reportTicker= document.getElementById('report-ticker');
  const reportSummary = document.getElementById('report-summary');
  const sentimentLabel = document.getElementById('sentiment-label');
  const gaugeFill   = document.getElementById('gauge-fill');
  const gaugeNeedle = document.getElementById('gauge-needle');
  const toggleFull  = document.getElementById('toggle-full');
  const fullWrap    = document.getElementById('full-report-wrap');
  const fullReport  = document.getElementById('full-report');

  const CIRCUMFERENCE = 251.2; // matches the SVG arc's stroke-dasharray

  // sentiment -> { fillOffset (0=full bearish arc, 251.2=full bullish arc), needle angle deg, color, label }
  const SENTIMENT_MAP = {
    bullish: { offset: CIRCUMFERENCE * 0.06, angle: 60,  color: 'var(--green)' },
    neutral: { offset: CIRCUMFERENCE * 0.5,  angle: 0,   color: 'var(--neutral)' },
    bearish: { offset: CIRCUMFERENCE * 0.94, angle: -60, color: 'var(--red)' },
  };

  function normalizeSentiment(raw) {
    const s = (raw || '').toLowerCase();
    if (s.includes('bull')) return 'bullish';
    if (s.includes('bear')) return 'bearish';
    return 'neutral';
  }

  function setGauge(rawSentiment) {
    const key = normalizeSentiment(rawSentiment);
    const cfg = SENTIMENT_MAP[key];
    gaugeFill.style.strokeDashoffset = String(CIRCUMFERENCE - cfg.offset);
    gaugeFill.style.stroke = cfg.color;
    gaugeNeedle.style.transform = `rotate(${cfg.angle}deg)`;
    sentimentLabel.textContent = (rawSentiment || key).toUpperCase();
    sentimentLabel.style.color = cfg.color;
  }

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
  }

  function clearError() {
    errorBox.classList.add('hidden');
    errorBox.textContent = '';
  }

  function resetReport() {
    report.classList.add('hidden');
    fullWrap.classList.remove('expanded');
    toggleFull.setAttribute('aria-expanded', 'false');
    toggleFull.querySelector('span').textContent = 'View full report';
  }

  async function analyze() {
    const ticker = input.value.trim();
    if (!ticker) {
      showError('Enter a ticker or company name first.');
      input.focus();
      return;
    }

    clearError();
    resetReport();
    loading.classList.remove('hidden');
    btn.disabled = true;

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker }),
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        showError(data.error || 'Something went wrong while analyzing that ticker.');
        return;
      }

      reportTicker.textContent = data.ticker || ticker;
      reportSummary.textContent = data.summary || '(no summary returned)';
      setGauge(data.sentiment);
      fullReport.innerHTML = window.marked
        ? marked.parse(data.full_report || '')
        : (data.full_report || '').replace(/\n/g, '<br>');

      report.classList.remove('hidden');
    } catch (err) {
      showError('Could not reach the server. Is app.py running?');
    } finally {
      loading.classList.add('hidden');
      btn.disabled = false;
    }
  }

  toggleFull.addEventListener('click', () => {
    const expanded = fullWrap.classList.toggle('expanded');
    toggleFull.setAttribute('aria-expanded', String(expanded));
    toggleFull.querySelector('span').textContent = expanded ? 'Hide full report' : 'View full report';
  });

  btn.addEventListener('click', analyze);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') analyze();
  });
})();
