"""Git analysis — commit metrics, author stats, file hotspots, contribution heatmap.

Comprehensive git history analysis including bus factor, branch analysis,
code churn, merge analysis, and time-based patterns.
"""

import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta


def is_git_repo(path: str) -> bool:
    """Check if path is a git repository."""
    return os.path.isdir(os.path.join(path, '.git'))


def git_command(path: str, *args, timeout: int = 30) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ['git'] + list(args),
            cwd=path, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ''


def get_authors(path: str, limit: int = 50) -> list:
    """Get commit counts per author."""
    output = git_command(path, 'log', '--format=%aN', '-10000')
    if not output:
        return []
    authors = Counter(output.split('\n'))
    return [{'name': name, 'commits': count} for name, count in authors.most_common(limit)]


def get_author_emails(path: str, limit: int = 50) -> list:
    """Get author emails with commit counts."""
    output = git_command(path, 'log', '--format=%aE', '-10000')
    if not output:
        return []
    emails = Counter(output.split('\n'))
    return [{'email': email, 'commits': count} for email, count in emails.most_common(limit)]


def get_commit_stats(path: str, limit: int = 1000) -> list:
    """Get lines added/removed per commit."""
    output = git_command(path, 'log', '--shortstat', '--format=%H|%aI|%aN', f'-{limit}')
    if not output:
        return []
    stats = []
    blocks = output.split('\n\n')
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue
        header = lines[0].split('|')
        sha = header[0][:8] if header else ''
        date = header[1][:10] if len(header) > 1 else ''
        author = header[2] if len(header) > 2 else ''
        added = 0
        removed = 0
        for line in lines[1:]:
            m = re.search(r'(\d+) insertion', line)
            if m:
                added = int(m.group(1))
            m = re.search(r'(\d+) deletion', line)
            if m:
                removed = int(m.group(1))
        stats.append({
            'sha': sha, 'date': date, 'author': author,
            'added': added, 'removed': removed,
            'net': added - removed,
        })
    return stats


def get_contribution_heatmap(path: str, weeks: int = 52) -> dict:
    """Get commit counts per day for the last N weeks."""
    since_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', '--since', since_date, '--format=%ad', '--date=short', '-50000')
    if not output:
        return {}
    return dict(Counter(output.split('\n')))


def get_most_active_files(path: str, limit: int = 20) -> list:
    """Get files with most commits touching them."""
    output = git_command(path, 'log', '--name-only', '--format=', '-5000')
    if not output:
        return []
    files = Counter(f for f in output.split('\n') if f.strip())
    return [{'file': name, 'commits': count} for name, count in files.most_common(limit)]


def get_file_hotspots(path: str, limit: int = 20) -> list:
    """Get files ranked by cumulative code churn (lines changed)."""
    output = git_command(path, 'log', '--numstat', '--format=', '-5000')
    if not output:
        return []
    churn = Counter()
    for line in output.split('\n'):
        parts = line.split('\t')
        if len(parts) == 3:
            added = int(parts[0]) if parts[0] != '-' else 0
            removed = int(parts[1]) if parts[1] != '-' else 0
            if parts[2].strip():
                churn[parts[2].strip()] += added + removed
    return [{'file': name, 'churn': count} for name, count in churn.most_common(limit)]


def get_branch_info(path: str) -> dict:
    """Get branch information."""
    current = git_command(path, 'rev-parse', '--abbrev-ref', 'HEAD')
    branches = git_command(path, 'branch', '-a')
    branch_list = []
    if branches:
        branch_list = [b.strip().lstrip('* ') for b in branches.split('\n') if b.strip()]
    local_branches = [b for b in branch_list if not b.startswith('remotes/')]
    remote_branches = [b for b in branch_list if b.startswith('remotes/')]
    last_fetch = git_command(path, 'log', '-1', '--format=%aI', 'refs/remotes/origin/HEAD') if 'origin' in str(branch_list) else ''
    return {
        'current': current or 'unknown',
        'count': len(local_branches),
        'local': local_branches[:20],
        'remote': remote_branches[:20],
        'last_fetch': last_fetch[:10] if last_fetch else 'unknown',
    }


def get_total_commits(path: str) -> int:
    """Get total commit count."""
    output = git_command(path, 'rev-list', '--count', 'HEAD')
    try:
        return int(output)
    except ValueError:
        return 0


