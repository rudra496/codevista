"""CodeVista CLI — comprehensive command-line interface.

Commands: analyze, quick, serve, compare, watch, health,
security, deps, git-stats, languages, complexity.
"""

import argparse
import os
import sys
import time
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser


def main():
    parser = argparse.ArgumentParser(
        prog='codevista',
        description='🔍 CodeVista — Google Analytics for your code',
    )
    parser.add_argument('-v', '--version', action='version', version='CodeVista 1.0.0')
    sub = parser.add_subparsers(dest='command', help='Available commands')

    # analyze — full analysis
    p = sub.add_parser('analyze', help='Full codebase analysis')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('-o', '--output', default='codevista-report.html', help='Output HTML file')
    p.add_argument('--no-git', action='store_true', help='Skip git analysis')
    p.add_argument('--depth', type=int, default=None, help='Max directory depth')
    p.add_argument('--no-serve', action='store_true', help='Do not auto-open browser')
    p.add_argument('--json', action='store_true', help='Output raw JSON instead of HTML')

    # quick — fast analysis
    p = sub.add_parser('quick', help='Fast analysis (limited depth, no git)')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('-o', '--output', default='codevista-report.html', help='Output HTML file')

    # serve — serve and auto-reload
    p = sub.add_parser('serve', help='Serve report on local server with auto-reload')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('-o', '--output', default='codevista-report.html', help='Output HTML file')
    p.add_argument('--port', type=int, default=8080, help='Server port')
    p.add_argument('--host', default='0.0.0.0', help='Server host')

    # compare — compare two projects
    p = sub.add_parser('compare', help='Compare two codebases')
    p.add_argument('path1', help='First project directory')
    p.add_argument('path2', help='Second project directory')
    p.add_argument('-o', '--output', default='comparison.html', help='Output file')

    # watch — re-analyze on changes
    p = sub.add_parser('watch', help='Re-analyze on file changes')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('-o', '--output', default='codevista-report.html', help='Output HTML file')
    p.add_argument('--interval', type=float, default=3.0, help='Poll interval in seconds')

    # health — health score only
    p = sub.add_parser('health', help='Show health score summary')
    p.add_argument('path', nargs='?', default='.', help='Project directory')

    # security — security scan only
    p = sub.add_parser('security', help='Security scan only')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('--json', action='store_true', help='Output raw JSON')

    # deps — dependency analysis
    p = sub.add_parser('deps', help='Dependency analysis')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('--outdated', action='store_true', help='Check for outdated packages')
    p.add_argument('--licenses', action='store_true', help='Fetch license info')

    # git-stats — git statistics
    p = sub.add_parser('git-stats', help='Git repository statistics')
    p.add_argument('path', nargs='?', default='.', help='Project directory')

    # languages — language breakdown
    p = sub.add_parser('languages', help='Language distribution breakdown')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('--top', type=int, default=15, help='Number of languages to show')

    # complexity — complexity analysis
    p = sub.add_parser('complexity', help='Complexity analysis and top functions')
    p.add_argument('path', nargs='?', default='.', help='Project directory')
    p.add_argument('--threshold', type=int, default=10, help='Complexity warning threshold')
    p.add_argument('--top', type=int, default=20, help='Number of top functions to show')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    command_map = {
        'analyze': cmd_analyze,
        'quick': cmd_quick,
        'serve': cmd_serve,
        'compare': cmd_compare,
        'watch': cmd_watch,
        'health': cmd_health,
        'security': cmd_security,
        'deps': cmd_deps,
        'git-stats': cmd_git_stats,
        'languages': cmd_languages,
        'complexity': cmd_complexity,
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


def _resolve_path(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print(f"❌ Directory not found: {path}")
        sys.exit(1)
    return path


def cmd_analyze(args):
    from .analyzer import analyze_project
    from .report import generate_report
    from .metrics import calculate_health

    path = _resolve_path(args.path)
    print(f"🔍 Analyzing {path}...")
    start = time.time()

    analysis = analyze_project(path, max_depth=args.depth, include_git=not args.no_git)
    scores = calculate_health(analysis)
    elapsed = time.time() - start

    if args.json:
        import json
        result = {**analysis, 'scores': scores}
        print(json.dumps(result, indent=2, default=str))
        return

    output = os.path.abspath(args.output)
    generate_report(analysis, output)

    print(f"\n{'─'*50}")
    print(f"✅ Report generated: {output}")
    print(f"{'─'*50}")
    print(f"   📁 {analysis['total_files']:,} files analyzed")
    print(f"   📝 {analysis['total_lines']['code']:,} lines of code")
    print(f"   🧩 {len(analysis['languages'])} languages detected")
    print(f"   ⚡ {len(analysis.get('functions', [])):,} functions")
    print(f"   🔒 {len(analysis['security_issues'])} security issues")
    print(f"   📦 {len(analysis['dependencies'])} dependencies")
    print(f"   🏥 Health score: {scores['overall']}/100")
    print(f"   ⏱️  Completed in {elapsed:.2f}s")

    if not args.no_serve:
        _open_file(output)


def cmd_quick(args):
    from .analyzer import quick_analyze
    from .report import generate_report

    path = _resolve_path(args.path)
    print(f"⚡ Quick analysis of {path}...")
    start = time.time()

    analysis = quick_analyze(path)
    output = os.path.abspath(args.output)
    generate_report(analysis, output)

    print(f"✅ Quick report: {output} ({time.time() - start:.2f}s)")
    _open_file(output)


def cmd_serve(args):
    from .analyzer import analyze_project
    from .report import generate_report

    path = _resolve_path(args.path)
    output = os.path.abspath(args.output)
    print(f"🌐 Analyzing {path}...")
    analysis = analyze_project(path)
    generate_report(analysis, output)

    os.chdir(os.path.dirname(output))
    fname = os.path.basename(output)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.path = f'/{fname}'
            return super().do_GET()
        def log_message(self, format, *args):
            pass

    server = HTTPServer((args.host, args.port), Handler)
    url = f'http://localhost:{args.port}'
    print(f"\n🚀 Serving report at {url}")
    print(f"   Press Ctrl+C to stop")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        server.server_close()


def cmd_compare(args):
    from .analyzer import analyze_project
    from .report import generate_report
    from .metrics import calculate_health
    import html

    path1 = _resolve_path(args.path1)
    path2 = _resolve_path(args.path2)
    print(f"📊 Comparing {path1} vs {path2}...")

    a1 = analyze_project(path1, include_git=False, quick_mode=True)
    a2 = analyze_project(path2, include_git=False, quick_mode=True)
    s1 = calculate_health(a1)
    s2 = calculate_health(a2)

    sc = lambda s: '#2cb67d' if s >= 80 else '#ff8906' if s >= 50 else '#e53170'
    e = html.escape

    comparison_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CodeVista Comparison</title>
<style>:root{{--bg:#0a0a1a;--surface:#12122a;--text:#eeeef5;--text2:#8888aa;--primary:#7f5af0;--green:#2cb67d;--warning:#ff8906;--accent:#e53170;--radius:16px;}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;margin:0;padding:24px;}}
.container{{max-width:1000px;margin:0 auto;}}h1{{text-align:center;font-size:2em;margin-bottom:8px;}}
.sub{{text-align:center;color:var(--text2);margin-bottom:24px;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;}}
.card{{background:var(--surface);border-radius:var(--radius);padding:24px;border:1px solid rgba(127,90,240,0.12);}}
.card h2{{font-size:1.1em;margin-bottom:12px;}}
.metric{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:0.9em;}}
.metric .l{{color:var(--text2);}}.vs{{text-align:center;font-size:2em;color:var(--text2);padding:8px;}}
.health-bar{{height:8px;border-radius:4px;background:rgba(255,255,255,0.05);margin-top:12px;overflow:hidden;}}
.health-fill{{height:100%;border-radius:4px;transition:width 1s;}}
</style></head><body><div class="container">
<h1>📊 CodeVista Comparison</h1><div class="sub">{e(os.path.basename(path1))} vs {e(os.path.basename(path2))}</div>
<div class="grid">
<div class="card"><h2>{e(os.path.basename(path1))}</h2>
  <div class="metric"><span class="l">Files</span><span>{a1["total_files"]:,}</span></div>
  <div class="metric"><span class="l">Lines of Code</span><span>{a1["total_lines"]["code"]:,}</span></div>
  <div class="metric"><span class="l">Languages</span><span>{len(a1["languages"])}</span></div>
  <div class="metric"><span class="l">Avg Complexity</span><span>{a1["avg_complexity"]:.1f}</span></div>
  <div class="metric"><span class="l">Security Issues</span><span>{len(a1["security_issues"])}</span></div>
  <div class="metric"><span class="l">Dependencies</span><span>{len(a1["dependencies"])}</span></div>
  <div class="metric"><span class="l">Functions</span><span>{len(a1.get("functions",[])):,}</span></div>
  <div class="metric"><span class="l" style="font-size:1.1em;font-weight:700">Health Score</span>
    <span style="font-size:1.3em;color:{sc(s1["overall"])}">{s1["overall"]}</span></div>
  <div class="health-bar"><div class="health-fill" style="width:{s1["overall"]}%;background:{sc(s1["overall"])}"></div></div>
</div>
<div class="card"><h2>{e(os.path.basename(path2))}</h2>
  <div class="metric"><span class="l">Files</span><span>{a2["total_files"]:,}</span></div>
  <div class="metric"><span class="l">Lines of Code</span><span>{a2["total_lines"]["code"]:,}</span></div>
  <div class="metric"><span class="l">Languages</span><span>{len(a2["languages"])}</span></div>
  <div class="metric"><span class="l">Avg Complexity</span><span>{a2["avg_complexity"]:.1f}</span></div>
  <div class="metric"><span class="l">Security Issues</span><span>{len(a2["security_issues"])}</span></div>
  <div class="metric"><span class="l">Dependencies</span><span>{len(a2["dependencies"])}</span></div>
  <div class="metric"><span class="l">Functions</span><span>{len(a2.get("functions",[])):,}</span></div>
  <div class="metric"><span class="l" style="font-size:1.1em;font-weight:700">Health Score</span>
    <span style="font-size:1.3em;color:{sc(s2["overall"])}">{s2["overall"]}</span></div>
  <div class="health-bar"><div class="health-fill" style="width:{s2["overall"]}%;background:{sc(s2["overall"])}"></div></div>
</div></div>
<div class="vs">VS</div>
</div></body></html>'''

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(comparison_html)
    print(f"✅ Comparison saved: {args.output}")


def cmd_watch(args):
    from .analyzer import analyze_project
    from .report import generate_report

    path = os.path.abspath(args.path)
    _resolve_path(args.path)
    print(f"👁️  Watching {path} for changes (every {args.interval}s)...")

    last_mtime = _get_max_mtime(path)
    while True:
        try:
            time.sleep(args.interval)
            current = _get_max_mtime(path)
            if current > last_mtime:
                last_mtime = current
                print(f"\n🔄 Change detected, re-analyzing...")
                analysis = analyze_project(path)
                generate_report(analysis, args.output)
                print(f"✅ Report updated: {args.output}")
        except KeyboardInterrupt:
            print("\n👋 Watch stopped")
            break


def cmd_health(args):
    from .analyzer import analyze_project
    from .metrics import calculate_health, get_trend

    path = _resolve_path(args.path)
    print(f"🏥 Analyzing health of {path}...")
    start = time.time()
    analysis = analyze_project(path, include_git=False, quick_mode=True)
    scores = calculate_health(analysis)
    elapsed = time.time() - start

    print(f"\n{'─'*45}")
    print(f"  CodeVista Health Report")
    print(f"  {os.path.basename(path)}")
    print(f"{'─'*45}")
    for cat, score in scores.items():
        if cat == 'overall':
            continue
        trend = get_trend(score)
        icon = {'good': '✅', 'warning': '⚠️', 'critical': '❌'}[trend]
        bar_len = score // 5
        bar = '█' * bar_len + '░' * (20 - bar_len)
        color = '#2cb67d' if trend == 'good' else '#ff8906' if trend == 'warning' else '#e53170'
        print(f"  {icon} {cat.replace('_', ' ').title():18s} {score:3d}/100 [{bar}]")
    print(f"{'─'*45}")
    print(f"  🏥 Overall Health: {scores['overall']}/100")
    print(f"  ⏱️  Analysis time: {elapsed:.2f}s")
    print(f"  📁 {analysis['total_files']:,} files · {analysis['total_lines']['code']:,} LoC")
    print(f"{'─'*45}")


def cmd_security(args):
    from .security import scan_directory, security_summary, get_severity_icon

    path = _resolve_path(args.path)
    print(f"🔒 Running security scan on {path}...")
    start = time.time()
    issues = scan_directory(path)
    elapsed = time.time() - start

    if args.json:
        import json
        print(json.dumps(issues, indent=2))
        return

    summary = security_summary(issues)
    print(f"\n{'─'*50}")
    print(f"  🔒 Security Scan Results")
    print(f"{'─'*50}")
    print(f"  Total issues: {summary['total']}")
    print(f"  Score: {summary['score']}/100")
    for sev in ('critical', 'high', 'medium', 'low'):
        count = summary['by_severity'].get(sev, 0)
        if count > 0:
            print(f"  {get_severity_icon(sev)} {sev.upper():10s} {count}")
    if summary['top_files']:
        print(f"\n  Top affected files:")
        for f in summary['top_files'][:5]:
            print(f"    • {f}")
    print(f"{'─'*50}")
    print(f"  ⏱️  Scan completed in {elapsed:.2f}s")


def cmd_deps(args):
    from .dependencies import find_dependencies, check_outdated_deps, extract_licenses, analyze_dependency_health

    path = _resolve_path(args.path)
    deps, pkg_manager = find_dependencies(path)

    if not deps:
        print(f"📦 No dependencies found (no {pkg_manager or 'package'} file)")
        return

    health = analyze_dependency_health(deps, pkg_manager or 'pip')
    print(f"\n📦 Dependencies ({pkg_manager or 'unknown'})")
    print(f"{'─'*60}")
    print(f"  Total: {health['total']} packages")
    print(f"  Pinned: {health['pinned']} | Ranged: {health['ranged']} | Wildcard: {health['wildcard']}")
    print(f"  Pin rate: {health['pin_rate']}%")
    print(f"  Pin score: {health['pin_score']}/100")
    print(f"\n  {'Package':<35s} {'Version':<15s} {'Operator':<10s}")
    print(f"  {'─'*60}")
    for d in deps[:50]:
        print(f"  {d['name']:<35s} {d.get('spec','*'):<15s} {d.get('operator',''):<10s}")

    if args.outdated:
        print(f"\n🔄 Checking for outdated packages (max 10)...")
        outdated = check_outdated_deps(deps, pkg_manager or 'pip')
        if outdated:
            print(f"  {'Package':<25s} {'Current':<15s} {'Latest':<15s}")
            print(f"  {'─'*55}")
            for o in outdated:
                print(f"  {o['name']:<25s} {o['current']:<15s} {o['latest']:<15s}")
        else:
            print("  ✅ All checked packages are up to date!")

    if args.licenses:
        print(f"\n📜 Fetching license info (max 10)...")
        licenses = extract_licenses(deps, pkg_manager or 'pip')
        for l in licenses:
            print(f"  {l['name']:<25s} {l.get('license','Unknown')}")


def cmd_git_stats(args):
    from .git_analysis import full_git_analysis

    path = _resolve_path(args.path)
    if not os.path.isdir(os.path.join(path, '.git')):
        print("❌ Not a git repository")
        sys.exit(1)

    print(f"👥 Analyzing git repository...")
    git = full_git_analysis(path)
    if not git:
        print("❌ Could not analyze git repository")
        sys.exit(1)

    dr = git['date_range']
    bus = git['bus_factor']
    br = git['branches']
    churn = git['code_churn']
    merges = git['merges']

    print(f"\n{'─'*50}")
    print(f"  👥 Git Statistics")
    print(f"{'─'*50}")
    print(f"  Total commits:   {git['total_commits']:,}")
    print(f"  Contributors:    {len(git['authors'])}")
    print(f"  Active since:    {dr.get('first', '?')}")
    print(f"  Last commit:     {dr.get('last', '?')}")
    print(f"  Current branch:  {br.get('current', '?')}")
    print(f"  Local branches:  {br.get('count', 0)}")
    print(f"  Bus factor:      {bus.get('factor', 0)} ({bus.get('coverage_pct', 0)}% coverage)")
    print(f"  Tags:            {len(git.get('tags', []))}")
    print(f"\n  📈 90-day Activity:")
    print(f"     Lines added:  {churn.get('added', 0):,}")
    print(f"     Lines removed:{churn.get('removed', 0):,}")
    print(f"     Net change:   {churn.get('net', 0):+,}")
    print(f"     Avg commit:   {churn.get('avg_commit_size', 0)} lines")
    print(f"     Merge rate:   {merges.get('merge_rate', 0)}%")
    print(f"\n  🏆 Top Contributors:")
    for a in git['authors'][:10]:
        pct = a['commits'] / max(git['total_commits'], 1) * 100
        bar = '█' * int(pct / 2)
        print(f"     {a['name']:<30s} {a['commits']:>5d} ({pct:.1f}%) {bar}")
    print(f"{'─'*50}")


def cmd_languages(args):
    from .analyzer import analyze_project
    from .languages import get_lang_color, get_category

    path = _resolve_path(args.path)
    print(f"🧩 Analyzing languages in {path}...")
    analysis = analyze_project(path, include_git=False, quick_mode=True)

    langs = sorted(analysis['languages'].items(), key=lambda x: -x[1])
    total = sum(c for _, c in langs) or 1

    print(f"\n{'─'*60}")
    print(f"  🧩 Language Distribution ({len(langs)} languages)")
    print(f"{'─'*60}")
    print(f"  {'Language':<25s} {'Lines':>10s} {'%':>7s}  {'Bar'}")
    print(f"  {'─'*60}")
    for lang, count in langs[:args.top]:
        pct = count / total * 100
        bar_len = int(pct / 3)
        cat = get_category(lang)
        print(f"  {lang:<25s} {count:>10,} {pct:>6.1f}% {'█' * bar_len}")
    print(f"{'─'*60}")
    print(f"  Total: {total:,} lines across {len(langs)} languages")


def cmd_complexity(args):
    from .analyzer import analyze_project

    path = _resolve_path(args.path)
    print(f"⚡ Analyzing complexity in {path}...")
    analysis = analyze_project(path, include_git=False, quick_mode=True)

    top_funcs = sorted(analysis.get('functions', []),
                       key=lambda x: x['complexity'], reverse=True)[:args.top]

    print(f"\n{'─'*70}")
    print(f"  ⚡ Complexity Analysis (threshold: {args.threshold})")
    print(f"{'─'*70}")
    print(f"  Avg complexity: {analysis['avg_complexity']:.1f}")
    print(f"  Max complexity: {analysis['max_complexity']}")
    high_count = sum(1 for f in analysis.get('functions', []) if f['complexity'] > args.threshold)
    print(f"  Functions above threshold: {high_count}")
    print(f"\n  {'#':>3s} {'Function':<35s} {'CC':>4s} {'Cog':>5s} {'Nest':>5s} {'Params':>6s} {'Lines':>5s} {'File'}")
    print(f"  {'─'*70}")

    for i, f in enumerate(top_funcs, 1):
        cc_color = '🔴' if f['complexity'] > 20 else '🟠' if f['complexity'] > args.threshold else '🟢'
        print(f"  {cc_color} {i:>2d} {f['name']:<35s} {f['complexity']:>4d} {f.get('cognitive_complexity',0):>5d} {f.get('nesting_depth',0):>5d} {f.get('param_count',0):>6d} {f['line_count']:>5d}  .../{f.get('file','').split('/')[-1] if f.get('file') else ''}")

    print(f"{'─'*70}")


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_max_mtime(path):
    latest = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ('node_modules', '__pycache__', '.git', 'vendor', 'build', 'dist',
                    '.venv', 'venv', 'target', '.tox', '.next', '.nuxt')]
        for f in files:
            try:
                mtime = os.path.getmtime(os.path.join(root, f))
                if mtime > latest:
                    latest = mtime
            except OSError:
                continue
    return latest


def _open_file(filepath):
    try:
        if sys.platform == 'darwin':
            subprocess.run(['open', filepath], check=False)
        elif sys.platform == 'win32':
            os.startfile(filepath)
        else:
            subprocess.run(['xdg-open', filepath], check=False)
    except (OSError, subprocess.SubprocessError):
        pass


if __name__ == '__main__':
    main()
