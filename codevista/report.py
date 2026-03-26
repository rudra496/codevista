"""HTML report generator — self-contained, beautiful, interactive.

Generates a single HTML file with modern purple/blue/teal gradient theme,
dark mode, glassmorphism, animations, inline SVG charts, and responsive design.
"""

import json
import os
import math
import html as html_mod
from datetime import datetime
from collections import Counter

from .metrics import calculate_health, get_trend, generate_recommendations
from .security import security_summary, get_severity_color
from .languages import get_lang_color, group_languages_for_chart


def generate_report(analysis: dict, output_path: str = None) -> str:
    """Generate a self-contained HTML report."""
    scores = calculate_health(analysis)
    recommendations = generate_recommendations(analysis, scores)
    sec_sum = security_summary(analysis['security_issues'])
    report_html = build_html(analysis, scores, recommendations, sec_sum)
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_html)
    return report_html


def esc(s):
    return html_mod.escape(str(s), quote=True)


def score_color(score):
    if score >= 80:
        return '#2cb67d'
    elif score >= 50:
        return '#ff8906'
    return '#e53170'


def trend_icon(trend):
    return {'good': '✅', 'warning': '⚠️', 'critical': '❌'}.get(trend, '❓')


def build_html(analysis, scores, recommendations, sec_sum):
    """Build the complete HTML report with all sections."""
    a = analysis
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    files_json = json.dumps([{
        'path': f['path'], 'lang': f['language'], 'color': f['color'],
        'total': f['lines']['total'], 'code': f['lines']['code'],
        'comment': f['lines']['comment'], 'blank': f['lines']['blank'],
        'complexity': f['complexity'], 'maintainability': f.get('maintainability_index', 0),
        'size': f['size'],
    } for f in a['files']])

    funcs_json = json.dumps([{
        'name': f['name'], 'file': f.get('file', ''),
        'line': f['start_line'], 'complexity': f['complexity'],
        'cognitive': f.get('cognitive_complexity', 0),
        'params': f['param_count'], 'nesting': f.get('nesting_depth', 0),
        'loc': f['line_count'],
    } for f in a.get('top_complex_functions', [])])

    lang_grouped = group_languages_for_chart(a['languages'])
    pie_svg = build_pie_svg(lang_grouped)
    bar_svg = build_bar_svg(sorted(a['files'], key=lambda x: x['lines']['total'], reverse=True)[:15])
    comp_svg = build_complexity_svg(sorted(a['files'], key=lambda x: x['complexity'], reverse=True)[:10])
    size_svg = build_size_dist_svg(a.get('size_distribution', {}))
    comp_hist_svg = build_complexity_histogram(a.get('complexity_distribution', {}))

    heatmap_svg = ''
    if a.get('git') and a['git'].get('heatmap'):
        heatmap_svg = build_heatmap_svg(a['git']['heatmap'])

    sec_html = build_security_section(a['security_issues'], sec_sum)
    recs_html = build_recommendations_section(recommendations)
    deps_html = build_deps_section(a)
    tree_html = build_tree_html(a.get('dir_tree', {}))
    git_html = build_git_section(a.get('git'))
    metrics_html = build_metrics_section(a)
    tech_html = build_tech_section(a)

    severity_donut = build_severity_donut(sec_sum.get('by_severity', {}))
    contributors_svg = ''
    if a.get('git') and a['git'].get('authors'):
        contributors_svg = build_contributors_svg(a['git']['authors'][:12])
    timeline_svg = ''
    if a.get('git') and a['git'].get('commit_timeline'):
        timeline_svg = build_timeline_svg(a['git']['commit_timeline'])

    lang_badges = ''.join(
        f'<span class="badge lang-badge" style="border-color:{get_lang_color(l)};color:{get_lang_color(l)}">{esc(l)} ({a["languages"][l]:,})</span>'
        for l in sorted(a['languages'].keys(), key=lambda x: a['languages'][x], reverse=True)[:15]
    )

    fw_badges = ''.join(
        f'<span class="badge">{esc(fw)}</span>' for fw in a.get('frameworks', [])[:20]
    )

    import_graph_svg = build_import_graph_svg(a.get('import_graph', {}))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeVista — {esc(a["project_name"])}</title>
<style>
/* ── Theme Variables ─────────────────────────────────── */
:root {{
  --bg: #0a0a1a; --surface: #12122a; --surface2: #1a1a3e; --surface3: #222250;
  --glass: rgba(127,90,240,0.06); --glass-border: rgba(127,90,240,0.12);
  --text: #eeeef5; --text2: #8888aa; --text3: #5a5a7a;
  --primary: #7f5af0; --primary-light: #a78bfa; --primary-dark: #5b3fd4;
  --green: #2cb67d; --green-light: #34d399;
  --accent: #e53170; --accent-light: #f472b6;
  --warning: #ff8906; --warning-light: #fbbf24;
  --info: #38bdf8; --teal: #14b8a6;
  --radius: 16px; --radius-sm: 10px; --radius-xs: 6px;
  --shadow: 0 4px 24px rgba(0,0,0,0.3); --shadow-lg: 0 8px 48px rgba(0,0,0,0.4);
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}

/* ── Reset & Base ───────────────────────────────────── */
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  line-height: 1.6; min-height: 100vh; overflow-x: hidden;
}}
body::before {{
  content: ''; position: fixed; inset: 0; z-index: -1;
  background: radial-gradient(ellipse at 20% 0%, rgba(127,90,240,0.08) 0%, transparent 60%),
              radial-gradient(ellipse at 80% 100%, rgba(20,184,166,0.06) 0%, transparent 60%);
}}

/* ── Layout ─────────────────────────────────────────── */
.container {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
.main-content {{ margin-left: 0; transition: margin var(--transition); }}

/* ── Sidebar ────────────────────────────────────────── */
.sidebar {{
  position: fixed; left: 0; top: 0; bottom: 0; width: 240px;
  background: var(--surface); border-right: 1px solid var(--glass-border);
  padding: 20px 0; z-index: 50; overflow-y: auto;
  transition: transform var(--transition);
}}
.sidebar .logo {{ padding: 12px 20px; font-size: 1.2em; font-weight: 800; color: var(--primary-light); }}
.sidebar nav a {{
  display: flex; align-items: center; gap: 10px; padding: 10px 20px;
  color: var(--text2); text-decoration: none; font-size: 0.9em;
  transition: all var(--transition); border-left: 3px solid transparent;
}}
.sidebar nav a:hover, .sidebar nav a.active {{
  color: var(--text); background: var(--glass); border-left-color: var(--primary);
}}
.sidebar nav a .icon {{ font-size: 1.1em; width: 24px; text-align: center; }}

@media (max-width: 900px) {{
  .sidebar {{ transform: translateX(-100%); }}
  .sidebar.open {{ transform: translateX(0); }}
  .main-content {{ margin-left: 0 !important; }}
  .menu-btn {{ display: flex !important; }}
}}
.menu-btn {{
  display: none; position: fixed; top: 16px; left: 16px; z-index: 60;
  width: 40px; height: 40px; border-radius: 10px; background: var(--surface);
  border: 1px solid var(--glass-border); color: var(--text);
  align-items: center; justify-content: center; font-size: 1.2em; cursor: pointer;
}}

/* ── Header ─────────────────────────────────────────── */
header {{
  background: linear-gradient(135deg, var(--primary-dark), var(--primary), var(--teal));
  border-radius: var(--radius); padding: 48px 40px; margin-bottom: 28px;
  position: relative; overflow: hidden;
}}
header::before {{
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 25% 40%, rgba(255,255,255,0.12) 0%, transparent 50%),
              radial-gradient(circle at 75% 70%, rgba(20,184,166,0.15) 0%, transparent 40%);
}}
header::after {{
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.15) 100%);
}}
header h1 {{ font-size: 2.5em; font-weight: 900; position: relative; letter-spacing: -0.5px; }}
header .subtitle {{ opacity: 0.9; margin-top: 6px; font-size: 1.15em; position: relative; }}
header .meta {{ margin-top: 18px; opacity: 0.7; font-size: 0.9em; position: relative; }}
.header-badge {{
  display: inline-block; background: rgba(255,255,255,0.15); padding: 3px 10px;
  border-radius: 20px; font-size: 0.8em; margin-right: 6px; backdrop-filter: blur(4px);
}}

/* ── Health Ring ────────────────────────────────────── */
.health-ring {{
  position: absolute; right: 40px; top: 50%; transform: translateY(-50%);
}}
.health-ring svg {{ width: 130px; height: 130px; filter: drop-shadow(0 0 12px rgba(127,90,240,0.4)); }}
.health-ring .score-text {{
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; font-size: 2.2em; font-weight: 900;
}}
.health-ring .score-label {{ font-size: 0.35em; color: rgba(255,255,255,0.6); margin-top: 2px; }}
.score-ring-bg {{ transition: stroke-dasharray 1.5s cubic-bezier(0.4, 0, 0.2, 1); }}

/* ── Stats Grid ─────────────────────────────────────── */
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
.stat-card {{
  background: var(--glass); backdrop-filter: blur(12px); border-radius: var(--radius);
  padding: 20px; border: 1px solid var(--glass-border);
  transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
}}
.stat-card:hover {{ transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(127,90,240,0.25); }}
.stat-card .label {{ color: var(--text2); font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px; }}
.stat-card .value {{ font-size: 2em; font-weight: 800; margin-top: 4px; }}
.stat-card .sub {{ color: var(--text3); font-size: 0.8em; margin-top: 4px; }}

/* ── Scores Grid ────────────────────────────────────── */
.scores-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
.score-card {{
  background: var(--glass); backdrop-filter: blur(12px); border-radius: var(--radius-sm);
  padding: 18px 14px; text-align: center; border: 1px solid var(--glass-border);
  transition: transform var(--transition);
}}
.score-card:hover {{ transform: translateY(-2px); }}
.score-card .score-label {{ color: var(--text2); font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px; }}
.score-card .score-value {{ font-size: 1.8em; font-weight: 800; margin: 4px 0; }}
.score-card .trend {{ font-size: 1.1em; }}
.score-bar {{ height: 4px; border-radius: 2px; background: var(--surface3); margin-top: 8px; overflow: hidden; }}
.score-bar-fill {{ height: 100%; border-radius: 2px; transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1); }}

