"""Code Age Analysis — tracks file age, change frequency, and risk correlation.

Analyzes git history to determine file age, identify dead/hot/cold files,
and correlate age × complexity × churn to identify files most likely to have bugs.
"""

import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from .utils import read_file_safe, cyclomatic_complexity
from .languages import detect_language


# ── Configuration ───────────────────────────────────────────────────────────

AGE_THRESHOLDS = {
    'hot_days': 7,           # Changed in last 7 days
    'warm_days': 30,         # Changed in last 30 days
    'cold_days_min': 30,     # Cold: 30-365 days
    'cold_days_max': 365,    # Cold upper bound
    'dead_days': 365,        # Dead: unchanged > 365 days
    'ancient_days': 730,     # Ancient: > 2 years
}


# ── Main Analysis Entry Point ──────────────────────────────────────────────

def analyze_code_age(project_path: str,
                     files_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Analyze code age and change patterns across the project.

    Args:
        project_path: Absolute path to the project root.
        files_data: Optional pre-loaded file analysis data.

    Returns:
        Dict with 'file_ages', 'categories', 'risk_analysis', 'histogram',
        'statistics', 'correlation'.
    """
    project_path = os.path.abspath(project_path)

    # Check if git is available
    is_git = os.path.isdir(os.path.join(project_path, '.git'))

    if is_git:
        return _analyze_with_git(project_path, files_data)
    else:
        return _analyze_without_git(project_path, files_data)


# ── Git-Based Analysis ─────────────────────────────────────────────────────

def _analyze_with_git(project_path: str,
                       files_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Analyze code age using git history."""
    # Get all tracked files with their last commit dates
    file_dates = _get_git_file_dates(project_path)

    # Get commit counts per file (churn)
    file_commits = _get_git_file_commits(project_path)

    # Get file size history
    file_sizes = _get_git_file_sizes(project_path)

    # Get current files if not provided
    if files_data is None:
        files_data = _build_files_data(project_path, file_dates)

    # Build file age data
    file_ages = []
    now = datetime.now()

    for fd in files_data:
        rel = fd.get('path', '')
        if not rel:
            continue

        date_info = file_dates.get(rel, {})
        commit_count = file_commits.get(rel, 0)
        current_size = file_sizes.get(rel, fd.get('size', 0))

        last_modified = date_info.get('date', now)
        first_commit = date_info.get('first_commit', now)
        age_days = (now - last_modified).days
        total_age_days = (now - first_commit).days

        complexity = fd.get('complexity', 0)
        loc = fd.get('lines', {}).get('total', 0) if isinstance(fd.get('lines'), dict) else 0

        # Calculate change rate (commits per month of age)
        age_months = max(total_age_days / 30, 1)
        change_rate = commit_count / age_months

        # Categorize
        category = _categorize_file(age_days, commit_count)

        file_ages.append({
            'file': rel,
            'language': fd.get('language', 'Unknown'),
            'last_modified': last_modified.strftime('%Y-%m-%d') if isinstance(last_modified, datetime) else str(last_modified),
            'first_commit': first_commit.strftime('%Y-%m-%d') if isinstance(first_commit, datetime) else str(first_commit),
            'age_days': age_days,
            'total_age_days': total_age_days,
            'commit_count': commit_count,
            'change_rate': round(change_rate, 2),
            'complexity': complexity,
            'loc': loc,
            'size': current_size,
            'category': category,
        })

    # Sort by age
    file_ages.sort(key=lambda x: x['age_days'], reverse=True)

    # Calculate categories
    categories = _calculate_categories(file_ages)

    # Risk analysis: age × complexity × churn
    risk_analysis = _calculate_risk_analysis(file_ages)

    # Age histogram
    histogram = _build_age_histogram(file_ages)

    # Correlation analysis
    correlation = _calculate_correlation(file_ages)

    # Statistics
    statistics = _calculate_statistics(file_ages)

    return {
        'file_ages': file_ages,
        'categories': categories,
        'risk_analysis': risk_analysis,
        'histogram': histogram,
        'correlation': correlation,
        'statistics': statistics,
        'is_git': True,
    }


# ── Fallback: No Git ───────────────────────────────────────────────────────

def _analyze_without_git(project_path: str,
                          files_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Analyze code age using file modification times (no git)."""
    now = datetime.now()

    if files_data is None:
        files_data = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ('node_modules', '__pycache__', '.git', 'vendor', 'build', 'dist')]
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, project_path)
                lang = detect_language(fpath)
                mtime = os.path.getmtime(fpath)
                files_data.append({
                    'path': rel,
                    'language': lang or 'Unknown',
                    'size': os.path.getsize(fpath),
                    'complexity': 0,
                    'lines': {'total': 0, 'code': 0},
                    '_mtime': mtime,
                })

    file_ages = []
    for fd in files_data:
        rel = fd.get('path', '')
        mtime = fd.get('_mtime', 0)
        mod_date = datetime.fromtimestamp(mtime)
        age_days = (now - mod_date).days

        category = _categorize_file(age_days, 0)

        file_ages.append({
            'file': rel,
            'language': fd.get('language', 'Unknown'),
            'last_modified': mod_date.strftime('%Y-%m-%d'),
            'first_commit': mod_date.strftime('%Y-%m-%d'),
            'age_days': age_days,
            'total_age_days': age_days,
            'commit_count': 0,
            'change_rate': 0,
            'complexity': fd.get('complexity', 0),
            'loc': fd.get('lines', {}).get('total', 0) if isinstance(fd.get('lines'), dict) else 0,
            'size': fd.get('size', 0),
            'category': category,
        })

    file_ages.sort(key=lambda x: x['age_days'], reverse=True)
    categories = _calculate_categories(file_ages)
    risk_analysis = _calculate_risk_analysis(file_ages)
    histogram = _build_age_histogram(file_ages)
    correlation = _calculate_correlation(file_ages)
    statistics = _calculate_statistics(file_ages)

    return {
        'file_ages': file_ages,
        'categories': categories,
        'risk_analysis': risk_analysis,
        'histogram': histogram,
        'correlation': correlation,
        'statistics': statistics,
        'is_git': False,
    }


# ── Git Data Extraction ────────────────────────────────────────────────────

def _get_git_file_dates(project_path: str) -> Dict[str, Dict]:
    """Get last commit date and first commit date for each file."""
    result: Dict[str, Dict] = {}

    # Get last modification dates
    try:
        proc = subprocess.run(
            ['git', 'log', '-1', '--name-only', '--format=%aI', '--', '*.py', '*.js', '*.ts',
             '*.jsx', '*.tsx', '*.java', '*.go', '*.rs', '*.rb', '*.php', '*.cs', '*.kt',
             '*.c', '*.cpp', '*.h', '*.hpp', '*.swift', '*.vue', '*.svelte'],
            cwd=project_path, capture_output=True, text=True, timeout=30
        )
        output = proc.stdout
        current_date = None
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Try parsing as date
            try:
                current_date = datetime.fromisoformat(line.replace('Z', '+00:00')).replace(tzinfo=None)
                continue
            except (ValueError, TypeError):
                pass

            if current_date and line:
                rel = line.strip()
                if rel not in result:
                    result[rel] = {'date': current_date}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Get first commit dates
    try:
        proc = subprocess.run(
            ['git', 'log', '--diff-filter=A', '--follow', '--format=%aI', '--', '*'],
            cwd=project_path, capture_output=True, text=True, timeout=60
        )
        # This gives dates for all additions; not ideal but useful
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Alternative: get dates per file using ls-tree + log
    try:
        proc = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', 'HEAD'],
            cwd=project_path, capture_output=True, text=True, timeout=30
        )
        tracked_files = [f.strip() for f in proc.stdout.split('\n') if f.strip()]

        for rel in tracked_files:
            if rel in result:
                continue
            try:
                proc = subprocess.run(
                    ['git', 'log', '-1', '--format=%aI', '--', rel],
                    cwd=project_path, capture_output=True, text=True, timeout=5
                )
                date_str = proc.stdout.strip()
                if date_str:
                    result[rel] = {'date': datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)}
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Estimate first commit for files without it
    try:
        proc = subprocess.run(
            ['git', 'log', '--reverse', '--format=%aI', '-1'],
            cwd=project_path, capture_output=True, text=True, timeout=10
        )
        first_commit_str = proc.stdout.strip()
        if first_commit_str:
            first_commit = datetime.fromisoformat(first_commit_str.replace('Z', '+00:00')).replace(tzinfo=None)
            for rel, data in result.items():
                if 'first_commit' not in data:
                    data['first_commit'] = first_commit
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fill missing first_commits
    for rel in result:
        if 'first_commit' not in result[rel]:
            result[rel]['first_commit'] = result[rel].get('date', datetime.now())

    return result


def _get_git_file_commits(project_path: str) -> Dict[str, int]:
    """Get number of commits per file."""
    result: Dict[str, int] = {}

    try:
        proc = subprocess.run(
            ['git', 'log', '--name-only', '--format='],
            cwd=project_path, capture_output=True, text=True, timeout=30
        )
        for line in proc.stdout.split('\n'):
            line = line.strip()
            if line:
                result[line] = result.get(line, 0) + 1
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return result


def _get_git_file_sizes(project_path: str) -> Dict[str, int]:
    """Get current file sizes from git."""
    result: Dict[str, int] = {}

    try:
        proc = subprocess.run(
            ['git', 'ls-tree', '-r', '-l', 'HEAD'],
            cwd=project_path, capture_output=True, text=True, timeout=30
        )
        for line in proc.stdout.split('\n'):
            parts = line.split(None, 4)
            if len(parts) >= 4:
                try:
                    size = int(parts[3])
                    filepath = parts[4].strip()
                    result[filepath] = size
                except (ValueError, IndexError):
                    continue
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return result


def _build_files_data(project_path: str, file_dates: Dict[str, Dict]) -> List[Dict]:
    """Build files_data from git-tracked files."""
    files = []
    for rel in file_dates:
        fpath = os.path.join(project_path, rel)
        lang = detect_language(fpath)
        content = read_file_safe(fpath)

        lines = {'total': len(content.split('\n')) if content else 0}
        complexity = 0
        if content and lang:
            complexity = cyclomatic_complexity(content, lang)

        files.append({
            'path': rel,
            'language': lang or 'Unknown',
            'size': os.path.getsize(fpath) if os.path.isfile(fpath) else 0,
            'complexity': complexity,
            'lines': lines,
        })
    return files


# ── File Categorization ────────────────────────────────────────────────────

def _categorize_file(age_days: int, commit_count: int) -> str:
    """Categorize a file by its age and activity."""
    if age_days <= AGE_THRESHOLDS['hot_days']:
        return 'hot'
    elif age_days <= AGE_THRESHOLDS['warm_days']:
        return 'warm'
    elif age_days <= AGE_THRESHOLDS['cold_days_max']:
        if commit_count <= 1:
            return 'cold_stable'
        return 'cold'
    elif age_days <= AGE_THRESHOLDS['ancient_days']:
        if commit_count <= 2:
            return 'dead'
        return 'cold_stable'
    else:
        return 'dead'


def _calculate_categories(file_ages: List[Dict]) -> Dict[str, Any]:
    """Calculate category statistics."""
    category_counts: Counter = Counter()
    category_files: Dict[str, List[str]] = defaultdict(list)
    category_loc: Dict[str, int] = defaultdict(int)

    for fa in file_ages:
        cat = fa['category']
        category_counts[cat] += 1
        category_files[cat].append(fa['file'])
        category_loc[cat] += fa['loc']

    total = len(file_ages)

    return {
        'hot': {
            'count': category_counts.get('hot', 0),
            'pct': round(category_counts.get('hot', 0) / max(total, 1) * 100, 1),
            'files': category_files.get('hot', [])[:20],
            'total_loc': category_loc.get('hot', 0),
            'description': f'Changed in last {AGE_THRESHOLDS["hot_days"]} days',
        },
        'warm': {
            'count': category_counts.get('warm', 0),
            'pct': round(category_counts.get('warm', 0) / max(total, 1) * 100, 1),
            'files': category_files.get('warm', [])[:20],
            'total_loc': category_loc.get('warm', 0),
            'description': f'Changed in last {AGE_THRESHOLDS["warm_days"]} days',
        },
        'cold': {
            'count': category_counts.get('cold', 0),
            'pct': round(category_counts.get('cold', 0) / max(total, 1) * 100, 1),
            'files': category_files.get('cold', [])[:20],
            'total_loc': category_loc.get('cold', 0),
            'description': f'Changed {AGE_THRESHOLDS["cold_days_min"]}-{AGE_THRESHOLDS["cold_days_max"]} days ago',
        },
        'cold_stable': {
            'count': category_counts.get('cold_stable', 0),
            'pct': round(category_counts.get('cold_stable', 0) / max(total, 1) * 100, 1),
            'files': category_files.get('cold_stable', [])[:20],
            'total_loc': category_loc.get('cold_stable', 0),
            'description': 'Old but stable (few changes)',
        },
        'dead': {
            'count': category_counts.get('dead', 0),
            'pct': round(category_counts.get('dead', 0) / max(total, 1) * 100, 1),
            'files': category_files.get('dead', [])[:20],
            'total_loc': category_loc.get('dead', 0),
            'description': f'Unchanged for >{AGE_THRESHOLDS["dead_days"]} days',
        },
    }


# ── Risk Analysis ──────────────────────────────────────────────────────────

def _calculate_risk_analysis(file_ages: List[Dict]) -> Dict[str, Any]:
    """Identify files most likely to have bugs: high age × high complexity × high churn."""
    risk_files = []

    for fa in file_ages:
        age = fa['age_days']
        complexity = fa['complexity']
        commit_count = fa['commit_count']
        loc = fa['loc']

        if loc == 0 or complexity == 0:
            continue

        # Risk score: combines age, complexity, and churn
        age_factor = min(age / 365, 2.0)  # Caps at 2 years
        complexity_factor = min(complexity / 15, 2.0)  # Caps at CC=15
        churn_factor = min(commit_count / 20, 2.0)  # Caps at 20 commits
        loc_factor = min(loc / 500, 2.0)  # Caps at 500 LOC

        risk_score = (age_factor * 0.3 + complexity_factor * 0.35 +
                       churn_factor * 0.2 + loc_factor * 0.15) * 100

        risk_files.append({
            'file': fa['file'],
            'language': fa['language'],
            'risk_score': round(risk_score, 1),
            'age_days': age,
            'complexity': complexity,
            'commit_count': commit_count,
            'loc': loc,
            'factors': {
                'age': round(age_factor, 2),
                'complexity': round(complexity_factor, 2),
                'churn': round(churn_factor, 2),
                'size': round(loc_factor, 2),
            },
        })

    risk_files.sort(key=lambda x: x['risk_score'], reverse=True)

    # Categorize risk
    high_risk = [f for f in risk_files if f['risk_score'] >= 70]
    medium_risk = [f for f in risk_files if 40 <= f['risk_score'] < 70]
    low_risk = [f for f in risk_files if f['risk_score'] < 40]

    return {
        'high_risk': high_risk[:20],
        'medium_risk': medium_risk[:20],
        'low_risk': low_risk[:20],
        'top_risk_files': risk_files[:20],
        'high_risk_count': len(high_risk),
        'medium_risk_count': len(medium_risk),
        'low_risk_count': len(low_risk),
    }


# ── Age Histogram ──────────────────────────────────────────────────────────

def _build_age_histogram(file_ages: List[Dict]) -> Dict[str, int]:
    """Build age distribution histogram with buckets."""
    buckets = {
        '0-7 days (hot)': 0,
        '8-30 days (warm)': 0,
        '31-90 days': 0,
        '91-180 days': 0,
        '181-365 days (cold)': 0,
        '1-2 years': 0,
        '2-3 years': 0,
        '3+ years (ancient)': 0,
    }

    for fa in file_ages:
        age = fa['age_days']
        if age <= 7:
            buckets['0-7 days (hot)'] += 1
        elif age <= 30:
            buckets['8-30 days (warm)'] += 1
        elif age <= 90:
            buckets['31-90 days'] += 1
        elif age <= 180:
            buckets['91-180 days'] += 1
        elif age <= 365:
            buckets['181-365 days (cold)'] += 1
        elif age <= 730:
            buckets['1-2 years'] += 1
        elif age <= 1095:
            buckets['2-3 years'] += 1
        else:
            buckets['3+ years (ancient)'] += 1

    return dict(buckets)


# ── Correlation Analysis ──────────────────────────────────────────────────

def _calculate_correlation(file_ages: List[Dict]) -> Dict[str, Any]:
    """Analyze correlation between age, complexity, and churn."""
    if len(file_ages) < 3:
        return {'age_complexity': 0, 'age_churn': 0, 'complexity_churn': 0}

    ages = [fa['age_days'] for fa in file_ages if fa['loc'] > 0]
    complexities = [fa['complexity'] for fa in file_ages if fa['loc'] > 0]
    commits = [fa['commit_count'] for fa in file_ages if fa['loc'] > 0]
    locs = [fa['loc'] for fa in file_ages if fa['loc'] > 0]

    n = len(ages)
    if n < 3:
        return {'age_complexity': 0, 'age_churn': 0, 'complexity_churn': 0}

    def pearson(x, y):
        if len(x) != len(y) or len(x) < 2:
            return 0
        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)
        num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
        den_x = sum((a - mean_x) ** 2 for a in x) ** 0.5
        den_y = sum((b - mean_y) ** 2 for b in y) ** 0.5
        if den_x == 0 or den_y == 0:
            return 0
        return num / (den_x * den_y)

    ac = round(pearson(ages, complexities), 3)
    ach = round(pearson(ages, commits), 3)
    cc = round(pearson(complexities, commits), 3)
    alc = round(pearson(ages, locs), 3)

    # Insights
    insights = []
    if ac > 0.3:
        insights.append('Older files tend to be more complex (positive age-complexity correlation)')
    elif ac < -0.3:
        insights.append('Older files tend to be simpler (negative age-complexity correlation)')

    if ach > 0.3:
        insights.append('Older files have more commits (accumulated changes)')
    elif ach < -0.3:
        insights.append('Recently changed files are more active')

    if cc > 0.3:
        insights.append('Complex files are changed more often (high churn)')
    elif cc < -0.3:
        insights.append('Complex files are changed less often (stable complexity)')

    if alc > 0.3:
        insights.append('Older files tend to be larger (code grows over time)')

    if not insights:
        insights.append('No strong correlations detected between age, complexity, and churn')

    return {
        'age_complexity': ac,
        'age_churn': ach,
        'complexity_churn': cc,
        'age_loc': alc,
        'insights': insights,
        'sample_size': n,
    }


# ── Statistics ──────────────────────────────────────────────────────────────

def _calculate_statistics(file_ages: List[Dict]) -> Dict[str, Any]:
    """Calculate summary statistics for code age."""
    if not file_ages:
        return {}

    ages = [fa['age_days'] for fa in file_ages]
    commits = [fa['commit_count'] for fa in file_ages]
    change_rates = [fa['change_rate'] for fa in file_ages]

    sorted_ages = sorted(ages)
    n = len(sorted_ages)

    return {
        'total_files': len(file_ages),
        'avg_age_days': round(sum(ages) / max(n, 1), 1),
        'median_age_days': sorted_ages[n // 2] if n > 0 else 0,
        'min_age_days': min(ages) if ages else 0,
        'max_age_days': max(ages) if ages else 0,
        'p25_age_days': sorted_ages[n // 4] if n > 3 else 0,
        'p75_age_days': sorted_ages[3 * n // 4] if n > 3 else 0,
        'avg_commits': round(sum(commits) / max(n, 1), 1),
        'median_commits': sorted(commits)[n // 2] if n > 0 else 0,
        'total_commits': sum(commits),
        'avg_change_rate': round(sum(change_rates) / max(n, 1), 2),
        'stddev_age_days': round(_stddev(ages), 1) if ages else 0,
    }


def _stddev(values: List[float]) -> float:
    """Calculate standard deviation."""
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


# ── Terminal Output ─────────────────────────────────────────────────────────

def format_code_age_terminal(age_data: Dict[str, Any]) -> str:
    """Format code age analysis for terminal output."""
    stats = age_data.get('statistics', {})
    categories = age_data.get('categories', {})
    risk = age_data.get('risk_analysis', {})
    correlation = age_data.get('correlation', {})
    histogram = age_data.get('histogram', {})

    lines = [
        '',
        '─' * 55,
        '  📅 Code Age Analysis',
        '─' * 55,
        f'  Source: {"Git history" if age_data.get("is_git") else "File system mtime"}',
        f'  Files analyzed:   {stats.get("total_files", 0)}',
        f'  Avg age:          {stats.get("avg_age_days", 0):.0f} days',
        f'  Median age:       {stats.get("median_age_days", 0)} days',
        f'  Oldest file:      {stats.get("max_age_days", 0)} days',
        f'  Newest file:      {stats.get("min_age_days", 0)} days',
        '',
    ]

    # Category breakdown
    cat_icons = {'hot': '🔥', 'warm': '🌤️', 'cold': '❄️', 'cold_stable': '🧊', 'dead': '💀'}
    lines.append('  File Categories:')
    for cat_name in ('hot', 'warm', 'cold', 'cold_stable', 'dead'):
        cat = categories.get(cat_name, {})
        count = cat.get('count', 0)
        pct = cat.get('pct', 0)
        icon = cat_icons.get(cat_name, '❓')
        label = cat_name.replace('_', ' ').title()
        bar_len = int(pct / 5)
        bar = '█' * bar_len
        lines.append(f'  {icon} {label:16s} {count:4d} ({pct:5.1f}%) {bar}')
    lines.append('')

    # Age histogram
    lines.append('  Age Distribution:')
    max_count = max(histogram.values()) if histogram else 1
    for bucket, count in histogram.items():
        bar_len = int(count / max(max_count, 1) * 20)
        bar = '█' * bar_len
        lines.append(f'    {bucket:<22s} {count:4d} {bar}')
    lines.append('')

    # Risk analysis
    lines.append(f'  Risk Assessment:')
    lines.append(f'    🔴 High risk:   {risk.get("high_risk_count", 0)} files')
    lines.append(f'    🟡 Medium risk: {risk.get("medium_risk_count", 0)} files')
    lines.append(f'    🟢 Low risk:    {risk.get("low_risk_count", 0)} files')

    if risk.get('top_risk_files'):
        lines.append('')
        lines.append('  📁 Top Risk Files:')
        for rf in risk['top_risk_files'][:10]:
            fname = rf['file'].split('/')[-1]
            lines.append(
                f'    • {fname:<35s} risk:{rf["risk_score"]:5.1f} '
                f'age:{rf["age_days"]:4d}d cc:{rf["complexity"]:3d} '
                f'commits:{rf["commit_count"]:3d}'
            )
    lines.append('')

    # Correlation insights
    if correlation.get('insights'):
        lines.append('  📊 Correlation Insights:')
        for insight in correlation['insights']:
            lines.append(f'    • {insight}')
        lines.append('')

    lines.append('─' * 55)
    return '\n'.join(lines)


def generate_age_recommendations(age_data: Dict[str, Any]) -> List[Dict]:
    """Generate recommendations based on code age analysis."""
    recs: List[Dict] = []
    categories = age_data.get('categories', {})
    risk = age_data.get('risk_analysis', {})

    dead_count = categories.get('dead', {}).get('count', 0)
    if dead_count > 0:
        recs.append({
            'icon': '💀', 'category': 'Dead Code',
            'priority': 'medium',
            'message': f'{dead_count} files unchanged for >1 year. Consider removing dead code or adding tests.',
        })

    hot_count = categories.get('hot', {}).get('count', 0)
    if hot_count > 10:
        recs.append({
            'icon': '🔥', 'category': 'Active Development',
            'priority': 'low',
            'message': f'{hot_count} files changed in the last week. Ensure proper code review for these files.',
        })

    high_risk_count = risk.get('high_risk_count', 0)
    if high_risk_count > 5:
        recs.append({
            'icon': '⚠️', 'category': 'High-Risk Files',
            'priority': 'high',
            'message': f'{high_risk_count} files flagged as high risk (old + complex + high churn). Prioritize refactoring.',
        })

    if not recs:
        recs.append({
            'icon': '✨', 'category': 'Code Age',
            'priority': 'low',
            'message': 'Code age distribution looks healthy. Keep up the good maintenance!',
        })

    return recs
