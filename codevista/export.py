"""Export Module — export analysis results in multiple formats.

Supports: HTML, JSON, Markdown, SARIF (CI integration), CSV, CODE_METRICS.yaml,
and batch export to all formats at once.
"""

import csv
import io
import json
import os
import math
from datetime import datetime
from typing import Dict, List, Optional, Any

from .metrics import calculate_health
from .languages import get_lang_color


# ── Main Export Entry Point ────────────────────────────────────────────────

def export_report(analysis: Dict[str, Any], output_path: str,
                  format: str = 'html', **kwargs) -> str:
    """Export analysis results to the specified format.

    Args:
        analysis: Full analysis data from analyzer.
        output_path: Output file path (without extension).
        format: One of 'html', 'json', 'markdown', 'sarif', 'csv', 'yaml'.
        **kwargs: Additional options passed to format-specific exporters.

    Returns:
        Path to the generated file.
    """
    exporters = {
        'html': export_html,
        'json': export_json,
        'markdown': export_markdown,
        'sarif': export_sarif,
        'csv': export_csv,
        'yaml': export_code_metrics_yaml,
        'pdf': export_pdf,
    }

    exporter = exporters.get(format.lower())
    if not exporter:
        raise ValueError(f'Unsupported export format: {format}. '
                         f'Supported: {", ".join(exporters.keys())}')

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    return exporter(analysis, output_path, **kwargs)


def export_all(analysis: Dict[str, Any], output_dir: str,
               base_name: str = 'codevista-report') -> Dict[str, str]:
    """Export analysis to all supported formats.

    Args:
        analysis: Full analysis data.
        output_dir: Directory to write files to.
        base_name: Base filename (without extension).

    Returns:
        Dict mapping format to output file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    formats = {
        'json': f'{base_name}.json',
        'markdown': f'{base_name}.md',
        'csv': f'{base_name}.csv',
        'yaml': f'{base_name}.yaml',
        'sarif': f'{base_name}.sarif.json',
        'html': f'{base_name}.html',
    }

    for fmt, filename in formats.items():
        try:
            path = os.path.join(output_dir, filename)
            export_report(analysis, path, format=fmt)
            results[fmt] = path
        except Exception as e:
            results[fmt] = f'Error: {e}'

    return results


# ── HTML Export ─────────────────────────────────────────────────────────────

def export_html(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export as a self-contained HTML summary report."""
    from .report import generate_report

    path = output_path if output_path.endswith('.html') else output_path + '.html'
    generate_report(analysis, path)
    return path


# ── JSON Export ─────────────────────────────────────────────────────────────