def get_first_last_commit(path: str) -> dict:
    """Get date range of the repository."""
    first = git_command(path, 'log', '--reverse', '--format=%ad', '--date=short', '-1')
    last = git_command(path, 'log', '--format=%ad', '--date=short', '-1')
    return {'first': first or 'unknown', 'last': last or 'unknown'}


def get_commit_frequency(path: str) -> dict:
    """Analyze commit frequency patterns."""
    output = git_command(path, 'log', '--format=%aI', '-50000')
    if not output:
        return {}
    dates = [d[:10] for d in output.split('\n') if d.strip()]
    if not dates:
        return {}
    hours = Counter()
    weekdays = Counter()
    months = Counter()
    for d in output.split('\n'):
        if not d.strip():
            continue
        try:
            dt = datetime.fromisoformat(d.strip())
            hours[dt.hour] += 1
            weekdays[dt.strftime('%A')] += 1
            months[f"{dt.year}-{dt.month:02d}"] += 1
        except (ValueError, IndexError):
            continue
    return {
        'by_hour': dict(hours),
        'by_weekday': dict(weekdays),
        'by_month': dict(sorted(months.items())),
    }


def calculate_bus_factor(path: str, authors: list = None, threshold: float = 0.5) -> dict:
    """Calculate bus factor — minimum authors that account for X% of commits."""
    if authors is None:
        authors = get_authors(path)
    if not authors:
        return {'factor': 0, 'authors': 0, 'total': 0}
    total_commits = sum(a['commits'] for a in authors)
    cumulative = 0
    factor = 0
    key_authors = []
    for a in authors:
        cumulative += a['commits']
        factor += 1
        key_authors.append(a['name'])
        if cumulative / total_commits >= threshold:
            break
    return {
        'factor': factor,
        'authors': len(authors),
        'total_commits': total_commits,
        'key_authors': key_authors,
        'coverage_pct': round(cumulative / total_commits * 100, 1) if total_commits > 0 else 0,
    }


def get_merge_analysis(path: str) -> dict:
    """Analyze merge commit patterns."""
    output = git_command(path, 'log', '--merges', '--format=%H|%aI|%s', '-500')
    if not output:
        return {'total_merges': 0, 'merge_rate': 0}
    merges = []
    for line in output.split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        merges.append({
            'sha': parts[0][:8] if parts else '',
            'date': parts[1][:10] if len(parts) > 1 else '',
            'message': parts[2] if len(parts) > 2 else '',
        })
    total_commits = get_total_commits(path)
    merge_rate = len(merges) / max(total_commits, 1) * 100
    return {
        'total_merges': len(merges),
        'merge_rate': round(merge_rate, 1),
        'recent_merges': merges[:10],
    }


def get_code_churn(path: str, days: int = 90) -> dict:
    """Analyze code churn over the last N days."""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', f'--since={since}', '--numstat', '--format=')
    if not output:
        return {'added': 0, 'removed': 0, 'files_changed': 0, 'avg_commit_size': 0}
    total_added = 0
    total_removed = 0
    files_changed = set()
    for line in output.split('\n'):
        parts = line.split('\t')
        if len(parts) == 3 and parts[2].strip():
            a = int(parts[0]) if parts[0] != '-' else 0
            r = int(parts[1]) if parts[1] != '-' else 0
            total_added += a
            total_removed += r
            files_changed.add(parts[2].strip())
    commit_count_output = git_command(path, 'rev-list', '--count', f'--since={since}', 'HEAD')
    commit_count = int(commit_count_output) if commit_count_output.isdigit() else 1
    return {
        'period': f'last {days} days',
        'added': total_added,
        'removed': total_removed,
        'net': total_added - total_removed,
        'files_changed': len(files_changed),
        'commit_count': commit_count,
        'avg_commit_size': round((total_added + total_removed) / max(commit_count, 1), 1),
    }


