"""Trend analysis — track code quality over time with snapshots.

Save analysis snapshots with timestamps, compare snapshots, show trend arrows,
project health timeline (ASCII art), threshold alerts, code age distribution,
technical debt ratio tracking, and optimal review cadence suggestions.
"""

import json
import os
import sys
import math
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

SNAPSHOTS_DIR = os.path.expanduser('~/.codevista/snapshots')


def _ensure_snapshots_dir():
    """Create snapshots directory if it doesn't exist."""
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def save_snapshot(analysis: Dict[str, Any], project_path: str,
                  label: str = None) -> str:
    """Save an analysis snapshot with timestamp.

    Returns the snapshot file path.
    """
    _ensure_snapshots_dir()
    project_name = os.path.basename(os.path.abspath(project_path))
    safe_name = project_name.replace('/', '_').replace('\\', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    label_suffix = f'_{label}' if label else ''
    filename = f'{safe_name}_{timestamp}{label_suffix}.json'
    filepath = os.path.join(SNAPSHOTS_DIR, filename)

    from .metrics import calculate_health
    scores = calculate_health(analysis)

    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'project': project_name,
        'project_path': os.path.abspath(project_path),
        'label': label or '',
        'scores': scores,
        'total_files': analysis.get('total_files', 0),
        'total_lines': analysis.get('total_lines', {}),
        'avg_complexity': analysis.get('avg_complexity', 0),
        'max_complexity': analysis.get('max_complexity', 0),
        'languages': analysis.get('languages', {}),
        'security_issues_count': len(analysis.get('security_issues', [])),
        'security_issues': [
            {'severity': i['severity'], 'name': i['name'], 'file': i['file']}
            for i in analysis.get('security_issues', [])[:50]
        ],
        'dependencies_count': len(analysis.get('dependencies', [])),
        'function_count': len(analysis.get('functions', [])),
        'duplicate_count': len(analysis.get('duplicates', [])),
        'todo_count': len(analysis.get('todos', [])),
        'circular_deps_count': len(analysis.get('circular_deps', [])),
        'has_git': analysis.get('git') is not None,
    }

    # Add git-specific metrics
    if analysis.get('git'):
        git = analysis['git']
        snapshot['git_total_commits'] = git.get('total_commits', 0)
        snapshot['git_contributors'] = len(git.get('authors', []))
        snapshot['git_bus_factor'] = git.get('bus_factor', {}).get('factor', 0)
        churn = git.get('code_churn', {})
        snapshot['git_churn_added'] = churn.get('added', 0)
        snapshot['git_churn_removed'] = churn.get('removed', 0)

    # Add code age distribution
    snapshot['code_age_distribution'] = _compute_code_age_dist(analysis)

    # Add complexity distribution
    snapshot['complexity_distribution'] = analysis.get('complexity_distribution', {})

    # Add size distribution
    snapshot['size_distribution'] = analysis.get('size_distribution', {})

    # Technical debt ratio
    snapshot['technical_debt_ratio'] = _compute_tech_debt_ratio(analysis, scores)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, default=str)

    return filepath