def export_json(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export full analysis data as JSON."""
    path = output_path if output_path.endswith('.json') else output_path + '.json'

    # Convert non-serializable types
    serializable = _make_json_serializable(analysis)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, default=str, ensure_ascii=False)

    return path


# ── Markdown Export ────────────────────────────────────────────────────────

def export_markdown(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export analysis summary as Markdown."""
    path = output_path if output_path.endswith('.md') else output_path + '.md'

    scores = calculate_health(analysis)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        f'# 🔍 CodeVista Report: {analysis.get("project_name", "Unknown")}',
        f'',
        f'Generated: {now}',
        f'',
        f'## 📊 Overview',
        f'',
        f'| Metric | Value |',
        f'|--------|-------|',
        f'| Files | {analysis["total_files"]:,} |',
        f'| Lines of Code | {analysis["total_lines"]["code"]:,} |',
        f'| Comments | {analysis["total_lines"]["comment"]:,} |',
        f'| Blank Lines | {analysis["total_lines"]["blank"]:,} |',
        f'| Languages | {len(analysis["languages"])} |',
        f'| Functions | {len(analysis.get("functions", [])):,} |',
        f'| Avg Complexity | {analysis["avg_complexity"]:.1f} |',
        f'| Max Complexity | {analysis["max_complexity"]} |',
        f'| Dependencies | {len(analysis["dependencies"])} |',
        f'| Security Issues | {len(analysis["security_issues"])} |',
        f'| TODOs | {len(analysis.get("todos", []))} |',
        f'| Duplicates | {len(analysis.get("duplicates", []))} |',
        f'',
        f'## 🏥 Health Score: {scores["overall"]}/100',
        f'',
        f'| Category | Score |',
        f'|----------|-------|',
    ]

    for cat in ('readability', 'complexity', 'duplication', 'coverage', 'security',
                'dependencies', 'maintainability'):
        score = scores.get(cat, 0)
        emoji = '✅' if score >= 80 else '⚠️' if score >= 50 else '❌'
        lines.append(f'| {cat.title()} | {emoji} {score}/100 |')

    lines.extend([
        f'',
        f'## 🧩 Languages',
        f'',
    ])

    for lang, count in sorted(analysis['languages'].items(), key=lambda x: -x[1])[:15]:
        total = sum(analysis['languages'].values()) or 1
        pct = count / total * 100
        lines.append(f'- **{lang}**: {count:,} lines ({pct:.1f}%)')

    # Top complex functions
    top_funcs = analysis.get('top_complex_functions', [])[:15]
    if top_funcs:
        lines.extend([
            f'',
            f'## ⚡ Top Complex Functions',
            f'',
            f'| # | Function | Complexity | Cognitive | Lines | File |',
            f'|---|----------|------------|-----------|-------|------|',
        ])
        for i, f in enumerate(top_funcs, 1):
            fname = f.get('file', '').split('/')[-1] if f.get('file') else ''
            lines.append(
                f'| {i} | `{f["name"]}` | {f["complexity"]} | '
                f'{f.get("cognitive_complexity", 0)} | {f["line_count"]} | {fname} |'
            )

    # Security issues
    sec_issues = analysis.get('security_issues', [])
    if sec_issues:
        lines.extend([
            f'',
            f'## 🔒 Security Issues ({len(sec_issues)})',
            f'',
        ])
        sev_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        for issue in sorted(sec_issues, key=lambda x: sev_order.get(x['severity'], 4))[:20]:
            lines.append(
                f'- **[{issue["severity"].upper()}]** {issue["name"]} '
                f'({issue.get("file", "unknown")}:{issue.get("line", 0)})'
            )

    # Dependencies
    deps = analysis.get('dependencies', [])
    if deps:
        lines.extend([
            f'',
            f'## 📦 Dependencies ({analysis.get("package_manager", "unknown")})',
            f'',
        ])
        for d in deps[:30]:
            lines.append(f'- `{d["name"]}` {d.get("spec", "*")}')

    # Frameworks
    frameworks = analysis.get('frameworks', [])
    if frameworks:
        lines.extend([
            f'',
            f'## 🧩 Detected Frameworks',
            f'',
        ])
        for fw in frameworks:
            lines.append(f'- {fw}')

    lines.extend([
        f'',
        f'---',
        f'*Generated by [CodeVista](https://github.com) · {now}*',
    ])

    content = '\n'.join(lines)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


# ── SARIF Export (Static Analysis Results Interchange Format) ──────────────