def get_commit_timeline(path: str, months: int = 12) -> list:
    """Get monthly commit counts for timeline visualization."""
    since = (datetime.now() - timedelta(days=months * 30)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', f'--since={since}', '--format=%aI')
    if not output:
        return []
    monthly = Counter()
    for d in output.split('\n'):
        if not d.strip():
            continue
        try:
            dt = datetime.fromisoformat(d.strip())
            monthly[f"{dt.year}-{dt.month:02d}"] += 1
        except (ValueError, IndexError):
            continue
    return [{'month': m, 'count': c} for m, c in sorted(monthly.items())]


def get_tag_info(path: str) -> list:
    """Get git tags."""
    output = git_command(path, 'tag', '-l', '--sort=-creatordate')
    if not output:
        return []
    tags = []
    for tag in output.split('\n')[:20]:
        if not tag.strip():
            continue
        date = git_command(path, 'log', '-1', '--format=%aI', tag)
        message = git_command(path, 'tag', '-l', '-n1', tag)
        tags.append({
            'name': tag.strip(),
            'date': date[:10] if date else 'unknown',
            'message': message.split('\n')[0].strip() if message else '',
        })
    return tags


def get_stash_info(path: str) -> int:
    """Get number of stashed changes."""
    output = git_command(path, 'stash', 'list')
    if not output:
        return 0
    return len([l for l in output.split('\n') if l.strip()])


def get_uncommitted_changes(path: str) -> dict:
    """Get count of uncommitted changes."""
    status = git_command(path, 'status', '--porcelain')
    if not status:
        return {'modified': 0, 'added': 0, 'deleted': 0, 'untracked': 0}
    modified = 0
    added = 0
    deleted = 0
    untracked = 0
    for line in status.split('\n'):
        if not line.strip():
            continue
        code = line[:2]
        if code.startswith('??'):
            untracked += 1
        elif 'M' in code:
            modified += 1
        elif 'A' in code:
            added += 1
        elif 'D' in code:
            deleted += 1
    return {'modified': modified, 'added': added, 'deleted': deleted, 'untracked': untracked}


def get_active_developers(path: str, days: int = 90) -> list:
    """Get list of developers active in the last N days."""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', f'--since={since}', '--format=%aN')
    if not output:
        return []
    authors = Counter(output.split('\n'))
    return [{'name': name, 'commits': count} for name, count in authors.most_common()]


def full_git_analysis(path: str) -> dict:
    """Run complete git analysis."""
    if not is_git_repo(path):
        return None

    authors = get_authors(path)
    bus = calculate_bus_factor(path, authors)
    commit_stats = get_commit_stats(path)

    return {
        'authors': authors,
        'author_emails': get_author_emails(path),
        'total_commits': get_total_commits(path),
        'commit_stats': commit_stats[:100],
        'heatmap': get_contribution_heatmap(path),
        'active_files': get_most_active_files(path),
        'hotspots': get_file_hotspots(path),
        'branches': get_branch_info(path),
        'date_range': get_first_last_commit(path),
        'frequency': get_commit_frequency(path),
        'bus_factor': bus,
        'merges': get_merge_analysis(path),
        'code_churn': get_code_churn(path),
        'commit_timeline': get_commit_timeline(path),
        'tags': get_tag_info(path),
        'stash_count': get_stash_info(path),
        'uncommitted': get_uncommitted_changes(path),
        'active_developers': get_active_developers(path),
    }


def get_commit_message_stats(path: str, limit: int = 500) -> dict:
    """Analyze commit messages for conventions and quality."""
    output = git_command(path, 'log', '--format=%s', f'-{limit}')
    if not output:
        return {}
    
    messages = [m.strip() for m in output.split('\n') if m.strip()]
    
    lengths = [len(m) for m in messages]
    has_issue_ref = sum(1 for m in messages if re.search(r'#\d+|[A-Z]+-\d+', m))
    has_conventional = sum(1 for m in messages if re.match(r'^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?:\s+', m))
    has_signoff = sum(1 for m in messages if 'Signed-off-by' in m or 'Co-authored-by' in m)
    has_breaking = sum(1 for m in messages if re.match(r'^\w+(\(.+\))?!:', m))
    
    words_per_msg = []
    for m in messages:
        words = m.split()
        words_per_msg.append(len(words))
    
    return {
        'total_messages': len(messages),
        'avg_length': round(sum(lengths) / max(len(lengths), 1), 1),
        'max_length': max(lengths) if lengths else 0,
        'min_length': min(lengths) if lengths else 0,
        'avg_words': round(sum(words_per_msg) / max(len(words_per_msg), 1), 1),
        'with_issue_ref': has_issue_ref,
        'with_issue_ref_pct': round(has_issue_ref / max(len(messages), 1) * 100, 1),
        'conventional_commits': has_conventional,
        'conventional_commits_pct': round(has_conventional / max(len(messages), 1) * 100, 1),
        'with_signoff': has_signoff,
        'breaking_changes': has_breaking,
        'quality_score': round(min(
            (has_conventional / max(len(messages), 1) * 50) +
            (has_issue_ref / max(len(messages), 1) * 30) +
            (has_signoff / max(len(messages), 1) * 20), 100
        ), 1),
    }


def get_file_coauthorship(path: str, limit: int = 1000) -> list:
    """Find files modified by multiple authors (potential knowledge silos)."""
    output = git_command(path, 'log', '--name-only', '--format=%aN', f'-{limit}')
    if not output:
        return []
    
    file_authors = defaultdict(set)
    current_author = None
    for line in output.split('\n'):
        line = line.strip()
        if line and not line.startswith('.') and '/' in line:
            file_authors[line].add(current_author)
        elif line:
            current_author = line
    
    multi_author = [
        {'file': f, 'authors': list(authors), 'author_count': len(authors)}
        for f, authors in file_authors.items()
        if len(authors) >= 2
    ]
    return sorted(multi_author, key=lambda x: x['author_count'], reverse=True)[:20]


def get_commit_size_distribution(path: str, limit: int = 500) -> dict:
    """Analyze the distribution of commit sizes."""
    stats = get_commit_stats(path, limit)
    if not stats:
        return {}
    
    sizes = [s['added'] + s['removed'] for s in stats]
    if not sizes:
        return {}
    
    return {
        'total_lines_changed': sum(sizes),
        'average': round(sum(sizes) / len(sizes), 1),
        'median': sorted(sizes)[len(sizes) // 2],
        'max': max(sizes),
        'min': min(sizes),
        'distribution': {
            'tiny (1-10)': sum(1 for s in sizes if s <= 10),
            'small (11-50)': sum(1 for s in sizes if 11 <= s <= 50),
            'medium (51-200)': sum(1 for s in sizes if 51 <= s <= 200),
            'large (201-1000)': sum(1 for s in sizes if 201 <= s <= 1000),
            'huge (>1000)': sum(1 for s in sizes if s > 1000),
        },
    }


def analyze_review_patterns(path: str) -> dict:
    """Analyze code review patterns if review data is available."""
    return {
        'pull_requests': 0,
        'avg_review_time_hours': 0,
        'reviewers': [],
        'merge_without_review': 0,
    }


def get_contribution_by_weekday(path: str, weeks: int = 52) -> dict:
    """Get commit counts broken down by day of week."""
    since_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', '--since', since_date, '--format=%ad', '--date=format:%A', '-50000')
    if not output:
        return {}
    return dict(Counter(output.split('\n')))


def get_contribution_by_hour(path: str, weeks: int = 12) -> dict:
    """Get commit counts broken down by hour of day."""
    since_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
    output = git_command(path, 'log', '--since', since_date, '--format=%ad', '--date=format:%H', '-50000')
    if not output:
        return {}
    hourly = dict(Counter(output.split('\n')))
    result = {}
    for h in range(24):
        key = f'{h:02d}'
        result[key] = hourly.get(key, 0)
    return result


def analyze_branch_age(path: str) -> list:
    """Find stale branches."""
    branches = get_branch_info(path)
    stale = []
    for branch in branches.get('local', []):
        if branch in ('main', 'master', 'develop', 'staging'):
            continue
        last_commit = git_command(path, 'log', '-1', '--format=%aI', branch)
        if last_commit:
            try:
                last_date = datetime.fromisoformat(last_commit.strip())
                age_days = (datetime.now() - last_date).days
                if age_days > 30:
                    stale.append({
                        'branch': branch,
                        'age_days': age_days,
                        'last_commit': last_commit[:10],
                    })
            except ValueError:
                pass
    return sorted(stale, key=lambda x: x['age_days'], reverse=True)[:20]


def compute_git_health_score(git_data: dict) -> int:
    """Compute an overall git health score (0-100)."""
    if not git_data:
        return 0
    
    score = 50
    
    # Good commit frequency
    if git_data.get('total_commits', 0) > 100:
        score += 10
    
    # Multiple contributors
    authors = len(git_data.get('authors', []))
    if authors >= 3:
        score += 10
    elif authors >= 2:
        score += 5
    
    # Good bus factor
    bus = git_data.get('bus_factor', {})
    if bus.get('factor', 0) >= 3:
        score += 10
    elif bus.get('factor', 0) >= 2:
        score += 5
    
    # Reasonable merge rate
    merges = git_data.get('merges', {})
    if merges.get('merge_rate', 0) < 80:
        score += 5
    
    # Recent activity
    churn = git_data.get('code_churn', {})
    if churn.get('commit_count', 0) > 10:
        score += 10
    
    # Tags/releases
    if len(git_data.get('tags', [])) > 0:
        score += 5
    
    return min(100, score)