def load_snapshots(project_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Load all snapshots for a project, newest first."""
    _ensure_snapshots_dir()
    project_name = os.path.basename(os.path.abspath(project_path))
    safe_name = project_name.replace('/', '_').replace('\\', '_')

    snapshots = []
    for fname in sorted(os.listdir(SNAPSHOTS_DIR), reverse=True):
        if not fname.startswith(safe_name) or not fname.endswith('.json'):
            continue
        filepath = os.path.join(SNAPSHOTS_DIR, fname)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                snapshots.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
        if len(snapshots) >= limit:
            break

    return snapshots


def list_snapshots(project_path: str) -> List[Dict[str, Any]]:
    """List snapshots with minimal info."""
    _ensure_snapshots_dir()
    project_name = os.path.basename(os.path.abspath(project_path))
    safe_name = project_name.replace('/', '_').replace('\\', '_')

    results = []
    for fname in sorted(os.listdir(SNAPSHOTS_DIR), reverse=True):
        if not fname.startswith(safe_name) or not fname.endswith('.json'):
            continue
        filepath = os.path.join(SNAPSHOTS_DIR, fname)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            results.append({
                'file': filepath,
                'timestamp': data.get('timestamp', ''),
                'label': data.get('label', ''),
                'overall_score': data.get('scores', {}).get('overall', 0),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return results


def compare_snapshots(snapshot_a: Dict, snapshot_b: Dict) -> Dict[str, Any]:
    """Compare two snapshots and return differences with trend arrows."""
    comparison = {
        'timestamp_a': snapshot_a.get('timestamp', ''),
        'timestamp_b': snapshot_b.get('timestamp', ''),
        'label_a': snapshot_a.get('label', ''),
        'label_b': snapshot_b.get('label', ''),
        'metric_changes': [],
        'alerts': [],
        'improved': 0,
        'degraded': 0,
        'stable': 0,
    }

    # Compare scores
    scores_a = snapshot_a.get('scores', {})
    scores_b = snapshot_b.get('scores', {})
    score_keys = ['overall', 'readability', 'complexity', 'duplication',
                  'coverage', 'security', 'dependencies', 'maintainability']

    for key in score_keys:
        val_a = scores_a.get(key, 0)
        val_b = scores_b.get(key, 0)
        diff = val_b - val_a
        arrow, trend = _trend_arrow(diff)
        change = {
            'metric': key.replace('_', ' ').title(),
            'old_value': val_a,
            'new_value': val_b,
            'diff': diff,
            'arrow': arrow,
            'trend': trend,
        }
        comparison['metric_changes'].append(change)

        # Track counts
        if trend == 'improving':
            comparison['improved'] += 1
        elif trend == 'degrading':
            comparison['degraded'] += 1
        else:
            comparison['stable'] += 1

    # Compare numeric metrics
    numeric_metrics = [
        ('Total Files', 'total_files', True),
        ('Lines of Code', 'total_lines.code', True),
        ('Avg Complexity', 'avg_complexity', False),
        ('Max Complexity', 'max_complexity', False),
        ('Security Issues', 'security_issues_count', False),
        ('Dependencies', 'dependencies_count', False),
        ('Functions', 'function_count', True),
        ('Duplicates', 'duplicate_count', False),
        ('TODOs', 'todo_count', False),
        ('Circular Deps', 'circular_deps_count', False),
        ('Tech Debt Ratio', 'technical_debt_ratio', False),
    ]

    for label, key, higher_is_better in numeric_metrics:
        val_a = _get_nested(snapshot_a, key)
        val_b = _get_nested(snapshot_b, key)
        if val_a is None or val_b is None:
            continue
        diff = val_b - val_a
        if not higher_is_better:
            diff = -diff  # Invert for security issues, complexity, etc.
        if abs(diff) < 0.01:
            arrow, trend = '→', 'stable'
        elif diff > 0:
            arrow, trend = '↑', 'improving'
        else:
            arrow, trend = '↓', 'degrading'
        comparison['metric_changes'].append({
            'metric': label,
            'old_value': val_a,
            'new_value': val_b,
            'diff': val_b - val_a,
            'arrow': arrow,
            'trend': trend,
        })

    # Generate alerts for threshold crossings
    comparison['alerts'] = _generate_threshold_alerts(snapshot_a, snapshot_b)

    return comparison


def format_trends_terminal(snapshots: List[Dict[str, Any]]) -> str:
    """Format trend analysis as a terminal-friendly string."""
    if len(snapshots) < 1:
        return '❌ No snapshots found. Run `codevista snapshot ./project` first.\n'

    lines = []
    lines.append(f"\n{'═'*60}")
    lines.append(f"  📈 CodeVista Trend Analysis")
    lines.append(f"  {snapshots[0].get('project', 'Unknown Project')}")
    lines.append(f"  {len(snapshots)} snapshot(s) available")
    lines.append(f"{'═'*60}")

    # Latest snapshot summary
    latest = snapshots[0]
    lines.append(f"\n  📅 Latest: {latest.get('timestamp', '?')}")
    if latest.get('label'):
        lines.append(f"  🏷️  Label: {latest['label']}")
    scores = latest.get('scores', {})
    overall = scores.get('overall', 0)
    icon = '✅' if overall >= 80 else '⚠️' if overall >= 50 else '❌'
    lines.append(f"  {icon} Health Score: {overall}/100")

    # Score breakdown
    lines.append(f"\n  {'Category':<18s} {'Score':>6s}  {'Trend'}")
    lines.append(f"  {'─'*35}")
    for cat in ('readability', 'complexity', 'duplication', 'coverage',
                'security', 'dependencies', 'maintainability'):
        val = scores.get(cat, 0)
        arrow = '→'
        if len(snapshots) >= 2:
            prev = snapshots[1].get('scores', {}).get(cat, val)
            diff = val - prev
            if diff > 2:
                arrow = '↑'
            elif diff < -2:
                arrow = '↓'
        icon_cat = '✅' if val >= 80 else '⚠️' if val >= 50 else '❌'
        bar_len = val // 5
        bar = '█' * bar_len + '░' * (20 - bar_len)
        lines.append(f"  {icon_cat} {cat.replace('_',' ').title():<16s} {val:>3d}/100 [{bar}] {arrow}")

    # Comparison with previous
    if len(snapshots) >= 2:
        comp = compare_snapshots(snapshots[1], snapshots[0])
        lines.append(f"\n  📊 Changes since {comp['timestamp_a'][:16]}")
        lines.append(f"  {'─'*50}")
        for mc in comp['metric_changes']:
            lines.append(
                f"    {mc['arrow']} {mc['metric']:<22s} "
                f"{mc['old_value']!s:>8s} → {mc['new_value']!s:>8s}"
            )
        lines.append(f"\n  Summary: {comp['improved']} improved, "
                     f"{comp['degraded']} degraded, {comp['stable']} stable")

        if comp['alerts']:
            lines.append(f"\n  🚨 Alerts:")
            for alert in comp['alerts'][:10]:
                lines.append(f"    {alert['icon']} {alert['message']}")

    # ASCII timeline chart
    if len(snapshots) >= 2:
        lines.append(format_timeline_ascii(snapshots))

    # Technical debt trend
    lines.append(format_tech_debt_trend(snapshots))

    # Review cadence suggestion
    lines.append(format_review_cadence(snapshots))

    # All snapshots list
    lines.append(f"\n  📋 Available Snapshots:")
    lines.append(f"  {'─'*55}")
    for i, snap in enumerate(snapshots[:15]):
        score = snap.get('scores', {}).get('overall', 0)
        label = f" ({snap['label']})" if snap.get('label') else ''
        lines.append(f"    {i+1:>2d}. [{score:>3d}/100] {snap.get('timestamp','?')[:19]}{label}")

    return '\n'.join(lines) + '\n'


def format_comparison_terminal(comparison: Dict[str, Any]) -> str:
    """Format a snapshot comparison for terminal output."""
    lines = []
    lines.append(f"\n{'═'*60}")
    lines.append(f"  📊 Snapshot Comparison")
    if comparison.get('label_a'):
        lines.append(f"  {comparison['label_a']} vs {comparison['label_b']}")
    else:
        lines.append(f"  {comparison['timestamp_a'][:19]} vs {comparison['timestamp_b'][:19]}")
    lines.append(f"{'═'*60}")

    lines.append(f"\n  {'Metric':<22s} {'Before':>8s} {'After':>8s}  {'Change'}")
    lines.append(f"  {'─'*50}")
    for mc in comparison['metric_changes']:
        old_v = mc['old_value']
        new_v = mc['new_value']
        diff = mc['diff']
        if isinstance(old_v, (int, float)) and isinstance(new_v, (int, float)):
            sign = '+' if diff >= 0 else ''
            change_str = f"{sign}{diff:.1f}" if isinstance(diff, float) else f"{sign}{diff}"
        else:
            change_str = str(diff)
        lines.append(
            f"  {mc['arrow']} {mc['metric']:<20s} "
            f"{str(old_v):>8s} {str(new_v):>8s}  {change_str}"
        )

    summary = (f"\n  ✅ {comparison['improved']} improved  "
               f"❌ {comparison['degraded']} degraded  "
               f"➡️  {comparison['stable']} stable")

    lines.append(summary)

    if comparison['alerts']:
        lines.append(f"\n  🚨 Threshold Alerts:")
        for alert in comparison['alerts'][:15]:
            lines.append(f"    {alert['icon']} {alert['message']}")

    return '\n'.join(lines) + '\n'


def format_timeline_ascii(snapshots: List[Dict[str, Any]]) -> str:
    """Generate an ASCII art timeline chart of health scores over time."""
    lines = []
    lines.append(f"\n  📈 Health Score Timeline")

    # Only use last 20 snapshots for display
    display = snapshots[:20][::-1]  # oldest first

    if len(display) < 2:
        lines.append("  (need at least 2 snapshots)")
        return '\n'.join(lines)

    chart_height = 12
    chart_width = min(len(display), 60)

    # Use last chart_width snapshots
    data = display[-chart_width:]
    scores = [s.get('scores', {}).get('overall', 0) for s in data]

    # Draw chart
    lines.append("  100 ┤")
    for row in range(chart_height):
        threshold = 100 - (row * (100 / chart_height))
        label = f"{int(threshold):>3d} ┤"
        row_str = ''
        for score in scores:
            if score >= threshold:
                row_str += '█'
            else:
                row_str += ' '
        lines.append(f"  {label} {row_str}")

    lines.append("    0 ┤{'─' * len(scores)}")

    # Time labels
    dates = []
    step = max(1, len(data) // 5)
    for i in range(0, len(data), step):
        ts = data[i].get('timestamp', '')[:10]
        dates.append((i, ts))

    if len(dates) > 1:
        line = '       '
        pos = 0
        for i, (idx, ts) in enumerate(dates):
            # Approximate position
            while len(line) < idx + 7:
                line += ' '
            line = line[:idx + 7] + ts[-2:]
        lines.append(f"  {line}")

    # Latest value
    if scores:
        latest = scores[-1]
        arrow = '↑' if len(scores) >= 2 and latest > scores[-2] else '↓' if len(scores) >= 2 and latest < scores[-2] else '→'
        lines.append(f"\n  Current: {latest}/100 {arrow}")

    return '\n'.join(lines)


def format_tech_debt_trend(snapshots: List[Dict[str, Any]]) -> str:
    """Show technical debt ratio trend."""
    lines = []
    lines.append(f"\n  🔧 Technical Debt Trend")

    display = snapshots[:10]
    if len(display) < 1:
        lines.append("  (no data)")
        return '\n'.join(lines)

    for snap in display:
        ratio = snap.get('technical_debt_ratio', 0)
        ts = snap.get('timestamp', '')[:16]
        label = snap.get('label', '')
        pct = f"{ratio:.1%}" if isinstance(ratio, (int, float)) else str(ratio)

        # Visual bar
        bar_len = min(int(ratio * 30), 30)
        if ratio < 0.1:
            color = '🟢'
        elif ratio < 0.25:
            color = '🟡'
        elif ratio < 0.5:
            color = '🟠'
        else:
            color = '🔴'

        bar = '█' * bar_len + '░' * (30 - bar_len)
        label_str = f" ({label})" if label else ''
        lines.append(f"    {color} {ts}{label_str}")
        lines.append(f"       [{bar}] {pct}")

    return '\n'.join(lines)


def format_review_cadence(snapshots: List[Dict[str, Any]]) -> str:
    """Suggest optimal review cadence based on change rate."""
    lines = []
    lines.append(f"\n  📅 Recommended Review Cadence")

    if len(snapshots) < 2:
        lines.append("  (need at least 2 snapshots to calculate)")
        return '\n'.join(lines)

    # Calculate time between snapshots
    times = []
    for s in snapshots[:10]:
        try:
            ts = datetime.fromisoformat(s.get('timestamp', ''))
            times.append(ts)
        except (ValueError, TypeError):
            continue

    if len(times) < 2:
        lines.append("  (could not parse timestamps)")
        return '\n'.join(lines)

    # Calculate rate of change
    latest = snapshots[0]
    prev = snapshots[1]
    score_change = abs(
        latest.get('scores', {}).get('overall', 0) -
        prev.get('scores', {}).get('overall', 0)
    )
    loc_change = abs(
        _get_nested(latest, 'total_lines.code', 0) -
        _get_nested(prev, 'total_lines.code', 0)
    )
    new_issues = (
        latest.get('security_issues_count', 0) -
        prev.get('security_issues_count', 0)
    )

    # Determine cadence
    tech_debt = latest.get('technical_debt_ratio', 0)
    overall = latest.get('scores', {}).get('overall', 100)

    if score_change > 10 or new_issues > 3 or tech_debt > 0.5:
        cadence = "Weekly — high volatility detected"
        icon = "🔴"
    elif score_change > 5 or loc_change > 500 or tech_debt > 0.25:
        cadence = "Bi-weekly — moderate changes"
        icon = "🟡"
    elif overall < 60:
        cadence = "Weekly — health score needs attention"
        icon = "🟠"
    elif tech_debt < 0.1 and score_change < 2:
        cadence = "Monthly — project is stable"
        icon = "🟢"
    else:
        cadence = "Bi-weekly — standard monitoring"
        icon = "🔵"

    lines.append(f"  {icon} {cadence}")
    lines.append(f"     Score delta: {score_change:+d}")
    lines.append(f"     LoC delta:   {loc_change:+,}")
    lines.append(f"     New issues:  {new_issues:+d}")
    lines.append(f"     Tech debt:   {tech_debt:.1%}" if isinstance(tech_debt, (int, float)) else f"     Tech debt:   {tech_debt}")

    return '\n'.join(lines)


def format_code_age_dist_terminal(snapshots: List[Dict[str, Any]]) -> str:
    """Show code age distribution changes over time."""
    lines = []
    lines.append(f"\n  📅 Code Age Distribution Changes")

    display = snapshots[:5]
    if not display:
        return "  (no data)\n"

    # Headers
    cats = ['hot', 'warm', 'cold', 'cold_stable', 'dead']
    cat_labels = {'hot': '🔥 Hot', 'warm': '🌤️ Warm', 'cold': '❄️ Cold',
                  'cold_stable': '🧊 Stable', 'dead': '💀 Dead'}
    header = f"  {'Snapshot':<20s}"
    for cat in cats:
        header += f" {cat_labels.get(cat, cat):>8s}"
    lines.append(header)
    lines.append(f"  {'─'*65}")

    for snap in display:
        ts = snap.get('timestamp', '')[:16]
        dist = snap.get('code_age_distribution', {})
        row = f"  {ts:<20s}"
        for cat in cats:
            val = dist.get(cat, 0)
            row += f" {val:>8d}"
        lines.append(row)

    return '\n'.join(lines) + '\n'


# ── Internal helpers ──────────────────────────────────────────────────────

def _trend_arrow(diff: float) -> Tuple[str, str]:
    """Get trend arrow and label for a numeric difference."""
    if abs(diff) < 0.5:
        return '→', 'stable'
    elif diff > 0:
        return '↑', 'improving'
    else:
        return '↓', 'degrading'


def _get_nested(data: Dict, key: str, default=None):
    """Get a nested value using dot notation."""
    keys = key.split('.')
    obj = data
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, default)
        else:
            return default
        if obj is default:
            return default
    return obj


def _generate_threshold_alerts(old_snap: Dict, new_snap: Dict) -> List[Dict]:
    """Generate alerts when metrics cross important thresholds."""
    alerts = []
    new_scores = new_snap.get('scores', {})
    old_scores = old_snap.get('scores', {})

    # Health score alerts
    new_overall = new_scores.get('overall', 100)
    old_overall = old_scores.get('overall', 100)

    if old_overall >= 70 and new_overall < 70:
        alerts.append({
            'icon': '🚨', 'severity': 'critical',
            'message': f'Overall health dropped below 70 ({new_overall}/100)',
        })
    if old_overall >= 50 and new_overall < 50:
        alerts.append({
            'icon': '💀', 'severity': 'critical',
            'message': f'Overall health dropped below 50 ({new_overall}/100) — critical!',
        })

    # Security score alerts
    new_sec = new_scores.get('security', 100)
    old_sec = old_scores.get('security', 100)
    if old_sec >= 70 and new_sec < 70:
        alerts.append({
            'icon': '🔒', 'severity': 'high',
            'message': f'Security score dropped below 70 ({new_sec}/100)',
        })

    # Complexity alerts
    new_avg_cc = new_snap.get('avg_complexity', 0)
    old_avg_cc = old_snap.get('avg_complexity', 0)
    if old_avg_cc <= 10 and new_avg_cc > 10:
        alerts.append({
            'icon': '⚡', 'severity': 'warning',
            'message': f'Average complexity rose above 10 ({new_avg_cc:.1f})',
        })
    if new_avg_cc > 20:
        alerts.append({
            'icon': '⚡', 'severity': 'critical',
            'message': f'Average complexity very high ({new_avg_cc:.1f})',
        })

    # Dependency count alerts
    new_deps = new_snap.get('dependencies_count', 0)
    if new_deps > 50:
        alerts.append({
            'icon': '📦', 'severity': 'warning',
            'message': f'High dependency count ({new_deps}) — consider auditing',
        })

    # Security issues alerts
    new_sec_issues = new_snap.get('security_issues_count', 0)
    old_sec_issues = old_snap.get('security_issues_count', 0)
    if new_sec_issues > old_sec_issues + 5:
        alerts.append({
            'icon': '🔓', 'severity': 'high',
            'message': f'{new_sec_issues - old_sec_issues} new security issues detected',
        })
    if new_sec_issues > 0 and old_sec_issues == 0:
        alerts.append({
            'icon': '🔓', 'severity': 'warning',
            'message': f'First security issues detected ({new_sec_issues})',
        })

    # Circular dependency alerts
    new_circ = new_snap.get('circular_deps_count', 0)
    old_circ = old_snap.get('circular_deps_count', 0)
    if old_circ == 0 and new_circ > 0:
        alerts.append({
            'icon': '🔄', 'severity': 'warning',
            'message': f'New circular dependencies detected ({new_circ})',
        })

    # Deterioration alerts for score categories
    for cat in ('readability', 'maintainability', 'coverage'):
        old_v = old_scores.get(cat, 100)
        new_v = new_scores.get(cat, 100)
        if old_v - new_v >= 15:
            alerts.append({
                'icon': '📉', 'severity': 'warning',
                'message': f'{cat.title()} dropped by {old_v - new_v} points ({old_v} → {new_v})',
            })

    return alerts


def _compute_tech_debt_ratio(analysis: Dict, scores: Dict) -> float:
    """Compute technical debt ratio (0.0 - 1.0)."""
    total = analysis.get('total_lines', {}).get('total', 0)
    if total == 0:
        return 0.0

    todo_count = len(analysis.get('todos', []))
    dup_count = len(analysis.get('duplicates', []))
    high_cc = sum(1 for f in analysis.get('functions', [])
                  if f.get('complexity', 0) > 15)
    long_funcs = sum(1 for f in analysis.get('functions', [])
                     if f.get('line_count', 0) > 50)
    deep_nest = sum(1 for f in analysis.get('functions', [])
                    if f.get('nesting_depth', 0) > 4)
    many_args = sum(1 for f in analysis.get('functions', [])
                    if f.get('param_count', 0) > 5)
    sec_issues = len(analysis.get('security_issues', []))
    circ_deps = len(analysis.get('circular_deps', []))
    func_count = max(len(analysis.get('functions', [])), 1)

    # Weighted debt items per 1000 lines
    kloc = total / 1000
    debt_per_kloc = (
        todo_count * 0.5 +
        dup_count * 0.3 +
        high_cc * 1.0 +
        long_funcs * 0.4 +
        deep_nest * 0.6 +
        many_args * 0.3 +
        sec_issues * 1.5 +
        circ_deps * 2.0
    ) / max(kloc, 0.1)

    # Normalize: 0 debt items/kloc = 0%, 10+ = 100%
    ratio = min(debt_per_kloc / 10.0, 1.0)
    return round(ratio, 4)


def _compute_code_age_dist(analysis: Dict) -> Dict[str, int]:
    """Compute code age distribution from git data."""
    dist = {'hot': 0, 'warm': 0, 'cold': 0, 'cold_stable': 0, 'dead': 0}

    git = analysis.get('git')
    if not git:
        return dist

    from datetime import datetime
    now = datetime.now()

    active_files = git.get('active_files', [])
    for file_info in active_files[:100]:
        # Use commit count as a proxy for activity
        commits = file_info.get('commits', 0)
        if commits >= 20:
            dist['hot'] += 1
        elif commits >= 10:
            dist['warm'] += 1
        elif commits >= 3:
            dist['cold'] += 1
        elif commits >= 1:
            dist['cold_stable'] += 1
        else:
            dist['dead'] += 1

    return dist


def delete_snapshot(project_path: str, index: int) -> bool:
    """Delete a snapshot by index (1-based)."""
    snaps = list_snapshots(project_path)
    if index < 1 or index > len(snaps):
        return False
    filepath = snaps[index - 1]['file']
    try:
        os.remove(filepath)
        return True
    except OSError:
        return False


def delete_all_snapshots(project_path: str) -> int:
    """Delete all snapshots for a project. Returns count deleted."""
    snaps = list_snapshots(project_path)
    count = 0
    for snap in snaps:
        try:
            os.remove(snap['file'])
            count += 1
        except OSError:
            pass
    return count