def export_sarif(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export as SARIF for CI integration (GitHub Code Scanning, etc.)."""
    path = output_path if output_path.endswith('.json') else output_path + '.sarif.json'

    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    project_path = analysis.get('project_path', os.getcwd())

    rules = []
    results = []

    # Convert security issues to SARIF
    seen_rules = set()
    for issue in analysis.get('security_issues', []):
        rule_id = f'codevista-{issue["name"].lower().replace(" ", "-")}'
        if rule_id not in seen_rules:
            seen_rules.add(rule_id)
            sev_map = {'critical': 'error', 'high': 'error', 'medium': 'warning', 'low': 'note'}
            rules.append({
                'id': rule_id,
                'name': issue['name'],
                'shortDescription': {'text': issue['name']},
                'fullDescription': {'text': issue.get('remediation', issue['name'])},
                'helpUri': 'https://github.com',
                'properties': {'category': 'Security'},
                'defaultConfiguration': {
                    'level': sev_map.get(issue['severity'], 'warning'),
                },
            })

        sev_level = {'critical': 'error', 'high': 'error', 'medium': 'warning',
                     'low': 'note'}.get(issue['severity'], 'warning')

        results.append({
            'ruleId': rule_id,
            'level': sev_level,
            'message': {'text': f'{issue["name"]}: {issue.get("remediation", "")}'},
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'uri': os.path.relpath(issue.get('file', ''), project_path)
                                if issue.get('file') else 'unknown',
                    },
                    'region': {
                        'startLine': issue.get('line', 1),
                    },
                },
            }],
        })

    # Convert quality issues to SARIF
    quality_issues = analysis.get('quality_issues', [])
    for qi in quality_issues[:100]:
        rule_id = f'codevista-{qi.get("type", "quality")}'
        if rule_id not in seen_rules:
            seen_rules.add(rule_id)
            rules.append({
                'id': rule_id,
                'name': qi.get('type', 'quality'),
                'shortDescription': {'text': qi.get('type', 'Quality issue')},
                'fullDescription': {'text': qi.get('message', '')},
                'properties': {'category': 'Quality'},
                'defaultConfiguration': {'level': 'warning'},
            })

        results.append({
            'ruleId': rule_id,
            'level': 'warning',
            'message': {'text': qi.get('message', 'Quality issue')},
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'uri': os.path.relpath(qi.get('file', ''), project_path)
                                if qi.get('file') else 'unknown',
                    },
                    'region': {
                        'startLine': qi.get('line', 1),
                    },
                },
            }],
        })

    # Convert TODOs to SARIF
    for todo in analysis.get('todos', [])[:50]:
        rule_id = 'codevista-todo'
        if rule_id not in seen_rules:
            seen_rules.add(rule_id)
            rules.append({
                'id': rule_id,
                'name': 'TODO/FIXME/HACK',
                'shortDescription': {'text': 'TODO/FIXME/HACK comment found'},
                'fullDescription': {'text': 'Technical debt markers found in code.'},
                'properties': {'category': 'Technical Debt'},
                'defaultConfiguration': {'level': 'note'},
            })

        results.append({
            'ruleId': rule_id,
            'level': 'note',
            'message': {'text': f'{todo.get("tag", "TODO")}: {todo.get("text", "")}'},
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'uri': 'unknown',
                    },
                    'region': {
                        'startLine': todo.get('line', 1),
                    },
                },
            }],
        })

    sarif = {
        '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
        'version': '2.1.0',
        'runs': [{
            'tool': {
                'driver': {
                    'name': 'CodeVista',
                    'version': '1.0.0',
                    'informationUri': 'https://github.com',
                    'rules': rules,
                },
            },
            'invocations': [{
                'executionSuccessful': True,
                'startTimeUtc': now,
                'endTimeUtc': now,
            }],
            'results': results,
            'columnKind': 'utf16CodeUnits',
        }],
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sarif, f, indent=2)

    return path


# ── CSV Export ──────────────────────────────────────────────────────────────

def export_csv(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export file metrics as CSV."""
    path = output_path if output_path.endswith('.csv') else output_path + '.csv'

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'File', 'Language', 'Total Lines', 'Code Lines', 'Comment Lines',
            'Blank Lines', 'Complexity', 'Maintainability Index',
            'Functions', 'Size (bytes)', 'Comment Ratio', 'Import Count',
            'TODOs', 'Quality Issues',
        ])

        for fd in analysis.get('files', []):
            lc = fd.get('lines', {})
            writer.writerow([
                fd['path'],
                fd.get('language', ''),
                lc.get('total', 0),
                lc.get('code', 0),
                lc.get('comment', 0),
                lc.get('blank', 0),
                fd.get('complexity', 0),
                fd.get('maintainability_index', 0),
                fd.get('function_count', 0),
                fd.get('size', 0),
                round(fd.get('comment_ratio', 0), 4),
                fd.get('import_count', 0),
                len(fd.get('todos', [])),
                len(fd.get('quality_issues', [])),
            ])

    return path


# ── CODE_METRICS.yaml Export ───────────────────────────────────────────────