/* ── Sections ───────────────────────────────────────── */
.section {{
  background: var(--glass); backdrop-filter: blur(12px); border-radius: var(--radius);
  padding: 28px; margin-bottom: 24px; border: 1px solid var(--glass-border);
  animation: fadeSlideUp 0.6s ease-out both;
}}
.section:nth-child(2) {{ animation-delay: 0.05s; }}
.section:nth-child(3) {{ animation-delay: 0.1s; }}
.section:nth-child(4) {{ animation-delay: 0.15s; }}
.section:nth-child(5) {{ animation-delay: 0.2s; }}
.section:nth-child(6) {{ animation-delay: 0.25s; }}
@keyframes fadeSlideUp {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.section h2 {{
  font-size: 1.25em; margin-bottom: 18px; display: flex; align-items: center; gap: 10px;
}}
.section h2 .icon {{ font-size: 1.3em; }}
.section.collapsed .section-body {{ display: none; }}
.section-header {{
  cursor: pointer; user-select: none; display: flex; align-items: center;
  justify-content: space-between;
}}
.section-header .toggle {{ color: var(--text2); font-size: 1.1em; transition: transform var(--transition); }}
.section.collapsed .toggle {{ transform: rotate(-90deg); }}

/* ── Badges ─────────────────────────────────────────── */
.badges {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
.badge {{
  background: rgba(127,90,240,0.12); color: var(--primary-light); padding: 5px 14px;
  border-radius: 20px; font-size: 0.82em; font-weight: 600;
  border: 1px solid rgba(127,90,240,0.2); transition: all var(--transition);
}}
.badge:hover {{ background: rgba(127,90,240,0.2); border-color: var(--primary); }}
.lang-badge {{ background: transparent; }}

/* ── Tables ─────────────────────────────────────────── */
.table-wrap {{ overflow-x: auto; margin-top: 12px; border-radius: var(--radius-sm); }}
table {{ width: 100%; border-collapse: collapse; }}
th {{
  text-align: left; padding: 12px 14px; color: var(--text2); font-size: 0.75em;
  text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--glass-border);
  cursor: pointer; user-select: none; white-space: nowrap;
}}
th:hover {{ color: var(--primary-light); }}
td {{ padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 0.88em; }}
tr:hover {{ background: rgba(127,90,240,0.04); }}
tr:last-child td {{ border-bottom: none; }}

/* ── Security Items ─────────────────────────────────── */
.sec-item {{
  display: flex; align-items: flex-start; gap: 14px; padding: 14px;
  background: var(--surface2); border-radius: var(--radius-sm);
  margin-bottom: 8px; border-left: 3px solid var(--accent);
  transition: transform var(--transition);
}}
.sec-item:hover {{ transform: translateX(3px); }}
.severity-badge {{
  padding: 2px 10px; border-radius: 4px; font-size: 0.72em; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px; flex-shrink: 0; white-space: nowrap;
}}
.severity-badge.critical {{ background: rgba(229,49,112,0.15); color: var(--accent); }}
.severity-badge.high {{ background: rgba(255,137,6,0.15); color: var(--warning); }}
.severity-badge.medium {{ background: rgba(127,90,240,0.15); color: var(--primary-light); }}
.severity-badge.low {{ background: rgba(167,169,190,0.1); color: var(--text2); }}

/* ── Recommendations ────────────────────────────────── */
.rec {{
  display: flex; gap: 14px; padding: 14px; background: var(--surface2);
  border-radius: var(--radius-sm); margin-bottom: 8px;
  border-left: 3px solid var(--primary);
  transition: transform var(--transition);
}}
.rec:hover {{ transform: translateX(3px); }}
.rec .icon {{ font-size: 1.4em; flex-shrink: 0; margin-top: 2px; }}
.rec .content {{ flex: 1; }}
.rec .category {{ font-size: 0.75em; color: var(--primary-light); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
.rec .priority {{
  display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 0.7em;
  font-weight: 600; margin-left: 8px;
}}
.rec .priority.critical {{ background: rgba(229,49,112,0.15); color: var(--accent); }}
.rec .priority.high {{ background: rgba(255,137,6,0.15); color: var(--warning); }}
.rec .priority.medium {{ background: rgba(127,90,240,0.15); color: var(--primary-light); }}
.rec .priority.low {{ background: rgba(167,169,190,0.1); color: var(--text2); }}

/* ── Directory Tree ─────────────────────────────────── */
.tree {{ font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace; font-size: 0.82em; line-height: 2; }}
.tree .dir {{ color: var(--primary-light); font-weight: 600; cursor: pointer; }}
.tree .dir:hover {{ color: var(--text); }}
.tree .file {{ color: var(--text2); }}
.tree .size {{ color: var(--text3); font-size: 0.85em; }}
.tree .indent {{ display: inline-block; width: 24px; }}
.tree-children {{ display: block; }}
.tree-collapsed > .tree-children {{ display: none; }}
.tree-toggle {{ cursor: pointer; user-select: none; }}

/* ── Search ─────────────────────────────────────────── */
.search-wrap {{ position: relative; margin-bottom: 16px; }}
.search {{
  width: 100%; padding: 12px 16px 12px 44px; background: var(--surface2);
  border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
  color: var(--text); font-size: 0.95em; outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}}
.search:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(127,90,240,0.15); }}
.search::placeholder {{ color: var(--text3); }}
.search-icon {{ position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--text3); }}

/* ── Filter Pills ───────────────────────────────────── */
.filters {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }}
.filter-pill {{
  padding: 4px 14px; border-radius: 20px; font-size: 0.78em; cursor: pointer;
  background: var(--surface2); color: var(--text2); border: 1px solid transparent;
  transition: all var(--transition);
}}
.filter-pill:hover, .filter-pill.active {{
  background: rgba(127,90,240,0.15); color: var(--primary-light); border-color: var(--primary);
}}

/* ── Charts ─────────────────────────────────────────── */
.chart-container {{ margin: 18px 0; overflow-x: auto; }}
.chart-container svg {{ display: block; max-width: 100%; }}
.chart-title {{ font-size: 1em; font-weight: 600; margin-bottom: 8px; color: var(--text2); }}

/* ── Theme Toggle ───────────────────────────────────── */
.theme-toggle {{
  position: fixed; bottom: 24px; right: 24px; width: 48px; height: 48px;
  border-radius: 50%; background: var(--surface); border: 1px solid var(--glass-border);
  color: var(--text); font-size: 1.4em; cursor: pointer; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  transition: transform var(--transition), box-shadow var(--transition);
  box-shadow: var(--shadow);
}}
.theme-toggle:hover {{ transform: scale(1.1); box-shadow: var(--shadow-lg); }}

/* ── Scroll to top ──────────────────────────────────── */
.scroll-top {{
  position: fixed; bottom: 80px; right: 24px; width: 42px; height: 42px;
  border-radius: 50%; background: var(--primary); border: none;
  color: white; font-size: 1.2em; cursor: pointer; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; transition: opacity var(--transition);
  box-shadow: 0 4px 12px rgba(127,90,240,0.3);
}}
.scroll-top.visible {{ opacity: 1; pointer-events: auto; }}

/* ── Print ──────────────────────────────────────────── */
@media print {{
  body {{ background: white !important; color: black !important; }}
  body::before {{ display: none; }}
  .sidebar, .theme-toggle, .scroll-top, .menu-btn {{ display: none !important; }}
  .main-content {{ margin-left: 0 !important; }}
  header {{ background: #7f5af0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .section {{ background: white !important; border: 1px solid #ddd !important; backdrop-filter: none !important;
              break-inside: avoid; }}
  .stat-card, .score-card, .sec-item, .rec {{ background: white !important; border: 1px solid #eee !important; }}
}}

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 768px) {{
  header {{ padding: 28px 24px; }}
  .health-ring {{ width: 90px; height: 90px; right: 20px; }}
  .health-ring svg {{ width: 90px; height: 90px; }}
  .health-ring .score-text {{ font-size: 1.6em; }}
  .stats {{ grid-template-columns: repeat(2, 1fr); }}
  .section {{ padding: 20px; }}
}}

/* ── Misc ───────────────────────────────────────────── */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
.text-muted {{ color: var(--text3); }}
.text-sm {{ font-size: 0.85em; }}
.mt-2 {{ margin-top: 16px; }}
.mt-3 {{ margin-top: 24px; }}
.mb-2 {{ margin-bottom: 16px; }}
.fw-600 {{ font-weight: 600; }}
</style>
</head>
<body>
<button class="menu-btn" onclick="document.querySelector('.sidebar').classList.toggle('open')">☰</button>

<aside class="sidebar" id="sidebar">
  <div class="logo">🔍 CodeVista</div>
  <nav>
    <a href="#dashboard"><span class="icon">📊</span> Dashboard</a>
    <a href="#scores"><span class="icon">🏥</span> Health Scores</a>
    <a href="#tech"><span class="icon">🧩</span> Tech Stack</a>
    <a href="#structure"><span class="icon">📁</span> Architecture</a>
    <a href="#metrics"><span class="icon">📈</span> Code Metrics</a>
    <a href="#functions"><span class="icon">⚡</span> Functions</a>
    <a href="#files"><span class="icon">📋</span> All Files</a>
    {"<a href='#security'><span class='icon'>🔒</span> Security</a>" if sec_sum["total"] > 0 else ""}
    <a href="#deps"><span class="icon">📦</span> Dependencies</a>
    {"<a href='#git'><span class='icon'>👥</span> Git Insights</a>" if a.get('git') else ""}
    <a href="#recs"><span class="icon">💡</span> Recommendations</a>
  </nav>
</aside>

<button class="scroll-top" id="scrollTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">↑</button>
<button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>

<div class="container">
<div class="main-content" id="mainContent">

<!-- Dashboard -->
<header id="dashboard">
  <h1>🔍 CodeVista</h1>
  <div class="subtitle">{esc(a["project_name"])} — Codebase Analysis Report</div>
  <div class="meta">
    <span class="header-badge">📅 {now}</span>
    <span class="header-badge">📁 {a["total_files"]:,} files</span>
    <span class="header-badge">📝 {a["total_lines"]["code"]:,} LoC</span>
  </div>
  <div class="health-ring">
    <svg viewBox="0 0 130 130">
      <defs>
        <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:{score_color(scores['overall'])};stop-opacity:1" />
          <stop offset="100%" style="stop-color:var(--teal);stop-opacity:0.8" />
        </linearGradient>
      </defs>
      <circle cx="65" cy="65" r="54" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>
      <circle cx="65" cy="65" r="54" fill="none" stroke="url(#scoreGrad)" stroke-width="10"
        stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(-90 65 65)"
        class="score-ring-bg" id="scoreRing"/>
    </svg>
    <div class="score-text" style="color:{score_color(scores['overall'])}">
      <span id="scoreNum">0</span>
      <div class="score-label">Health Score</div>
    </div>
  </div>
</header>

<div class="stats">
  <div class="stat-card"><div class="label">Files</div><div class="value">{a["total_files"]:,}</div><div class="sub">source files analyzed</div></div>
  <div class="stat-card"><div class="label">Lines of Code</div><div class="value">{a["total_lines"]["code"]:,}</div><div class="sub">{a["total_lines"]["comment"]:,} comments · {a["total_lines"]["blank"]:,} blank</div></div>
  <div class="stat-card"><div class="label">Languages</div><div class="value">{len(a["languages"])}</div><div class="sub">{", ".join(sorted(a["languages"].keys(), key=lambda x: a["languages"][x], reverse=True)[:4])}</div></div>
  <div class="stat-card"><div class="label">Complexity</div><div class="value">{a["avg_complexity"]:.1f}</div><div class="sub">avg cyclomatic · max {a["max_complexity"]}</div></div>
  <div class="stat-card"><div class="label">Functions</div><div class="value">{len(a.get('functions',[])):,}</div><div class="sub">methods analyzed</div></div>
  <div class="stat-card"><div class="label">Security</div><div class="value" style="color:{score_color(sec_sum['score'])}">{sec_sum["total"]}</div><div class="sub">issues found · score {sec_sum["score"]}</div></div>
  <div class="stat-card"><div class="label">Dependencies</div><div class="value">{len(a["dependencies"])}</div><div class="sub">{esc(a["package_manager"] or "none detected")}</div></div>
  <div class="stat-card"><div class="label">TODOs</div><div class="value">{len(a.get('todos',[]))}</div><div class="sub">technical debt markers</div></div>
</div>

<!-- Health Scores -->
<section class="section" id="scores">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">🏥</span> Health Scores</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <div class="scores-grid">
      {" ".join(f'''<div class="score-card">
        <div class="score-label">{cat.replace("_"," ").title()}</div>
        <div class="score-value" style="color:{score_color(scores[cat])}">{scores[cat]}</div>
        <div class="trend">{trend_icon(get_trend(scores[cat]))}</div>
        <div class="score-bar"><div class="score-bar-fill" style="width:{scores[cat]}%;background:{score_color(scores[cat])}"></div></div>
      </div>''' for cat in ['readability','complexity','duplication','coverage','security','dependencies','maintainability'])}
    </div>
  </div>
</section>

<!-- Tech Stack -->
<section class="section" id="tech">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">🧩</span> Technology Stack</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <div class="grid-2">
      <div>
        <div class="chart-title">Languages</div>
        <div class="badges">{lang_badges}</div>
      </div>
      <div>
        <div class="chart-title">Frameworks &amp; Tools</div>
        <div class="badges">{fw_badges if a.get('frameworks') else '<span class="text-muted">No frameworks detected</span>'}</div>
      </div>
    </div>
    {tech_html}
    <div class="chart-container">{pie_svg}</div>
  </div>
</section>

<!-- Architecture -->
<section class="section" id="structure">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">📁</span> Architecture</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <div class="grid-2">
      <div>
        <div class="chart-title">Directory Tree</div>
        <div class="tree" id="dirTree">{tree_html}</div>
      </div>
      <div>
        <div class="chart-title">Import Graph (Top Modules)</div>
        <div class="chart-container">{import_graph_svg}</div>
      </div>
    </div>
  </div>
</section>

<!-- Code Metrics -->
<section class="section" id="metrics">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">📈</span> Code Metrics</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    {metrics_html}
    <div class="grid-2">
      <div>
        <div class="chart-title">LOC by File (Top 15)</div>
        <div class="chart-container">{bar_svg}</div>
      </div>
      <div>
        <div class="chart-title">Complexity Hot Spots</div>
        <div class="chart-container">{comp_svg}</div>
      </div>
    </div>
    <div class="grid-2 mt-3">
      <div>
        <div class="chart-title">File Size Distribution</div>
        <div class="chart-container">{size_svg}</div>
      </div>
      <div>
        <div class="chart-title">Complexity Distribution</div>
        <div class="chart-container">{comp_hist_svg}</div>
      </div>
    </div>
  </div>
</section>

<!-- Functions -->
<section class="section" id="functions">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">⚡</span> Top Complex Functions</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <div class="table-wrap"><table id="funcsTable">
      <thead><tr><th onclick="sortFuncs(0)">Function</th><th onclick="sortFuncs(1)">File</th><th onclick="sortFuncs(2)">Complexity</th><th onclick="sortFuncs(3)">Cognitive</th><th onclick="sortFuncs(4)">Params</th><th onclick="sortFuncs(5)">Nesting</th><th onclick="sortFuncs(6)">Lines</th></tr></thead>
      <tbody id="funcsBody"></tbody>
    </table></div>
  </div>
</section>

<!-- All Files -->
<section class="section" id="files">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">📋</span> All Files</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input type="text" class="search" placeholder="Search files..." id="fileSearch" oninput="renderFiles()">
    </div>
    <div class="filters" id="langFilters"></div>
    <div class="table-wrap"><table id="filesTable">
      <thead><tr><th onclick="sortTable(0)">File</th><th onclick="sortTable(1)">Language</th><th onclick="sortTable(2)">Lines</th><th onclick="sortTable(3)">Code</th><th onclick="sortTable(4)">Comments</th><th onclick="sortTable(5)">Complexity</th><th onclick="sortTable(6)">Maint.</th><th onclick="sortTable(7)">Size</th></tr></thead>
      <tbody id="filesBody"></tbody>
    </table></div>
  </div>
</section>

<!-- Security -->
{"<section class='section' id='security'><div class='section-header' onclick='toggleSection(this)'><h2><span class='icon'>🔒</span> Security Scan</h2><span class='toggle'>▼</span></div><div class='section-body'>" + sec_html + "</div></section>" if sec_sum["total"] > 0 else ""}

<!-- Dependencies -->
<section class="section" id="deps">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">📦</span> Dependencies</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">{deps_html}</div>
</section>

<!-- Git Insights -->
{"<section class='section' id='git'><div class='section-header' onclick='toggleSection(this)'><h2><span class='icon'>👥</span> Git Insights</h2><span class='toggle'>▼</span></div><div class='section-body'>" + git_html + "</div></section>" if a.get('git') else ""}

<!-- Recommendations -->
<section class="section" id="recs">
  <div class="section-header" onclick="toggleSection(this)">
    <h2><span class="icon">💡</span> Recommendations</h2><span class="toggle">▼</span>
  </div>
  <div class="section-body">{recs_html}</div>
</section>

<div style="text-align:center;padding:40px 0;color:var(--text3);font-size:0.85em;">
  Generated by <strong style="color:var(--primary-light)">CodeVista</strong> · {now}
</div>

</div>
</div>

<script>
const FILES = {{files_json}};
const FUNCS = {{funcs_json}};
let currentLang = null, sortCol = 2, sortAsc = false;
let funcSortCol = 2, funcSortAsc = false;

// Animated score ring
setTimeout(()=>{{
  const ring = document.getElementById('scoreRing');
  const num = document.getElementById('scoreNum');
  const target = {{scores["overall"]}};
  const circ = 2 * Math.PI * 54;
  ring.setAttribute('stroke-dasharray', (target/100*circ)+' '+circ);
  let cur = 0;
  const step = Math.max(1, Math.floor(target/40));
  const iv = setInterval(()=>{{
    cur = Math.min(cur + step, target);
    num.textContent = cur;
    if(cur >= target) clearInterval(iv);
  }}, 30);
}}, 300);

// Scroll to top button
window.addEventListener('scroll', ()=>{{
  document.getElementById('scrollTop').classList.toggle('visible', window.scrollY > 400);
}});

// Active sidebar link
const sections = document.querySelectorAll('section[id], header[id]');
window.addEventListener('scroll', ()=>{{
  let current = '';
  sections.forEach(s=>{{ if(s.getBoundingClientRect().top < 200) current = s.id; }});
  document.querySelectorAll('.sidebar nav a').forEach(a=>{{
    a.classList.toggle('active', a.getAttribute('href') === '#'+current);
  }});
  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
}});

// Lang filters
const filtersEl = document.getElementById('langFilters');
const langSet = new Set(FILES.map(f=>f.lang));
[...langSet].sort().forEach(l=>{{
  const pill = document.createElement('span');
  pill.className = 'filter-pill';
  pill.textContent = l;
  pill.onclick = ()=>{{
    document.querySelectorAll('.filter-pill').forEach(p=>p.classList.remove('active'));
    if(currentLang === l){{ currentLang=null; }} else {{ currentLang=l; pill.classList.add('active'); }}
    renderFiles();
  }};
  filtersEl.appendChild(pill);
}});

function renderFiles(){{
  const q = (document.getElementById('fileSearch')?.value||'').toLowerCase();
  const rows = FILES.filter(f=>{{
    if(currentLang && f.lang !== currentLang) return false;
    if(q && !f.path.toLowerCase().includes(q)) return false;
    return true;
  }}}}).sort((a,b)=>{{
    const keys = ['path','lang','total','code','comment','complexity','maintainability','size'];
    const va = a[keys[sortCol]], vb = b[keys[sortCol]];
    if(typeof va==='string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va-vb : vb-va;
  }});
  document.getElementById('filesBody').innerHTML = rows.map(f=>`<tr>
    <td style="font-family:monospace;font-size:0.82em">${{escHtml(f.path)}}</td>
    <td><span style="color:${{f.color}}">${{escHtml(f.lang)}}</span></td>
    <td>${{f.total}}</td><td>${{f.code}}</td><td>${{f.comment}}</td>
    <td style="color:${{f.complexity>15?'var(--accent)':f.complexity>8?'var(--warning)':'var(--green)'}}">${{f.complexity}}</td>
    <td style="color:${{f.maintainability<50?'var(--accent)':f.maintainability<70?'var(--warning)':'var(--green)'}}">${{f.maintainability}}</td>
    <td>${{fmtSize(f.size)}}</td>
  </tr>`).join('');
}}