def export_code_metrics_yaml(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export in GitHub CODE_METRICS.yaml format."""
    path = output_path if output_path.endswith('.yaml') else output_path + '.yaml'

    lines = [
        '# Code Metrics Report',
        f'# Generated by CodeVista on {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'# Project: {analysis.get("project_name", "Unknown")}',
        '',
        f'project: {analysis.get("project_name", "Unknown")}',
        f'files_total: {analysis["total_files"]}',
        f'lines_of_code: {analysis["total_lines"]["code"]}',
        f'lines_of_comments: {analysis["total_lines"]["comment"]}',
        f'lines_of_blank: {analysis["total_lines"]["blank"]}',
        f'languages_count: {len(analysis["languages"])}',
        f'functions_count: {len(analysis.get("functions", []))}',
        f'avg_complexity: {analysis["avg_complexity"]:.1f}',
        f'max_complexity: {analysis["max_complexity"]}',
        f'dependencies_count: {len(analysis["dependencies"])}',
        f'security_issues_count: {len(analysis["security_issues"])}',
        '',
    ]

    # Health scores
    scores = calculate_health(analysis)
    lines.extend([
        'health_scores:',
        f'  overall: {scores["overall"]}',
        f'  readability: {scores.get("readability", 0)}',
        f'  complexity: {scores.get("complexity", 0)}',
        f'  duplication: {scores.get("duplication", 0)}',
        f'  coverage: {scores.get("coverage", 0)}',
        f'  security: {scores.get("security", 0)}',
        f'  dependencies: {scores.get("dependencies", 0)}',
        f'  maintainability: {scores.get("maintainability", 0)}',
        '',
    ])

    # Languages
    lines.append('languages:')
    for lang, count in sorted(analysis['languages'].items(), key=lambda x: -x[1]):
        total = sum(analysis['languages'].values()) or 1
        pct = round(count / total * 100, 1)
        lines.append(f'  {lang}: {count} ({pct}%)')
    lines.append('')

    # Top complex functions
    top_funcs = analysis.get('top_complex_functions', [])[:20]
    if top_funcs:
        lines.append('top_complex_functions:')
        for f in top_funcs:
            fname = f.get('file', '').split('/')[-1] if f.get('file') else ''
            lines.append(
                f'  - name: "{f["name"]}"\n'
                f'    file: "{fname}"\n'
                f'    complexity: {f["complexity"]}\n'
                f'    cognitive_complexity: {f.get("cognitive_complexity", 0)}\n'
                f'    lines: {f["line_count"]}\n'
                f'    params: {f.get("param_count", 0)}'
            )
        lines.append('')

    # Frameworks
    frameworks = analysis.get('frameworks', [])
    if frameworks:
        lines.append('frameworks:')
        for fw in frameworks:
            lines.append(f'  - {fw}')
        lines.append('')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return path


# ── PDF Export (HTML → PDF) ────────────────────────────────────────────────

def export_pdf(analysis: Dict[str, Any], output_path: str, **kwargs) -> str:
    """Export as PDF via wkhtmltopdf if available, else fallback to HTML."""
    import tempfile
    import subprocess

    # First generate HTML
    html_path = kwargs.get('html_path')
    if not html_path:
        html_fd, html_path = tempfile.mkstemp(suffix='.html')
        os.close(html_fd)
        export_html(analysis, html_path)

    pdf_path = output_path if output_path.endswith('.pdf') else output_path + '.pdf'

    # Try wkhtmltopdf
    try:
        result = subprocess.run(
            ['wkhtmltopdf', '--quiet', '--enable-local-file-access',
             '--print-media-type', html_path, pdf_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and os.path.isfile(pdf_path):
            return pdf_path
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Try weasyprint
    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(pdf_path)
        if os.path.isfile(pdf_path):
            return pdf_path
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: return the HTML file with a note
    final_path = output_path if output_path.endswith('.html') else output_path + '.html'
    import shutil
    shutil.copy2(html_path, final_path)
    return final_path


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_json_serializable(obj: Any, max_depth: int = 10) -> Any:
    """Recursively convert non-serializable types for JSON export."""
    if max_depth <= 0:
        return str(obj)

    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v, max_depth - 1) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v, max_depth - 1) for v in obj]
    elif isinstance(obj, (set, frozenset)):
        return list(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', errors='replace')
    elif hasattr(obj, '__dict__'):
        return _make_json_serializable(obj.__dict__, max_depth - 1)
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    return obj