function renderFuncs(){{
  const rows = [...FUNCS].sort((a,b)=>{{
    const keys=['name','file','complexity','cognitive','params','nesting','loc'];
    const va=a[keys[funcSortCol]], vb=b[keys[funcSortCol]];
    if(typeof va==='string') return funcSortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return funcSortAsc ? va-vb : vb-va;
  }});
  document.getElementById('funcsBody').innerHTML = rows.map(f=>`<tr>
    <td style="font-family:monospace;font-weight:600">${{escHtml(f.name)}}</td>
    <td style="font-size:0.82em;color:var(--text2)">${{escHtml(f.file)}}</td>
    <td style="color:${{f.complexity>15?'var(--accent)':f.complexity>8?'var(--warning)':'var(--green)'}}">${{f.complexity}}</td>
    <td style="color:${{f.cognitive>20?'var(--accent)':f.cognitive>10?'var(--warning)':'var(--text2)'}}">${{f.cognitive}}</td>
    <td>${{f.params}}</td>
    <td style="color:${{f.nesting>4?'var(--accent)':'var(--text2)'}}">${{f.nesting}}</td>
    <td>${{f.loc}}</td>
  </tr>`).join('');
}}

function escHtml(s){{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}
function fmtSize(b){{ return b<1024?b+'B':b<1048576?(b/1024).toFixed(1)+'KB':(b/1048576).toFixed(1)+'MB'; }}
function sortTable(col){{ if(sortCol===col) sortAsc=!sortAsc; else{{ sortCol=col; sortAsc=col===0; }} renderFiles(); }}
function sortFuncs(col){{ if(funcSortCol===col) funcSortAsc=!funcSortAsc; else{{ funcSortCol=col; funcSortAsc=false; }} renderFuncs(); }}
function toggleSection(el){{ el.parentElement.classList.toggle('collapsed'); }}

function toggleTheme(){{
  const light = {{ '--bg':'#f8f9fc','--surface':'#ffffff','--surface2':'#f0f1f5','--surface3':'#e5e6eb',
    '--glass':'rgba(0,0,0,0.02)','--glass-border':'rgba(0,0,0,0.08)',
    '--text':'#1a1a2e','--text2':'#5a5a7a','--text3':'#8888aa' }};
  const dark = {{ '--bg':'#0a0a1a','--surface':'#12122a','--surface2':'#1a1a3e','--surface3':'#222250',
    '--glass':'rgba(127,90,240,0.06)','--glass-border':'rgba(127,90,240,0.12)',
    '--text':'#eeeef5','--text2':'#8888aa','--text3':'#5a5a7a' }};
  const isLight = document.body.style.getPropertyValue('--bg') === light['--bg'];
  Object.entries(isLight ? dark : light).forEach(([k,v])=>document.body.style.setProperty(k,v));
  document.querySelector('.theme-toggle').textContent = isLight ? '🌙' : '☀️';
}}

// Tree toggles
document.querySelectorAll('.tree-toggle').forEach(el=>{{
  el.addEventListener('click', ()=>el.parentElement.classList.toggle('tree-collapsed'));
}});

renderFiles();
renderFuncs();
</script>
</body></html>'''


# ── SVG Chart Builders ──────────────────────────────────────────────────────

def build_pie_svg(languages, cx=120, cy=120, r=90):
    if not languages:
        return '<div style="color:var(--text2)">No languages detected</div>'
    total = sum(languages.values()) or 1
    slices = []
    angle = 0
    for lang, count in sorted(languages.items(), key=lambda x: -x[1]):
        pct = count / total
        sweep = pct * 360
        color = get_lang_color(lang)
        x1 = cx + r * _cosd(angle)
        y1 = cy + r * _sind(angle)
        x2 = cx + r * _cosd(angle + sweep)
        y2 = cy + r * _sind(angle + sweep)
        large = 1 if sweep > 180 else 0
        slices.append(f'<path d="M{cx},{cy} L{x1},{y1} A{r},{r} 0 {large},1 {x2},{y2} Z" fill="{color}" opacity="0.85"><title>{esc(lang)}: {count:,} ({pct:.1f}%)</title></path>')
        angle += sweep
    legend_items = []
    for i, (l, c) in enumerate(sorted(languages.items(), key=lambda x: -x[1])[:12]):
        pct = c / total * 100
        legend_items.append(
            f'<rect x="260" y="{i*24}" width="14" height="14" rx="3" fill="{get_lang_color(l)}"/>'
            f'<text x="280" y="{i*24+11}" fill="var(--text2)" font-size="11">{esc(l)}</text>'
            f'<text x="400" y="{i*24+11}" fill="var(--text3)" font-size="11" text-anchor="end">{c:,} ({pct:.1f}%)</text>'
        )
    legend = ''.join(legend_items)
    h = max(len(languages) * 24 + 20, 260)
    return f'<svg viewBox="0 0 450 {h}" width="100%" height="{h}"><text x="120" y="20" fill="var(--text)" font-size="13" font-weight="600" text-anchor="middle">Language Distribution</text>{"".join(slices)}{legend}</svg>'


def build_bar_svg(top_files):
    if not top_files:
        return ''
    max_val = max(f['lines']['total'] for f in top_files) or 1
    n = len(top_files)
    bw = max(30, min(50, 700 // n))
    w = n * bw + 30
    bars = ''
    for i, f in enumerate(top_files):
        h = (f['lines']['total'] / max_val) * 260
        y = 280 - h
        name = f['path'].split('/')[-1][:18]
        bars += f'''<rect x="{i*bw+20}" y="{y}" width="{bw-6}" height="{h}" rx="4" fill="{f['color']}" opacity="0.8">
      <title>{esc(f['path'])}: {f['lines']['total']} lines</title></rect>
      <text x="{i*bw+bw/2+17}" y="{y-6}" fill="var(--text2)" font-size="10" text-anchor="middle">{f['lines']['total']}</text>
      <text x="{i*bw+bw/2+17}" y="296" fill="var(--text3)" font-size="8" text-anchor="middle" transform="rotate(-40 {i*bw+bw/2+17} 296)">{esc(name)}</text>'''
    return f'<svg viewBox="0 0 {w} 340" width="100%" height="340">{bars}</svg>'


def build_complexity_svg(files):
    if not files:
        return ''
    max_val = max(f['complexity'] for f in files) or 1
    n = len(files)
    bw = max(40, min(55, 700 // n))
    w = n * bw + 30
    bars = ''
    for i, f in enumerate(files):
        h = (f['complexity'] / max_val) * 200
        y = 220 - h
        color = '#e53170' if f['complexity'] > 15 else '#ff8906' if f['complexity'] > 8 else '#2cb67d'
        name = f['path'].split('/')[-1][:16]
        bars += f'''<rect x="{i*bw+20}" y="{y}" width="{bw-6}" height="{h}" rx="4" fill="{color}" opacity="0.8">
      <title>{esc(f['path'])}: complexity {f['complexity']}</title></rect>
      <text x="{i*bw+bw/2+17}" y="{y-6}" fill="var(--text2)" font-size="10" text-anchor="middle">{f['complexity']}</text>
      <text x="{i*bw+bw/2+17}" y="236" fill="var(--text3)" font-size="8" text-anchor="middle" transform="rotate(-40 {i*bw+bw/2+17} 236)">{esc(name)}</text>'''
    return f'<svg viewBox="0 0 {w} 280" width="100%" height="280">{bars}</svg>'


def build_size_dist_svg(dist):
    if not dist:
        return '<div style="color:var(--text2)">No data</div>'
    order = {'tiny': 0, 'small': 1, 'medium': 2, 'large': 3, 'huge': 4}
    labels = {'tiny': '<1KB', 'small': '1-5KB', 'medium': '5-20KB', 'large': '20-100KB', 'huge': '>100KB'}
    sorted_dist = sorted(dist.items(), key=lambda x: order.get(x[0], 0))
    max_val = max(v for _, v in sorted_dist) or 1
    colors = ['#2cb67d', '#7f5af0', '#38bdf8', '#ff8906', '#e53170']
    bars = ''
    n = len(sorted_dist)
    bw = max(60, min(120, 600 // n))
    for i, (key, count) in enumerate(sorted_dist):
        h = (count / max_val) * 180
        y = 200 - h
        bars += f'''<rect x="{i*bw+30}" y="{y}" width="{bw-12}" height="{h}" rx="6" fill="{colors[i % len(colors)]}" opacity="0.8"/>
      <text x="{i*bw+bw/2+24}" y="{y-6}" fill="var(--text2)" font-size="12" text-anchor="middle" font-weight="600">{count}</text>
      <text x="{i*bw+bw/2+24}" y="220" fill="var(--text2)" font-size="10" text-anchor="middle">{labels.get(key, key)}</text>'''
    w = n * bw + 60
    return f'<svg viewBox="0 0 {w} 240" width="100%" height="240">{bars}</svg>'


def build_complexity_histogram(dist):
    if not dist:
        return '<div style="color:var(--text2)">No data</div>'
    order = {'low': 0, 'moderate': 1, 'high': 2, 'very-high': 3, 'extreme': 4}
    labels = {'low': 'Low (1-5)', 'moderate': 'Moderate (6-10)', 'high': 'High (11-20)', 'very-high': 'Very High (21-40)', 'extreme': 'Extreme (40+)'}
    colors = {'low': '#2cb67d', 'moderate': '#38bdf8', 'high': '#ff8906', 'very-high': '#e53170', 'extreme': '#ff0055'}
    sorted_dist = sorted(dist.items(), key=lambda x: order.get(x[0], 0))
    max_val = max(v for _, v in sorted_dist) or 1
    bars = ''
    n = len(sorted_dist)
    bw = max(80, min(140, 700 // n))
    for i, (key, count) in enumerate(sorted_dist):
        h = (count / max_val) * 180
        y = 200 - h
        c = colors.get(key, '#7f5af0')
        bars += f'''<rect x="{i*bw+30}" y="{y}" width="{bw-14}" height="{h}" rx="6" fill="{c}" opacity="0.8"/>
      <text x="{i*bw+bw/2+23}" y="{y-6}" fill="var(--text2)" font-size="12" text-anchor="middle" font-weight="600">{count}</text>
      <text x="{i*bw+bw/2+23}" y="220" fill="var(--text2)" font-size="9" text-anchor="middle">{labels.get(key, key)}</text>'''
    w = n * bw + 60
    return f'<svg viewBox="0 0 {w} 240" width="100%" height="240">{bars}</svg>'


def build_severity_donut(by_severity):
    if not by_severity:
        return ''
    colors = {'critical': '#e53170', 'high': '#ff8906', 'medium': '#7f5af0', 'low': '#a7a9be'}
    cx, cy, r = 80, 80, 60
    total = sum(by_severity.values()) or 1
    slices = []
    angle = 0
    for sev in ('critical', 'high', 'medium', 'low'):
        count = by_severity.get(sev, 0)
        if count == 0:
            continue
        sweep = (count / total) * 360
        c = colors.get(sev, '#999')
        x1 = cx + r * _cosd(angle)
        y1 = cy + r * _sind(angle)
        x2 = cx + r * _cosd(angle + sweep)
        y2 = cy + r * _sind(angle + sweep)
        large = 1 if sweep > 180 else 0
        slices.append(f'<path d="M{cx},{cy} L{x1},{y1} A{r},{r} 0 {large},1 {x2},{y2} Z" fill="{c}" opacity="0.8"/>')
        angle += sweep
    legend = ''.join(
        f'<circle cx="170" cy="{i*22+10}" r="5" fill="{colors.get(s,"#999")}"/>'
        f'<text x="182" y="{i*22+14}" fill="var(--text2)" font-size="11">{esc(s.title())}: {by_severity.get(s,0)}</text>'
        for i, s in enumerate(('critical', 'high', 'medium', 'low'))
    )
    return f'<svg viewBox="0 0 300 120" width="300" height="120">{"".join(slices)}{legend}</svg>'


def build_heatmap_svg(heatmap):
    from datetime import date, timedelta
    weeks = 52
    days = 7
    cs = 13
    gap = 2
    max_count = max(heatmap.values()) if heatmap else 1
    if max_count == 0:
        max_count = 1
    rects = ''
    for w in range(weeks):
        for d in range(days):
            try:
                dt = date.today() - timedelta(days=(weeks - 1 - w) * 7 + (6 - d))
                ds = dt.isoformat()
                count = heatmap.get(ds, 0)
            except (ValueError, OverflowError):
                count = 0
            if count > 0:
                intensity = min(count / max_count, 1)
                color = '#2cb67d'
                opacity = 0.2 + intensity * 0.8
            else:
                color = 'var(--surface3)'
                opacity = 0.4
            x = w * (cs + gap) + 45
            y = d * (cs + gap) + 35
            rects += f'<rect x="{x}" y="{y}" width="{cs}" height="{cs}" rx="2" fill="{color}" opacity="{opacity:.2f}"><title>{ds}: {count} commits</title></rect>'
    width = weeks * (cs + gap) + 60
    return f'<svg viewBox="0 0 {width} 150" width="100%" height="150">{rects}</svg>'


def build_contributors_svg(authors):
    if not authors:
        return ''
    max_val = authors[0]['commits'] if authors else 1
    max_val = max(max_val, 1)
    colors = ['#7f5af0', '#2cb67d', '#38bdf8', '#ff8906', '#e53170', '#14b8a6', '#a78bfa', '#f472b6', '#fbbf24', '#34d399', '#818cf8', '#fb923c']
    bars = ''
    for i, a in enumerate(authors[:12]):
        h = (a['commits'] / max_val) * 140
        y = 160 - h
        name = a['name'][:15]
        bars += f'''<rect x="{i*52+20}" y="{y}" width="38" height="{h}" rx="4" fill="{colors[i % len(colors)]}" opacity="0.8">
      <title>{esc(a["name"])}: {a["commits"]} commits</title></rect>
      <text x="{i*52+39}" y="{y-6}" fill="var(--text2)" font-size="10" text-anchor="middle">{a["commits"]}</text>
      <text x="{i*52+39}" y="178" fill="var(--text3)" font-size="7" text-anchor="middle" transform="rotate(-45 {i*52+39} 178)">{esc(name)}</text>'''
    w = len(authors[:12]) * 52 + 40
    return f'<svg viewBox="0 0 {w} 220" width="100%" height="220">{bars}</svg>'


def build_timeline_svg(timeline):
    if not timeline:
        return ''
    max_val = max(t['count'] for t in timeline) or 1
    n = len(timeline)
    bw = max(30, min(50, 700 // n))
    w = n * bw + 30
    bars = ''
    for i, t in enumerate(timeline):
        h = (t['count'] / max_val) * 140
        y = 160 - h
        bars += f'''<rect x="{i*bw+20}" y="{y}" width="{bw-6}" height="{h}" rx="3" fill="var(--primary)" opacity="0.7">
      <title>{t["month"]}: {t["count"]} commits</title></rect>
      <text x="{i*bw+bw/2+17}" y="{y-5}" fill="var(--text2)" font-size="9" text-anchor="middle">{t["count"]}</text>
      <text x="{i*bw+bw/2+17}" y="176" fill="var(--text3)" font-size="7" text-anchor="middle" transform="rotate(-45 {i*bw+bw/2+17} 176)">{t["month"]}</text>'''
    return f'<svg viewBox="0 0 {w} 210" width="100%" height="210">{bars}</svg>'


def build_import_graph_svg(import_graph):
    if not import_graph:
        return '<div style="color:var(--text2)">No import data</div>'
    sorted_modules = sorted(import_graph.keys(), key=lambda x: -len(import_graph[x]))[:12]
    n = len(sorted_modules)
    if n < 2:
        return '<div style="color:var(--text2)">Not enough import data</div>'
    r = min(120, n * 20)
    cx, cy = 200, 160
    nodes = {}
    for i, mod in enumerate(sorted_modules):
        angle = (2 * math.pi * i) / n - math.pi / 2
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        short = mod.split('.')[-1][:15]
        nodes[mod] = {'x': x, 'y': y, 'label': short}
    edges = []
    for mod in sorted_modules:
        for dep in import_graph[mod]:
            if dep in nodes and mod != dep:
                edges.append((mod, dep))
    edge_paths = ''
    for src, dst in edges[:30]:
        s, d = nodes[src], nodes[dst]
        edge_paths += f'<line x1="{s["x"]}" y1="{s["y"]}" x2="{d["x"]}" y2="{d["y"]}" stroke="rgba(127,90,240,0.2)" stroke-width="1"/>'
    node_circles = ''
    for mod, data in nodes.items():
        size = 8 + len(import_graph.get(mod, set())) * 1.5
        node_circles += f'''<circle cx="{data["x"]}" cy="{data["y"]}" r="{size}" fill="var(--primary)" opacity="0.7">
      <title>{esc(mod)} ({len(import_graph.get(mod, set()))} imports)</title></circle>
      <text x="{data["x"]}" y="{data["y"]+size+12}" fill="var(--text2)" font-size="9" text-anchor="middle">{esc(data["label"])}</text>'''
    w, h = 400, 320
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{edge_paths}{node_circles}</svg>'


# ── Section Builders ────────────────────────────────────────────────────────

def build_security_section(issues, sec_sum):
    if not issues:
        return '<div style="color:var(--green);font-size:1.1em;padding:16px">✅ No security issues detected!</div>'
    sev_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    items = []
    for issue in sorted(issues, key=lambda x: sev_order.get(x['severity'], 4))[:50]:
        file_short = issue['file'].split('/')[-1] if issue.get('file') else 'unknown'
        items.append(f'''<div class="sec-item">
      <div><span class="severity-badge {esc(issue['severity'])}">{esc(issue['severity'])}</span></div>
      <div style="flex:1">
        <div style="font-weight:600">{esc(issue['name'])}</div>
        <div style="font-size:0.82em;color:var(--text2)">{esc(file_short)} — line {issue.get('line',0)} · {issue.get('count',1)} occurrence(s)</div>
        {'<div style="font-size:0.8em;color:var(--text3);margin-top:4px">' + esc(issue.get('remediation', '')) + '</div>' if issue.get('remediation') else ''}
      </div>
    </div>''')
    return f'''
    <div class="grid-2 mb-2">
      <div>{build_severity_donut(sec_sum.get('by_severity', {}))}</div>
      <div>
        <div class="chart-title">Summary</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
          <div class="stat-card" style="padding:12px"><div class="label">Critical</div><div class="value" style="color:var(--accent)">{sec_sum["by_severity"].get("critical",0)}</div></div>
          <div class="stat-card" style="padding:12px"><div class="label">High</div><div class="value" style="color:var(--warning)">{sec_sum["by_severity"].get("high",0)}</div></div>
          <div class="stat-card" style="padding:12px"><div class="label">Medium</div><div class="value" style="color:var(--primary-light)">{sec_sum["by_severity"].get("medium",0)}</div></div>
          <div class="stat-card" style="padding:12px"><div class="label">Low</div><div class="value">{sec_sum["by_severity"].get("low",0)}</div></div>
        </div>
      </div>
    </div>
    <div class="chart-title">Findings</div>
    {''.join(items)}'''


def build_recommendations_section(recs):
    items = []
    for r in recs:
        items.append(f'''<div class="rec">
      <div class="icon">{r['icon']}</div>
      <div class="content">
        <div class="category">{esc(r['category'])}
          <span class="priority {r.get('priority', 'low')}">{esc(r.get('priority', 'low'))}</span>
        </div>
        <div class="text-sm" style="margin-top:4px">{esc(r['message'])}</div>
      </div>
    </div>''')
    return ''.join(items)


def build_deps_section(analysis):
    deps = analysis['dependencies']
    if not deps:
        return f'<div style="color:var(--text2)">No dependencies detected ({esc(analysis["package_manager"] or "no package file")} found)</div>'
    pm = analysis['package_manager'] or 'unknown'
    rows = ''
    for d in deps[:60]:
        section = d.get('section', '')
        rows += f'<tr><td style="font-family:monospace">{esc(d["name"])}</td><td>{esc(d.get("spec","*"))}</td><td>{esc(d.get("operator",""))}</td><td>{esc(section)}</td></tr>'
    extras = ''
    if analysis.get('circular_deps'):
        cycles = analysis['circular_deps'][:10]
        cycle_html = ''.join(
            f'<div style="font-size:0.82em;color:var(--text2);margin:4px 0">🔄 {" → ".join(c)}</div>'
            for c in cycles
        )
        extras += f'<div style="margin-top:16px"><div class="chart-title">⚠️ Circular Dependencies ({len(analysis["circular_deps"])})</div>{cycle_html}</div>'
    return f'''
    <div style="color:var(--text2);margin-bottom:12px">Package manager: <strong style="color:var(--text)">{esc(pm)}</strong> · {len(deps)} packages</div>
    <div class="table-wrap"><table>
      <thead><tr><th>Package</th><th>Version</th><th>Operator</th><th>Section</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>{extras}'''


def build_tree_html(tree, indent=0):
    lines = []
    sorted_keys = sorted(tree.keys(), key=lambda k: (not isinstance(tree[k], dict), k))
    for key in sorted_keys:
        val = tree[key]
        prefix = '<span class="indent"></span>' * indent
        if isinstance(val, dict) and any(isinstance(v, dict) for v in val.values()):
            lines.append(f'<span class="tree-toggle"><span class="indent"></span>{prefix}📁 <span class="dir">{esc(key)}/</span></span>')
            lines.append(f'<div class="tree-children">{build_tree_html(val, indent + 1)}</div>')
        elif isinstance(val, dict) and 'lines' in val:
            color = val.get('color', 'var(--text2)')
            lines.append(f'{prefix}📄 <span class="file" style="color:{color}">{esc(key)}</span> <span class="size">({val.get("lines",0)} lines)</span>')
        else:
            lines.append(f'{prefix}📄 <span class="file">{esc(key)}</span>')
    return '<br>'.join(lines)


def build_git_section(git_data):
    if not git_data:
        return '<div style="color:var(--text2)">No git repository found</div>'
    authors = git_data.get('authors', [])[:10]
    author_rows = ''.join(
        f'<tr><td>{esc(a["name"])}</td><td>{a["commits"]}</td><td>{a["commits"]/max(git_data["total_commits"],1)*100:.1f}%</td></tr>'
        for a in authors
    )
    active = git_data.get('active_files', [])[:10]
    file_rows = ''.join(
        f'<tr><td style="font-family:monospace;font-size:0.82em">{esc(f["file"])}</td><td>{f["commits"]}</td></tr>'
        for f in active
    )
    hotspots = git_data.get('hotspots', [])[:10]
    hotspot_rows = ''.join(
        f'<tr><td style="font-family:monospace;font-size:0.82em">{esc(h["file"])}</td><td>{h["churn"]:,}</td></tr>'
        for h in hotspots
    )
    dr = git_data.get('date_range', {})
    br = git_data.get('branches', {})
    bus = git_data.get('bus_factor', {})
    churn = git_data.get('code_churn', {})
    merges = git_data.get('merges', {})
    uncommitted = git_data.get('uncommitted', {})

    uncommitted_html = ''
    if uncommitted and sum(uncommitted.values()) > 0:
        uncommitted_html = f'''<div class="stat-card" style="padding:12px;border-color:rgba(255,137,6,0.3)">
          <div class="label" style="color:var(--warning)">Uncommitted Changes</div>
          <div class="value" style="font-size:1em;color:var(--warning)">{sum(uncommitted.values())}</div>
          <div class="sub">{uncommitted.get("modified",0)} modified · {uncommitted.get("untracked",0)} untracked</div>
        </div>'''

    return f'''
    <div class="stats mb-2">
      <div class="stat-card"><div class="label">Total Commits</div><div class="value">{git_data.get("total_commits",0):,}</div></div>
      <div class="stat-card"><div class="label">Contributors</div><div class="value">{len(git_data.get("authors",[]))}</div></div>
      <div class="stat-card"><div class="label">Active Since</div><div class="value" style="font-size:1em">{esc(dr.get("first","?"))}</div></div>
      <div class="stat-card"><div class="label">Branch</div><div class="value" style="font-size:1em">{esc(br.get("current","?"))}</div></div>
      <div class="stat-card"><div class="label">Bus Factor</div><div class="value" style="color:{"var(--accent)" if bus.get("factor",0)<=1 else "var(--green)"}">{bus.get("factor",0)}</div><div class="sub">{bus.get("coverage_pct",0)}% coverage by top devs</div></div>
      {uncommitted_html}
    </div>
    <div class="chart-title">Contribution Heatmap</div>
    <div class="chart-container">{build_heatmap_svg(git_data.get('heatmap', {}))}</div>
    <div class="chart-title">Top Contributors</div>
    <div class="chart-container">{build_contributors_svg(git_data.get('authors', []))}</div>
    {"<div class='chart-title'>Commit Timeline</div><div class='chart-container'>" + build_timeline_svg(git_data.get('commit_timeline', [])) + "</div>" if git_data.get('commit_timeline') else ""}
    <div class="grid-2 mt-3">
      <div>
        <div class="chart-title">Most Active Files</div>
        <div class="table-wrap"><table><thead><tr><th>File</th><th>Commits</th></tr></thead><tbody>{file_rows}</tbody></table></div>
      </div>
      <div>
        <div class="chart-title">Code Churn Hotspots</div>
        <div class="table-wrap"><table><thead><tr><th>File</th><th>Lines Changed</th></tr></thead><tbody>{hotspot_rows}</tbody></table></div>
      </div>
    </div>
    <div class="mt-3">
      <div class="chart-title">Commit Statistics</div>
      <div class="stats">
        <div class="stat-card" style="padding:12px"><div class="label">90-day Churn</div><div class="value" style="font-size:1.1em">{churn.get("added",0):,}+</div><div class="sub">{churn.get("removed",0):,}- net {churn.get("net",0):,}</div></div>
        <div class="stat-card" style="padding:12px"><div class="label">Merge Rate</div><div class="value" style="font-size:1.1em">{merges.get("merge_rate",0)}%</div><div class="sub">{merges.get("total_merges",0)} merge commits</div></div>
        <div class="stat-card" style="padding:12px"><div class="label">Tags</div><div class="value" style="font-size:1.1em">{len(git_data.get("tags",[]))}</div></div>
        <div class="stat-card" style="padding:12px"><div class="label">Avg Commit Size</div><div class="value" style="font-size:1.1em">{churn.get("avg_commit_size",0)}</div><div class="sub">lines changed</div></div>
      </div>
    </div>'''


def build_metrics_section(analysis):
    tl = analysis['total_lines']
    comment_pct = (tl['comment'] / tl['total'] * 100) if tl['total'] > 0 else 0
    blank_pct = (tl['blank'] / tl['total'] * 100) if tl['total'] > 0 else 0
    code_pct = (tl['code'] / tl['total'] * 100) if tl['total'] > 0 else 0
    func_count = len(analysis.get('functions', []))
    avg_func_loc = sum(f['line_count'] for f in analysis.get('functions', [])) / max(func_count, 1)
    deep_funcs = len([f for f in analysis.get('functions', []) if f.get('nesting_depth', 0) > 4])
    big_funcs = len([f for f in analysis.get('functions', []) if f['line_count'] > 50])
    many_args = len([f for f in analysis.get('functions', []) if f.get('param_count', 0) > 5])

    return f'''
    <div class="stats mb-2">
      <div class="stat-card"><div class="label">Code Lines</div><div class="value">{code_pct:.0f}%</div><div class="sub">{tl["code"]:,} lines</div></div>
      <div class="stat-card"><div class="label">Comments</div><div class="value">{comment_pct:.1f}%</div><div class="sub">{tl["comment"]:,} lines</div></div>
      <div class="stat-card"><div class="label">Blank Lines</div><div class="value">{blank_pct:.0f}%</div><div class="sub">{tl["blank"]:,} lines</div></div>
      <div class="stat-card"><div class="label">Avg Function Size</div><div class="value">{avg_func_loc:.0f}</div><div class="sub">lines per function</div></div>
    </div>
    <div class="stats">
      <div class="stat-card" style="padding:12px"><div class="label">Deep Nesting (&gt;4)</div><div class="value" style="color:{"var(--accent)" if deep_funcs>5 else "var(--text)"}">{deep_funcs}</div><div class="sub">functions with deep nesting</div></div>
      <div class="stat-card" style="padding:12px"><div class="label">Large Functions (&gt;50 loc)</div><div class="value" style="color:{"var(--warning)" if big_funcs>5 else "var(--text)"}">{big_funcs}</div></div>
      <div class="stat-card" style="padding:12px"><div class="label">Many Args (&gt;5)</div><div class="value" style="color:{"var(--warning)" if many_args>3 else "var(--text)"}">{many_args}</div></div>
      <div class="stat-card" style="padding:12px"><div class="label">Duplicates</div><div class="value">{len(analysis.get("duplicates",[]))}</div><div class="sub">code block duplicates</div></div>
    </div>'''


def build_tech_section(analysis):
    ts = analysis.get('tech_stack')
    if not ts:
        return ''
    categories = ['frameworks', 'databases', 'orm', 'containers', 'cicd', 'cloud', 'testing', 'linting', 'build_tools', 'package_managers']
    html = ''
    for cat in categories:
        items = ts.get(cat, [])
        if not items:
            continue
        cat_title = cat.replace('_', ' ').title()
        badges = ''.join(
            f'<span class="badge" title="{", ".join(i.get("evidence",[]))[:60]}">{esc(i["name"])} <small style="opacity:0.6">{i["confidence"]}</small></span>'
            for i in items[:15]
        )
        html += f'<div class="mt-2"><div class="chart-title">{esc(cat_title)}</div><div class="badges">{badges}</div></div>'
    return html


# ── Helpers ────────────────────────────────────────────────────────────────

def _cosd(deg):
    return math.cos(math.radians(deg))

def _sind(deg):
    return math.sin(math.radians(deg))


# ── Additional SVG Chart Builders ────────────────────────────────────────────

def build_radial_gauge_svg(value, max_value, label, color, size=150):
    """Build a radial gauge SVG."""
    r = size // 2 - 15
    cx = cy = size // 2
    pct = min(value / max(max_value, 1), 1)
    sweep = pct * 360
    x1 = cx + r * _cosd(-90)
    y1 = cy + r * _sind(-90)
    x2 = cx + r * _cosd(-90 + sweep)
    y2 = cy + r * _sind(-90 + sweep)
    large = 1 if sweep > 180 else 0
    svg = (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="12"/>'
        f'<path d="M{cx},{cy} L{x1},{y1} A{r},{r} 0 {large},1 {x2},{y2} Z" '
        f'fill="{color}" opacity="0.8"/>'
        f'<text x="{cx}" y="{cy - 5}" fill="var(--text)" font-size="{size//5}" font-weight="800" text-anchor="middle">{value}</text>'
        f'<text x="{cx}" y="{cy + size//8}" fill="var(--text2)" font-size="{size//10}" text-anchor="middle">{esc(label)}</text>'
        f'</svg>'
    )
    return svg


def build_sparkline_svg(values, width=200, height=40, color='var(--primary)'):
    """Build a sparkline SVG from a list of values."""
    if not values:
        return '<div style="color:var(--text3)">No data</div>'
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0
    range_val = max(max_val - min_val, 1)
    points = []
    n = len(values)
    for i, v in enumerate(values):
        x = i / max(n - 1, 1) * width
        y = height - ((v - min_val) / range_val * (height - 4)) - 2
        points.append(f'{x:.1f},{y:.1f}')
    polyline = ' '.join(points)
    area_points = f'0,{height} {polyline} {width},{height}'
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" preserveAspectRatio="none">'
        f'<polygon points="{area_points}" fill="{color}" opacity="0.15"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def build_treemap_svg(data, width=600, height=300):
    """Build a simple treemap SVG."""
    if not data:
        return ''
    total = sum(v for _, v in data)
    if total == 0:
        return ''
    colors = ['#7f5af0', '#2cb67d', '#38bdf8', '#ff8906', '#e53170', '#14b8a6',
              '#a78bfa', '#f472b6', '#fbbf24', '#34d399', '#818cf8', '#fb923c']
    rects = []
    x, y = 0, 0
    row_height = 0
    remaining_width = width
    for i, (name, value) in enumerate(sorted(data, key=lambda x: -x[1])):
        pct = value / total
        item_width = max(pct * width, 2)
        item_height = pct * height
        if x + item_width > width:
            x = 0
            y += row_height
            row_height = 0
            remaining_width = width
        if item_height > height - y:
            item_height = height - y
        if item_width > width - x:
            item_width = width - x
        c = colors[i % len(colors)]
        rects.append(
            f'<rect x="{x}" y="{y}" width="{item_width}" height="{item_height}" rx="3" fill="{c}" opacity="0.7">'
            f'<title>{esc(name)}: {value}</title></rect>'
        )
        if item_width > 30 and item_height > 12:
            label = name[:12]
            rects.append(
                f'<text x="{x + 4}" y="{y + 12}" fill="white" font-size="9" font-weight="600">{esc(label)}</text>'
            )
        x += item_width + 1
        row_height = max(row_height, item_height + 1)
        if y >= height:
            break
    return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">{"".join(rects)}</svg>'


def build_waffle_chart_svg(data, cols=20, cell_size=12, gap=2):
    """Build a waffle chart (proportional area chart)."""
    if not data:
        return ''
    total = sum(v for _, v in data)
    if total == 0:
        return ''
    colors = ['#7f5af0', '#2cb67d', '#38bdf8', '#ff8906', '#e53170', '#14b8a6']
    total_cells = cols * 5
    rects = []
    idx = 0
    for i, (name, value) in enumerate(data):
        cell_count = round(value / total * total_cells)
        c = colors[i % len(colors)]
        for j in range(cell_count):
            row = idx // cols
            col = idx % cols
            rx = col * (cell_size + gap)
            ry = row * (cell_size + gap)
            rects.append(
                f'<rect x="{rx}" y="{ry}" width="{cell_size}" height="{cell_size}" rx="2" fill="{c}" opacity="0.8">'
                f'<title>{esc(name)}: {value}</title></rect>'
            )
            idx += 1
    rows_needed = (idx + cols - 1) // cols
    w = cols * (cell_size + gap)
    h = rows_needed * (cell_size + gap)
    legend = ''.join(
        f'<rect x="{w + 20}" y="{i*20}" width="12" height="12" rx="2" fill="{colors[i % len(colors)]}"/>'
        f'<text x="{w + 38}" y="{i*20+10}" fill="var(--text2)" font-size="10">{esc(name)}</text>'
        for i, (name, _) in enumerate(data)
    )
    return f'<svg viewBox="0 0 {w + 150} {h}" width="100%" height="{h}">{"".join(rects)}{legend}</svg>'


def build_bullet_chart_svg(items, width=500, height=30):
    """Build a bullet chart for comparing values to targets."""
    if not items:
        return ''
    bars = ''
    max_val = max(max(v.get('value', 0), v.get('target', 100)) for v in items) or 1
    bar_height = max(height // max(len(items), 1) - 4, 8)
    for i, item in enumerate(items):
        y = i * (bar_height + 4)
        value = item.get('value', 0)
        target = item.get('target', 100)
        label = item.get('label', '')
        color = item.get('color', 'var(--primary)')
        target_width = (target / max_val) * width * 0.7
        value_width = (value / max_val) * width * 0.7
        bars += (
            f'<text x="0" y="{y + bar_height - 1}" fill="var(--text2)" font-size="10">{esc(label)}</text>'
            f'<rect x="60" y="{y}" width="{target_width}" height="{bar_height//2}" rx="2" fill="var(--surface3)"/>'
            f'<rect x="60" y="{y}" width="{value_width}" height="{bar_height}" rx="2" fill="{color}" opacity="0.7"/>'
        )
    total_h = len(items) * (bar_height + 4)
    return f'<svg viewBox="0 0 {width} {total_h}" width="100%" height="{total_h}">{bars}</svg>'


# ── Additional Report Section Builders ───────────────────────────────────────

def build_quality_heatmap(quality_issues):
    """Build a heatmap showing quality issues by file."""
    if not quality_issues:
        return '<div style="color:var(--text2)">No quality issues found!</div>'
    by_file = Counter()
    for qi in quality_issues:
        by_file[qi.get('file', 'unknown')] += 1
    top = by_file.most_common(15)
    max_count = top[0][1] if top else 1
    bars = ''
    for i, (f, count) in enumerate(top):
        fname = f.split('/')[-1][:25]
        w = (count / max_count) * 300
        color = '#e53170' if count > 10 else '#ff8906' if count > 5 else '#7f5af0'
        bars += (
            f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0">'
            f'<span style="width:200px;font-size:0.82em;font-family:monospace;color:var(--text2);'
            f'text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{esc(fname)}</span>'
            f'<div style="flex:1;height:20px;background:var(--surface2);border-radius:4px;overflow:hidden">'
            f'<div style="width:{w}px;height:100%;background:{color};opacity:0.7;border-radius:4px"></div>'
            f'</div>'
            f'<span style="font-size:0.82em;color:var(--text3);min-width:30px">{count}</span>'
            f'</div>'
        )
    return f'<div style="margin:12px 0">{bars}</div>'


def build_todos_section(todos):
    """Build the TODOs/FIXMEs section."""
    if not todos:
        return '<div style="color:var(--text2)">No TODOs found!</div>'
    by_tag = Counter(t['tag'] for t in todos)
    tag_badges = ''.join(
        f'<span class="severity-badge {tag.lower()}" style="margin-right:6px">{esc(tag)}: {by_tag[tag]}</span>'
        for tag in sorted(by_tag.keys())
    )
    items = ''
    for t in todos[:30]:
        tag_color = {
            'TODO': 'var(--warning)', 'FIXME': 'var(--accent)', 'HACK': 'var(--primary-light)',
            'XXX': 'var(--text2)', 'NOTE': 'var(--teal)', 'BUG': 'var(--accent)',
        }
        color = tag_color.get(t['tag'], 'var(--text2)')
        text = esc(t.get('text', '')[:100])
        items += (
            f'<div style="display:flex;gap:10px;padding:8px 12px;background:var(--surface2);'
            f'border-radius:var(--radius-xs);margin-bottom:4px;border-left:3px solid {color}">'
            f'<span style="font-size:0.75em;font-weight:700;color:{color};min-width:50px">{esc(t["tag"])}</span>'
            f'<span style="font-size:0.85em;color:var(--text2)">Line {t["line"]}</span>'
            f'<span style="font-size:0.85em;flex:1">{text}</span>'
            f'</div>'
        )
    return f'<div class="badges mb-2">{tag_badges}</div>{items}'


def build_duplication_section(duplicates):
    """Build the code duplication section."""
    if not duplicates:
        return '<div style="color:var(--green);font-size:1em;padding:12px">No significant code duplication detected!</div>'
    items = ''
    for d in duplicates[:20]:
        files = d.get('files', [])
        sim = d.get('similarity', 0)
        dup_type = d.get('type', 'unknown')
        icon = '🔴' if dup_type == 'exact' else '🟠'
        file_list = ', '.join(
            f'<span style="font-family:monospace;font-size:0.82em;color:var(--text2)">{esc(f.split("/")[-1])}</span>'
            for f in files
        )
        items += (
            f'<div style="padding:10px;background:var(--surface2);border-radius:var(--radius-xs);margin-bottom:6px">'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span>{icon}</span>'
            f'<span style="font-size:0.85em">{file_list}</span>'
            f'<span style="margin-left:auto;font-size:0.82em;color:var(--text3)">{sim*100:.0f}% similar</span>'
            f'</div></div>'
        )
    return f'<div style="margin-top:12px">{items}</div>'


def build_import_details_section(import_details):
    """Build detailed import analysis section."""
    if not import_details:
        return '<div style="color:var(--text2)">No import data available</div>'
    sections = ''
    for lang, details in import_details.items():
        stdlib = details.get('stdlib', [])
        third_party = details.get('third_party', [])
        local = details.get('local', [])
        total = len(stdlib) + len(third_party) + len(local)
        if total == 0:
            continue
        stdlib_pct = len(stdlib) / total * 100
        third_pct = len(third_party) / total * 100
        local_pct = len(local) / total * 100
        sections += (
            f'<div style="margin-bottom:16px">'
            f'<div style="font-weight:600;margin-bottom:6px">{esc(lang)}</div>'
            f'<div style="display:flex;gap:4px;height:20px;border-radius:4px;overflow:hidden;margin-bottom:4px">'
            f'<div style="width:{stdlib_pct}%;background:var(--green);opacity:0.7" title="Stdlib: {stdlib_pct:.0f}%"></div>'
            f'<div style="width:{third_pct}%;background:var(--warning);opacity="0.7" title="Third-party: {third_pct:.0f}%"></div>'
            f'<div style="width:{local_pct}%;background:var(--primary);opacity="0.7" title="Local: {local_pct:.0f}%"></div>'
            f'</div>'
            f'<div style="display:flex;gap:12px;font-size:0.8em;color:var(--text3)">'
            f'<span>Stdlib: {len(stdlib)}</span>'
            f'<span>Third-party: {len(third_party)}</span>'
            f'<span>Local: {len(local)}</span>'
            f'</div></div>'
        )
    return sections


def build_functions_detail(functions, max_display=30):
    """Build detailed function metrics section."""
    if not functions:
        return '<div style="color:var(--text2)">No functions detected</div>'
    sorted_funcs = sorted(functions, key=lambda x: x.get('complexity', 0), reverse=True)

    def cc_color(c):
        return '#e53170' if c > 15 else '#ff8906' if c > 8 else '#2cb67d'

    def cog_color(c):
        return '#e53170' if c > 20 else '#ff8906' if c > 10 else 'var(--text2)'

    items = ''
    for f in sorted_funcs[:max_display]:
        name = f.get('name', 'unknown')
        fname = f.get('file', '').split('/')[-1] or ''
        cc = f.get('complexity', 0)
        cog = f.get('cognitive_complexity', 0)
        params = f.get('param_count', 0)
        nesting = f.get('nesting_depth', 0)
        loc = f.get('line_count', 0)
        nest_color = 'var(--accent)' if nesting > 4 else 'var(--text2)'
        items += (
            f'<tr>'
            f'<td style="font-family:monospace;font-weight:600">{esc(name)}</td>'
            f'<td style="font-size:0.82em;color:var(--text3)">{esc(fname)}</td>'
            f'<td style="color:{cc_color(cc)};font-weight:700">{cc}</td>'
            f'<td style="color:{cog_color(cog)}">{cog}</td>'
            f'<td>{params}</td>'
            f'<td style="color:{nest_color}">{nesting}</td>'
            f'<td>{loc}</td>'
            f'</tr>'
        )
    return (
        f'<div class="table-wrap"><table>'
        f'<thead><tr><th>Function</th><th>File</th><th>CC</th><th>Cog</th><th>Params</th><th>Nest</th><th>Lines</th></tr></thead>'
        f'<tbody>{items}</tbody>'
        f'</table></div>'
    )


def build_inline_breadcrumb(path_parts):
    """Build a breadcrumb trail for file paths."""
    crumbs = []
    for i, part in enumerate(path_parts):
        if i < len(path_parts) - 1:
            crumbs.append(f'<span style="color:var(--text3)">{esc(part)}/</span>')
        else:
            crumbs.append(f'<span style="color:var(--text);font-weight:600">{esc(part)}</span>')
    return ' <span style="color:var(--text3)">›</span> '.join(crumbs)


def build_progress_ring_svg(value, max_val, label, color, size=80):
    """Build a small circular progress ring."""
    r = size // 2 - 8
    cx = cy = size // 2
    pct = min(value / max(max_val, 1), 1)
    circ = 2 * 3.14159 * r
    dash = pct * circ
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--surface3)" stroke-width="6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="6" '
        f'stroke-dasharray="{dash} {circ}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy + 3}" fill="var(--text)" font-size="{size//5}" font-weight="800" text-anchor="middle">{value}</text>'
        f'</svg>'
    )


def build_stacked_bar_svg(data, width=500, height=24, colors=None):
    """Build a horizontal stacked bar chart."""
    if not data:
        return ''
    if colors is None:
        colors = ['#7f5af0', '#2cb67d', '#38bdf8', '#ff8906', '#e53170', '#14b8a6']
    total = sum(v for _, v in data)
    if total == 0:
        return ''
    rects = ''
    x = 0
    for i, (name, value) in enumerate(data):
        w = (value / total) * width
        c = colors[i % len(colors)]
        rects += (
            f'<rect x="{x}" y="0" width="{w}" height="{height}" rx="3" fill="{c}" opacity="0.8">'
            f'<title>{esc(name)}: {value} ({value/total*100:.1f}%)</title></rect>'
        )
        if w > 25:
            rects += f'<text x="{x + w/2}" y="{height//2 + 4}" fill="white" font-size="9" text-anchor="middle">{esc(name)}</text>'
        x += w
    return f'<svg viewBox="0 0 {width} {height + 20}" width="100%" height="{height + 20}">{rects}</svg>'


def build_dot_matrix_svg(counts, cols=52, cell_size=11, gap=2, label='Activity'):
    """Build a dot matrix visualization."""
    if not counts:
        return ''
    values = list(counts.values())
    max_val = max(values) if values else 1
    rects = ''
    for i, (key, val) in enumerate(counts.items()):
        row = i // cols
        col = i % cols
        x = col * (cell_size + gap)
        y = row * (cell_size + gap)
        intensity = val / max(max_val, 1)
        if intensity > 0:
            c = '#2cb67d'
            opacity = 0.2 + intensity * 0.8
        else:
            c = 'var(--surface3)'
            opacity = 0.4
        rects += (
            f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" fill="{c}" opacity="{opacity:.2f}">'
            f'<title>{esc(key)}: {val}</title></rect>'
        )
    rows_needed = (len(counts) + cols - 1) // cols
    w = cols * (cell_size + gap)
    h = rows_needed * (cell_size + gap)
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{rects}</svg>'


def build_comparison_table(metrics_a, metrics_b, label_a, label_b):
    """Build a comparison table between two sets of metrics."""
    rows = ''
    for key, label in metrics_a.items():
        val_a = metrics_a[key]
        val_b = metrics_b.get(key, 0)
        if isinstance(val_a, (int, float)):
            diff = val_b - val_a
            diff_str = f'+{diff}' if diff > 0 else str(diff)
            color = '#2cb67d' if diff > 0 else '#e53170' if diff < 0 else 'var(--text2)'
            rows += (
                f'<tr><td>{esc(label)}</td>'
                f'<td>{val_a}</td>'
                f'<td>{val_b}</td>'
                f'<td style="color:{color}">{diff_str}</td></tr>'
            )
    return (
        f'<div class="table-wrap"><table>'
        f'<thead><tr><th>Metric</th><th>{esc(label_a)}</th><th>{esc(label_b)}</th><th>Diff</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table></div>'
    )


def build_tag_cloud_svg(items, width=500, height=200):
    """Build a tag cloud SVG."""
    if not items:
        return ''
    max_val = max(v for _, v in items) if items else 1
    colors = ['#7f5af0', '#2cb67d', '#38bdf8', '#ff8906', '#e53170', '#14b8a6']
    texts = ''
    x, y = 10, 10
    max_line_height = 0
    for i, (name, value) in enumerate(sorted(items, key=lambda x: -x[1])[:30]):
        pct = value / max(max_val, 1)
        font_size = int(10 + pct * 16)
        color = colors[i % len(colors)]
        estimated_width = len(name) * font_size * 0.6
        if x + estimated_width > width - 10:
            x = 10
            y += max_line_height + 4
            max_line_height = 0
        if y + font_size > height:
            break
        texts += (
            f'<text x="{x}" y="{y + font_size}" fill="{color}" font-size="{font_size}" '
            f'opacity="{0.5 + pct * 0.5}" font-weight="600">{esc(name)}</text>'
        )
        x += estimated_width + 8
        max_line_height = max(max_line_height, font_size)
    return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">{texts}</svg>'


def build_framework_scorecard(frameworks, deps_count, lang_count):
    """Build a framework technology scorecard."""
    if not frameworks:
        return '<div style="color:var(--text2)">No frameworks detected</div>'
    items = ''
    for fw in frameworks:
        items += (
            f'<div style="display:inline-flex;align-items:center;gap:6px;padding:6px 14px;'
            f'background:var(--surface2);border-radius:var(--radius-xs);margin:4px;'
            f'border:1px solid var(--glass-border)">'
            f'<span style="font-weight:600">{esc(fw)}</span>'
            f'</div>'
        )
    score = min(len(frameworks) * 10 + deps_count * 0.5 + lang_count * 5, 100)
    return (
        f'<div style="margin:12px 0">'
        f'<div class="chart-title">Detected Technologies</div>'
        f'<div class="badges">{items}</div>'
        f'<div style="margin-top:12px;font-size:0.85em;color:var(--text2)">'
        f'Tech diversity score: <strong style="color:var(--primary-light)">{int(score)}/100</strong>'
        f' ({len(frameworks)} frameworks, {lang_count} languages, {deps_count} deps)'
        f'</div></div>'
    )


def build_file_type_breakdown(files):
    """Build a detailed file type breakdown."""
    if not files:
        return ''
    by_type = Counter(f['language'] for f in files)
    total = sum(by_type.values())
    rows = ''
    for lang, count in by_type.most_common(20):
        pct = count / max(total, 1) * 100
        color = get_lang_color(lang)
        bar_w = pct * 3
        rows += (
            f'<div style="display:flex;align-items:center;gap:10px;margin:3px 0">'
            f'<span style="min-width:100px;font-size:0.82em;color:{color};font-weight:600;text-align:right">{esc(lang)}</span>'
            f'<div style="flex:1;height:16px;background:var(--surface2);border-radius:3px;overflow:hidden">'
            f'<div style="width:{bar_w}px;height:100%;background:{color};opacity:0.6;border-radius:3px"></div>'
            f'</div>'
            f'<span style="min-width:60px;font-size:0.82em;color:var(--text3);text-align:right">{count} ({pct:.1f}%)</span>'
            f'</div>'
        )
    return f'<div style="margin:12px 0">{rows}</div>'


def build_complexity_treemap(files, width=600, height=250):
    """Build a treemap of files colored by complexity."""
    if not files:
        return ''
    data = [(f['path'].split('/')[-1], f['complexity']) for f in files[:25] if f['complexity'] > 0]
    if not data:
        return ''
    total = sum(v for _, v in data)
    rects = ''
    x, y = 0, 0
    row_h = 0
    for name, cc in sorted(data, key=lambda x: -x[1]):
        pct = cc / total
        w = max(pct * width, 2)
        h = pct * height
        if x + w > width:
            x = 0
            y += row_h
            row_h = 0
        if h > height - y:
            h = height - y
        if w > width - x:
            w = width - x
        color = '#e53170' if cc > 15 else '#ff8906' if cc > 8 else '#2cb67d' if cc > 3 else '#38bdf8'
        rects += (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{color}" opacity="0.6">'
            f'<title>{esc(name)}: CC={cc}</title></rect>'
        )
        if w > 40 and h > 14:
            rects.append(f'<text x="{x + 3}" y="{y + 11}" fill="white" font-size="8">{esc(name[:15])}</text>')
        x += w + 1
        row_h = max(row_h, h + 1)
        if y >= height:
            break
    return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">{"".join(rects)}</svg>'


def build_maintainability_gauge(mi):
    """Build a maintainability index gauge."""
    color = '#2cb67d' if mi >= 65 else '#ff8906' if mi >= 40 else '#e53170'
    label = 'Excellent' if mi >= 80 else 'Good' if mi >= 65 else 'Moderate' if mi >= 40 else 'Poor'
    return build_radial_gauge_svg(mi, 100, label, color, size=100)


def build_effort_estimate(total_loc, avg_complexity):
    """Build estimated effort visualization."""
    # Based on COCOMO simplified: effort = a * (KLOC)^b * complexity_factor
    kloc = total_loc / 1000
    base_effort = 2.4 * (kloc ** 1.05)
    complexity_factor = 1 + (avg_complexity - 5) * 0.05
    adjusted_effort = base_effort * max(complexity_factor, 0.5)
    months = round(adjusted_effort, 1)
    team_size = max(1, round(months / 12, 1))
    return (
        f'<div class="stats">'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">Estimated Effort</div>'
        f'<div class="value" style="font-size:1.2em">{months} person-months</div>'
        f'<div class="sub">~{team_size} developers for 12 months</div></div>'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">Lines per Person-Month</div>'
        f'<div class="value" style="font-size:1.2em">{int(total_loc / max(months, 0.1))}</div>'
        f'<div class="sub">industry avg: ~500-1000</div></div>'
        f'</div>'
    )


def build_annual_velocity(commits_timeline):
    """Build annual commit velocity visualization."""
    if not commits_timeline:
        return ''
    monthly = {}
    for t in commits_timeline:
        month = t['month'][:7]
        monthly[month] = monthly.get(month, 0) + t['count']
    values = list(monthly.values())
    months = list(monthly.keys())
    if not values:
        return ''
    avg = sum(values) / len(values)
    return (
        f'<div style="margin:12px 0">'
        f'<div class="chart-title">Monthly Commit Velocity</div>'
        f'{build_sparkline_svg(values, width=400, height=50)}'
        f'<div style="font-size:0.82em;color:var(--text3);margin-top:4px">'
        f'Average: {avg:.0f} commits/month | Total months: {len(months)}'
        f'</div></div>'
    )


def build_author_activity_grid(authors, heatmap):
    """Build a grid showing author activity by day."""
    if not authors or not heatmap:
        return ''
    top_authors = authors[:8]
    grid = ''
    for author in top_authors:
        name = author['name'][:20]
        grid += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
            f'<span style="min-width:120px;font-size:0.8em;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{esc(name)}</span>'
            f'<div style="width:{min(author["commits"] * 3, 300)}px;height:14px;'
            f'background:var(--primary);opacity:0.6;border-radius:3px"></div>'
            f'<span style="font-size:0.8em;color:var(--text3)">{author["commits"]}</span>'
            f'</div>'
        )
    return f'<div style="margin:12px 0"><div class="chart-title">Author Activity</div>{grid}</div>'


def build_git_insights_summary(git_data):
    """Build a comprehensive git insights summary."""
    if not git_data:
        return '<div style="color:var(--text2)">No git data available</div>'
    dr = git_data.get('date_range', {})
    bus = git_data.get('bus_factor', {})
    churn = git_data.get('code_churn', {})
    uncommitted = git_data.get('uncommitted', {})
    return (
        f'<div class="stats">'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">First Commit</div>'
        f'<div class="value" style="font-size:1em">{esc(dr.get("first", "N/A"))}</div></div>'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">Bus Factor</div>'
        f'<div class="value" style="font-size:1em;color:{"var(--accent)" if bus.get("factor", 0) <= 1 else "var(--green)"}">'
        f'{bus.get("factor", "N/A")}</div></div>'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">90-Day Churn</div>'
        f'<div class="value" style="font-size:1em">{churn.get("added", 0):,} / {churn.get("removed", 0):,}</div></div>'
        f'<div class="stat-card" style="padding:12px">'
        f'<div class="label">Uncommitted</div>'
        f'<div class="value" style="font-size:1em;color:{"var(--warning)" if sum(uncommitted.values()) > 0 else "var(--green)"}">'
        f'{sum(uncommitted.values())}</div></div>'
        f'</div>'
    )


def build_license_compatibility(licenses):
    """Build license compatibility matrix."""
    if not licenses:
        return '<div style="color:var(--text2)">No license data available</div>'
    copyleft = ['GPL-2.0', 'GPL-3.0', 'AGPL-3.0', 'LGPL-2.1', 'LGPL-3.0', 'EUPL-1.2']
    permissive = ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', '0BSD', 'X11']
    weak_copyleft = ['LGPL-2.1', 'LGPL-3.0', 'MPL-2.0', 'EPL-1.0', 'CDDL-1.0']
    
    items = ''
    for lic in licenses:
        name = lic.get('name', 'Unknown')
        category = 'Copyleft' if name in copyleft else 'Permissive' if name in permissive else 'Weak Copyleft' if name in weak_copyleft else 'Other'
        color = '#e53170' if category == 'Copyleft' else '#2cb67d' if category == 'Permissive' else '#ff8906'
        items += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--glass-border)">'
            f'<span style="font-family:monospace;font-size:0.85em;flex:1">{esc(name)}</span>'
            f'<span style="padding:2px 8px;border-radius:4px;font-size:0.72em;font-weight:600;background:{color}22;color:{color}">{esc(category)}</span>'
            f'</div>'
        )
    return f'<div style="margin:12px 0">{items}</div>'


def build_security_trend(sec_issues):
    """Build security findings trend analysis."""
    by_file = Counter(i.get('file', 'unknown') for i in sec_issues)
    by_sev = Counter(i.get('severity', 'unknown') for i in sec_issues)
    critical_files = [f for f, c in by_file.most_common(5) if c > 1]
    if not critical_files:
        return '<div style="color:var(--green);padding:12px">No recurring security issues found!</div>'
    items = ''.join(
        f'<div style="padding:8px;background:var(--surface2);border-radius:var(--radius-xs);margin-bottom:4px;'
        f'display:flex;justify-content:space-between">'
        f'<span style="font-family:monospace;font-size:0.82em">{esc(f)}</span>'
        f'<span style="font-size:0.82em;color:var(--accent);font-weight:600">{c} issues</span>'
        f'</div>'
        for f, c in critical_files
    )
    return f'<div style="margin-top:8px"><div class="chart-title">Files with Most Issues</div>{items}</div>'


def build_code_quality_treemap(quality_issues):
    """Build a treemap of quality issue types."""
    if not quality_issues:
        return ''
    by_type = Counter(qi.get('type', 'unknown') for qi in quality_issues)
    data = list(by_type.most_common(12))
    return build_treemap_svg(data, width=500, height=200)


def build_recommendation_card(rec, index):
    """Build a single recommendation card with priority styling."""
    priority_colors = {
        'critical': ('#e53170', 'rgba(229,49,112,0.1)'),
        'high': ('#ff8906', 'rgba(255,137,6,0.1)'),
        'medium': ('#7f5af0', 'rgba(127,90,240,0.1)'),
        'low': ('#a7a9be', 'rgba(167,169,190,0.08)'),
    }
    color, bg = priority_colors.get(rec.get('priority', 'low'), priority_colors['low'])
    return (
        f'<div style="padding:16px;background:{bg};border-radius:var(--radius-sm);margin-bottom:8px;'
        f'border-left:4px solid {color};transition:transform 0.2s;cursor:default">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
        f'<span style="font-size:1.3em">{rec.get("icon", "💡")}</span>'
        f'<span style="font-size:0.75em;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:0.5px">'
        f'{esc(rec.get("category", "General"))}</span>'
        f'<span style="padding:1px 8px;border-radius:4px;font-size:0.7em;font-weight:600;'
        f'background:{color}22;color:{color}">{esc(rec.get("priority", "low"))}</span>'
        f'<span style="margin-left:auto;font-size:0.75em;color:var(--text3)">#{index + 1}</span>'
        f'</div>'
        f'<div style="font-size:0.9em;color:var(--text2);line-height:1.5">{esc(rec.get("message", ""))}</div>'
        f'</div>'
    )


def build_overview_dashboard(analysis, scores):
    """Build the overview dashboard section."""
    tl = analysis['total_lines']
    total = tl['total']
    code_pct = round(tl['code'] / max(total, 1) * 100, 1)
    comment_pct = round(tl['comment'] / max(total, 1) * 100, 1)
    blank_pct = round(tl['blank'] / max(total, 1) * 100, 1)
    
    return (
        f'<div style="margin:16px 0">'
        f'<div class="chart-title">Code Composition</div>'
        f'<div style="display:flex;height:32px;border-radius:8px;overflow:hidden;margin:8px 0">'
        f'<div style="width:{code_pct}%;background:var(--primary);display:flex;align-items:center;justify-content:center;'
        f'font-size:0.75em;font-weight:700;color:white" title="Code: {code_pct}%">Code {code_pct}%</div>'
        f'<div style="width:{comment_pct}%;background:var(--green);display:flex;align-items:center;justify-content:center;'
        f'font-size:0.75em;font-weight:700;color:white" title="Comments: {comment_pct}%">Comments {comment_pct}%</div>'
        f'<div style="width:{blank_pct}%;background:var(--surface3);display:flex;align-items:center;justify-content:center;'
        f'font-size:0.75em;font-weight:700;color:var(--text2)" title="Blank: {blank_pct}%">Blank {blank_pct}%</div>'
        f'</div></div>'
    )


def build_print_header(project_name, date_str):
    """Build a print-only header section."""
    return (
        f'<div class="print-only" style="display:none">@media print{{.print-only{{display:block!important}}}}'
        f'<div style="text-align:center;padding:20px 0;border-bottom:2px solid #333">'
        f'<h1 style="font-size:24px">CodeVista Report</h1>'
        f'<p>{esc(project_name)} — Generated {esc(date_str)}</p>'
        f'</div></div>'
    )


def build_footer(version, project_name):
    """Build the report footer."""
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    return (
        f'<footer style="text-align:center;padding:40px 0 20px;color:var(--text3);font-size:0.85em;'
        f'border-top:1px solid var(--glass-border);margin-top:40px">'
        f'<p>Generated by <strong style="color:var(--primary-light)">CodeVista</strong> v{version} · {now}</p>'
        f'<p style="margin-top:4px;font-size:0.75em">Project: {esc(project_name)} · '
        f'Zero dependencies · Runs locally</p>'
        f'</footer>'
    )


def build_skeleton_loader():
    """Build skeleton loading animation HTML."""
    return (
        '<style>'
        '.skeleton{background:linear-gradient(90deg,var(--surface2) 25%,var(--surface3) 50%,var(--surface2) 75%);'
        'background-size:200% 100%;animation:skeleton-loading 1.5s infinite;border-radius:8px}'
        '@keyframes skeleton-loading{0%{background-position:200% 0}100%{background-position:-200% 0}}'
        '</style>'
        '<div class="skeleton" style="height:200px;margin-bottom:16px"></div>'
        '<div class="skeleton" style="height:100px;margin-bottom:16px"></div>'
        '<div class="skeleton" style="height:300px"></div>'
    )


def build_empty_state(message, icon='🔍'):
    """Build an empty state placeholder."""
    return (
        f'<div style="text-align:center;padding:48px 24px;color:var(--text3)">'
        f'<div style="font-size:3em;margin-bottom:12px">{icon}</div>'
        f'<div style="font-size:1.1em;margin-bottom:8px">{esc(message)}</div>'
        f'</div>'
    )


def build_stats_comparison_bar(label, value_a, value_b, label_a, label_b):
    """Build a comparison bar for two values."""
    max_val = max(value_a, value_b, 1)
    w_a = (value_a / max_val) * 45
    w_b = (value_b / max_val) * 45
    return (
        f'<div style="margin:6px 0">'
        f'<div style="font-size:0.8em;color:var(--text2);margin-bottom:4px">{esc(label)}</div>'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<span style="min-width:60px;font-size:0.75em;text-align:right;color:var(--text3)">{esc(label_a)}</span>'
        f'<div style="width:{w_a}%;height:12px;background:var(--primary);opacity:0.7;border-radius:3px"></div>'
        f'<div style="width:{w_b}%;height:12px;background:var(--teal);opacity:0.7;border-radius:3px"></div>'
        f'<span style="min-width:60px;font-size:0.75em;color:var(--text3)">{esc(label_b)}</span>'
        f'</div></div>'
    )


def build_gauge_chart(title, value, max_val, thresholds=None):
    """Build a horizontal gauge chart with colored thresholds."""
    if thresholds is None:
        thresholds = [(0.6, "#2cb67d"), (0.8, "#ff8906"), (1.0, "#e53170")]
    pct = min(value / max(max_val, 1), 1.0)
    segments = ""
    prev = 0
    for threshold, color in thresholds:
        seg_w = (threshold - prev) * 300
        active = pct >= prev
        opacity = "0.8" if active else "0.2"
        segments += (
            '<rect x="' + str(int(prev * 300)) + '" y="0" width="' + str(int(seg_w)) +
            '" height="16" rx="3" fill="' + color + '" opacity="' + opacity + '"/>'
        )
        prev = threshold
    needle_x = min(pct * 300, 300)
    return (
        '<div style="margin:8px 0">'
        '<div style="font-size:0.85em;color:var(--text2);margin-bottom:4px">' +
        esc(title) + ': ' + str(value) + '/' + str(max_val) + '</div>'
        '<svg viewBox="0 0 320 30" width="100%" height="30">' + segments +
        '<circle cx="' + str(int(needle_x) + 10) + '" cy="8" r="6" fill="var(--text)" />'
        '</svg></div>'
    )


def build_data_table(headers, rows, sortable=True):
    """Build a generic data table with optional sorting."""
    header_cells = ""
    for h in headers:
        header_cells += "<th>" + esc(h) + "</th>"
    body_rows = ""
    for row in rows:
        cells = "".join("<td>" + esc(str(cell)) + "</td>" for cell in row)
        body_rows += "<tr>" + cells + "</tr>"
    return (
        '<div class="table-wrap"><table>'
        '<thead><tr>' + header_cells + '</tr></thead>'
        '<tbody>' + body_rows + '</tbody>'
        '</table></div>'
    )


def build_gauge_chart(title, value, max_val, thresholds=None):
    """Build a horizontal gauge chart with colored thresholds."""
    if thresholds is None:
        thresholds = [(0.6, "#2cb67d"), (0.8, "#ff8906"), (1.0, "#e53170")]
    pct = min(value / max(max_val, 1), 1.0)
    segments = ""
    prev = 0
    for threshold, color in thresholds:
        seg_w = int((threshold - prev) * 300)
        active = pct >= prev
        opacity = "0.8" if active else "0.2"
        segments += (
            '<rect x="' + str(int(prev * 300)) + '" y="0" width="' + str(seg_w) +
            '" height="16" rx="3" fill="' + color + '" opacity="' + opacity + '"/>'
        )
        prev = threshold
    needle_x = min(pct * 300, 300)
    return (
        '<div style="margin:8px 0">'
        '<div style="font-size:0.85em;color:var(--text2);margin-bottom:4px">' +
        esc(title) + ': ' + str(value) + '/' + str(max_val) + '</div>'
        '<svg viewBox="0 0 320 30" width="100%" height="30">' + segments +
        '<circle cx="' + str(int(needle_x) + 10) + '" cy="8" r="6" fill="var(--text)" />'
        '</svg></div>'
    )


def build_data_table(headers, rows, sortable=True):
    """Build a generic data table with optional sorting."""
    header_cells = ""
    for h in headers:
        header_cells += "<th>" + esc(h) + "</th>"
    body_rows = ""
    for row in rows:
        cells = "".join("<td>" + esc(str(cell)) + "</td>" for cell in row)
        body_rows += "<tr>" + cells + "</tr>"
    return (
        '<div class="table-wrap"><table>'
        '<thead><tr>' + header_cells + '</tr></thead>'
        '<tbody>' + body_rows + '</tbody>'
        '</table></div>'
    )
