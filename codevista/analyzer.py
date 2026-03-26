"""Core analyzer — language detection, complexity, duplication, framework detection.

Comprehensive per-function metrics, import analysis, code quality checks,
duplication detection, and file change tracking.
"""

import os
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any, Set

from .languages import detect_language, get_lang_color, get_comment_syntax
from .utils import (
    discover_files, read_file_safe, count_lines, cyclomatic_complexity,
    cognitive_complexity, extract_imports, normalize_import, block_hash,
    compute_file_hash, normalize_for_duplication, is_stdlib_import,
    detect_functions, extract_todos, detect_quality_issues,
    find_duplicate_strings, is_comment_line,
)
from .config import load_config, parse_codevista_config, should_ignore, DEFAULT_CONFIG
from .security import scan_file
from .dependencies import find_dependencies, detect_circular_imports
from .git_analysis import full_git_analysis


def analyze_project(project_path: str, max_depth: Optional[int] = None,
                    include_git: bool = True, quick_mode: bool = False) -> Dict[str, Any]:
    """Full analysis of a project. Returns comprehensive analysis dict."""
    project_path = os.path.abspath(project_path)
    ignore_patterns = load_config(project_path)
    config = parse_codevista_config(project_path)

    files = discover_files(project_path, max_depth, ignore_patterns, config)
    file_data = []
    import_graph = defaultdict(set)
    all_blocks = defaultdict(list)
    lang_stats = Counter()
    framework_markers = Counter()
    file_hashes = defaultdict(list)
    total_lines = {'code': 0, 'comment': 0, 'blank': 0, 'total': 0}
    security_issues = []
    complexities = []
    all_functions = []
    all_todos = []
    all_quality_issues = []
    all_duplicate_strings = []
    import_details = defaultdict(lambda: {'stdlib': [], 'third_party': [], 'local': []})
    lang_files = defaultdict(int)
    complexity_distribution = Counter()
    size_distribution = Counter()
    quality_issue_summary = Counter()

    for fpath in files:
        lang = detect_language(fpath)
        if lang is None:
            continue
        content = read_file_safe(fpath)
        if not content:
            continue

        rel_path = os.path.relpath(fpath, project_path)
        lc = count_lines(content, lang)
        cc = cyclomatic_complexity(content, lang)
        cog_cc = cognitive_complexity(content, lang)
        imports = extract_imports(content, lang)
        file_size = os.path.getsize(fpath)
        functions = detect_functions(content, lang)
        todos = extract_todos(content)
        quality_issues = detect_quality_issues(content, lang, rel_path)
        dup_strings = find_duplicate_strings(content)
        maint_idx = _maintainability_index(content, cc, lc)

        total_lines['code'] += lc['code']
        total_lines['comment'] += lc['comment']
        total_lines['blank'] += lc['blank']
        total_lines['total'] += lc['total']
        lang_stats[lang] += lc['total']
        lang_files[lang] += 1
        complexities.append(cc)

        complexity_bucket = _complexity_bucket(cc)
        complexity_distribution[complexity_bucket] += 1

        size_bucket = _size_bucket(file_size)
        size_distribution[size_bucket] += 1

        for qi in quality_issues:
            quality_issue_summary[qi['type']] += 1

        norm_name = rel_path.replace('\\', '/').replace('/', '.')
        for imp in imports:
            import_graph[norm_name].add(normalize_import(imp))
            if is_stdlib_import(imp, lang):
                import_details[lang]['stdlib'].append(imp)
            elif _is_local_import(imp, project_path, rel_path):
                import_details[lang]['local'].append(imp)
            else:
                import_details[lang]['third_party'].append(imp)

        fh = compute_file_hash(normalize_for_duplication(content))
        file_hashes[fh].append(rel_path)

        blocks = block_hash(content, config.get('duplication_block_size', 6))
        for bh in blocks:
            all_blocks[bh].append(rel_path)

        issues = scan_file(fpath, content)
        security_issues.extend(issues)

        all_functions.extend(functions)
        all_todos.extend(todos)
        all_quality_issues.extend(quality_issues)
        all_duplicate_strings.extend(dup_strings)

        comment_ratio = lc['comment'] / lc['total'] if lc['total'] > 0 else 0
        file_data.append({
            'path': rel_path,
            'language': lang,
            'color': get_lang_color(lang),
            'lines': lc,
            'complexity': cc,
            'cognitive_complexity': cog_cc,
            'maintainability_index': maint_idx,
            'size': file_size,
            'imports': imports[:20],
            'import_count': len(imports),
            'function_count': len(functions),
            'functions': functions if not quick_mode else functions[:10],
            'todos': todos,
            'quality_issues': quality_issues,
            'comment_ratio': comment_ratio,
        })

    frameworks = detect_frameworks(project_path)
    duplicates = _find_duplicates(all_blocks, file_hashes)
    circular = detect_circular_imports(dict(import_graph))
    deps, pkg_manager = find_dependencies(project_path)
    git_data = full_git_analysis(project_path) if include_git else None
    dir_structure = build_dir_tree(file_data, project_path)
    unused_imports = _detect_unused_imports(import_graph, import_details)

    tech_stack = None
    if not quick_mode:
        try:
            from .tech_detector import detect_tech_stack
            tech_stack = detect_tech_stack(project_path)
        except Exception:
            pass

    return {
        'project_name': os.path.basename(project_path),
        'project_path': project_path,
        'files': file_data,
        'total_files': len(file_data),
        'total_lines': total_lines,
        'languages': dict(lang_stats.most_common()),
        'language_files': dict(lang_files),
        'frameworks': frameworks,
        'tech_stack': tech_stack,
        'avg_complexity': sum(complexities) / len(complexities) if complexities else 0,
        'max_complexity': max(complexities) if complexities else 0,
        'median_complexity': _median(complexities) if complexities else 0,
        'functions': all_functions,
        'top_complex_functions': sorted(all_functions, key=lambda x: x['complexity'], reverse=True)[:20],
        'complexity_distribution': dict(complexity_distribution),
        'size_distribution': dict(size_distribution),
        'todos': all_todos,
        'quality_issues': all_quality_issues,
        'quality_issue_summary': dict(quality_issue_summary),
        'duplicate_strings': all_duplicate_strings[:20],
        'duplicates': duplicates[:50],
        'security_issues': security_issues,
        'circular_deps': circular,
        'dependencies': deps,
        'package_manager': pkg_manager,
        'import_graph': dict(import_graph),
        'import_details': {k: dict(v) for k, v in import_details.items()},
        'unused_imports': unused_imports,
        'git': git_data,
        'dir_tree': dir_structure,
    }


def detect_frameworks(project_path: str) -> List[str]:
    """Detect frameworks from config files and patterns."""
    frameworks = []
    checkers = [
        ('package.json', [
            ('react', 'React'), ('vue', 'Vue'), ('angular', 'Angular'),
            ('next', 'Next.js'), ('nuxt', 'Nuxt'), ('svelte', 'Svelte'),
            ('express', 'Express'), ('fastify', 'Fastify'), ('koa', 'Koa'),
            ('typescript', 'TypeScript'), ('tailwindcss', 'Tailwind CSS'),
            ('vite', 'Vite'), ('webpack', 'Webpack'), ('eslint', 'ESLint'),
            ('nestjs', 'NestJS'), ('gatsby', 'Gatsby'), ('remix', 'Remix'),
            ('astro', 'Astro'), ('hapi', 'hapi'), ('meteor', 'Meteor'),
            ('deno', 'Deno'), ('bun', 'Bun'),
        ]),
        ('requirements.txt', [
            ('django', 'Django'), ('flask', 'Flask'), ('fastapi', 'FastAPI'),
            ('starlette', 'Starlette'), ('requests', 'Requests'),
            ('celery', 'Celery'), ('scikit-learn', 'scikit-learn'),
            ('tensorflow', 'TensorFlow'), ('pytorch', 'PyTorch'),
            ('pandas', 'Pandas'), ('numpy', 'NumPy'),
            ('pytest', 'pytest'), ('selenium', 'Selenium'),
            ('streamlit', 'Streamlit'), ('gradio', 'Gradio'),
            ('dash', 'Dash'), ('plotly', 'Plotly'),
            ('tornado', 'Tornado'), ('pyramid', 'Pyramid'),
            ('sanic', 'Sanic'), ('falcon', 'Falcon'),
        ]),
        ('Gemfile', [
            ('rails', 'Ruby on Rails'), ('sinatra', 'Sinatra'),
            ('hanami', 'Hanami'), ('roda', 'Roda'),
        ]),
    ]

    for fname, patterns in checkers:
        fpath = os.path.join(project_path, fname)
        if not os.path.isfile(fpath):
            continue
        content = read_file_safe(fpath).lower()
        for pattern, name in patterns:
            if pattern in content:
                frameworks.append(name)

    marker_files = {
        'manage.py': 'Django',
        'next.config.js': 'Next.js',
        'next.config.mjs': 'Next.js',
        'next.config.ts': 'Next.js',
        'angular.json': 'Angular',
        'Cargo.toml': 'Rust',
        'go.mod': 'Go',
        'mix.exs': 'Elixir',
        'build.gradle': 'Gradle',
        'build.gradle.kts': 'Gradle',
        'pom.xml': 'Maven/Java',
        'composer.json': 'Composer/PHP',
    }
    for fname, fw_name in marker_files.items():
        if os.path.isfile(os.path.join(project_path, fname)):
            frameworks.append(fw_name)

    return list(dict.fromkeys(frameworks))


def build_dir_tree(file_data: List[Dict], project_path: str) -> Dict:
    """Build directory tree from file data."""
    tree = {}
    for f in file_data:
        parts = f['path'].replace('\\', '/').split('/')
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = {
            'lines': f['lines']['total'],
            'language': f['language'],
            'color': f['color'],
            'size': f['size'],
            'complexity': f['complexity'],
        }
    return tree


def _maintainability_index(content: str, cc: int, lc: Dict[str, int]) -> float:
    """Calculate maintainability index (simplified Microsoft formula)."""
    total = lc['total']
    if total == 0:
        return 100.0
    comment_ratio = lc['comment'] / total
    halstead_vol = _halstead_volume(content)
    if halstead_vol == 0:
        halstead_vol = 1
    mi = 171.0 - 5.2 * __import__('math').log(halstead_vol) - 0.23 * cc - 16.2 * __import__('math').log(total)
    mi = max(0, min(100, mi * (comment_ratio + 1)))
    return round(mi, 1)


def _halstead_volume(content: str) -> float:
    """Estimate Halstead volume from content."""
    operators = set()
    operands = set()
    total_ops = 0
    total_operands = 0
    op_patterns = [
        r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\breturn\b',
        r'\band\b', r'\bor\b', r'\bnot\b', r'\bin\b', r'\bis\b',
        r'\bclass\b', r'\bdef\b', r'\bwith\b', r'\bas\b', r'\bimport\b',
        r'\bfrom\b', r'\braise\b', r'\byield\b', r'\blambda\b',
        r'\+|-|\*|/|%|\*\*|//|<<|>>|&|\||\^|~|@',
        r'=|==|!=|<|>|<=|>=',
        r'\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=|//=|\*\*=',
    ]
    for pattern in op_patterns:
        matches = re.findall(pattern, content)
        if matches:
            operators.add(pattern)
            total_ops += len(matches)
    identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', content)
    keywords = {
        'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return',
        'import', 'from', 'as', 'with', 'try', 'except', 'finally',
        'raise', 'yield', 'lambda', 'pass', 'break', 'continue',
        'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False',
        'self', 'global', 'nonlocal', 'assert', 'del',
    }
    for ident in identifiers:
        if ident not in keywords:
            operands.add(ident)
            total_operands += 1
    n1 = len(operators)
    n2 = len(operands)
    N1 = total_ops
    N2 = total_operands
    n = n1 + n2
    N = N1 + N2
    if n == 0 or N == 0:
        return 0
    volume = N * __import__('math').log2(n) if n > 1 else N
    return volume


def _find_duplicates(all_blocks: Dict, file_hashes: Dict) -> List[Dict]:
    """Find duplicate code blocks and exact file duplicates."""
    duplicates = []
    seen_pairs = set()
    for bh, paths in all_blocks.items():
        if len(paths) > 1:
            unique_paths = list(set(paths))
            if len(unique_paths) > 1:
                for i in range(len(unique_paths)):
                    for j in range(i + 1, len(unique_paths)):
                        pair = tuple(sorted([unique_paths[i], unique_paths[j]]))
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            duplicates.append({
                                'files': list(pair),
                                'type': 'block',
                                'similarity': 1.0,
                            })
    for fh, paths in file_hashes.items():
        if len(paths) > 1:
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    pair = tuple(sorted([paths[i], paths[j]]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        duplicates.append({
                            'files': list(pair),
                            'type': 'exact',
                            'similarity': 1.0,
                        })
    return sorted(duplicates, key=lambda x: x['similarity'], reverse=True)


def _detect_unused_imports(import_graph: Dict, import_details: Dict) -> List[Dict]:
    """Detect potentially unused imports by checking if modules are referenced elsewhere."""
    unused = []
    all_imported = set()
    all_referenced = set()
    for module, targets in import_graph.items():
        for t in targets:
            all_imported.add(t)
    for targets in import_graph.values():
        all_referenced.update(targets)
    for t in all_imported:
        if t not in all_referenced:
            unused.append({'name': t, 'type': 'unused_import'})
    return unused[:50]


def _is_local_import(imp: str, project_path: str, rel_path: str) -> bool:
    """Check if an import refers to a local module."""
    base = normalize_import(imp)
    if base.startswith('.'):
        return True
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) > 1:
        top_level = parts[0]
        if base == top_level or base == top_level.replace('_', ''):
            return True
    check_path = os.path.join(project_path, base.replace('.', os.sep))
    if os.path.isdir(check_path):
        return True
    for ext in ('.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java'):
        if os.path.isfile(check_path + ext):
            return True
    return False


def _complexity_bucket(cc: int) -> str:
    if cc <= 5:
        return 'low'
    elif cc <= 10:
        return 'moderate'
    elif cc <= 20:
        return 'high'
    elif cc <= 40:
        return 'very-high'
    return 'extreme'


def _size_bucket(size: int) -> str:
    if size < 1024:
        return 'tiny'
    elif size < 5120:
        return 'small'
    elif size < 20480:
        return 'medium'
    elif size < 102400:
        return 'large'
    return 'huge'


def _median(values: List[int]) -> float:
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return float(s[n // 2])


def quick_analyze(project_path: str) -> Dict[str, Any]:
    """Fast analysis with reduced depth and no git."""
    return analyze_project(project_path, max_depth=3, include_git=False, quick_mode=True)


def compare_projects(path1: str, path2: str) -> Dict[str, Any]:
    """Analyze two projects and return comparison data."""
    a1 = analyze_project(path1, include_git=False, quick_mode=True)
    a2 = analyze_project(path2, include_git=False, quick_mode=True)
    return {'project1': a1, 'project2': a2}


def analyze_architecture(project_path: str, files_data: list) -> dict:
    """Deep architecture analysis including module clustering and coupling."""
    clusters = defaultdict(list)
    for f in files_data:
        parts = f['path'].replace(os.sep, '/').split('/')
        if len(parts) > 1:
            cluster = parts[0]
            clusters[cluster].append(f)
    
    cluster_metrics = {}
    for name, files in clusters.items():
        total_loc = sum(f['lines']['total'] for f in files)
        total_complexity = sum(f['complexity'] for f in files)
        avg_complexity = total_complexity / max(len(files), 1)
        languages = Counter(f['language'] for f in files)
        cluster_metrics[name] = {
            'files': len(files),
            'total_loc': total_loc,
            'avg_complexity': round(avg_complexity, 2),
            'languages': dict(languages),
            'top_files': sorted(files, key=lambda x: x['lines']['total'], reverse=True)[:5],
        }
    
    return {
        'clusters': dict(cluster_metrics),
        'total_clusters': len(clusters),
        'largest_cluster': max(cluster_metrics.values(), key=lambda x: x['total_loc']) if cluster_metrics else {},
        'depth': max(len(f['path'].split(os.sep)) for f in files_data) if files_data else 0,
        'breadth': len(clusters),
    }


def analyze_code_churn_per_file(project_path: str, files_data: list) -> list:
    """Analyze which files have changed most recently."""
    import subprocess
    churn = []
    for f in files_data:
        rel = f['path']
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '--', rel],
                cwd=project_path, capture_output=True, text=True, timeout=5
            )
            commits = len([l for l in result.stdout.split('\n') if l.strip()])
            churn.append({'file': rel, 'commit_count': commits, 'language': f['language']})
        except (subprocess.TimeoutExpired, FileNotFoundError):
            churn.append({'file': rel, 'commit_count': 0, 'language': f['language']})
    return sorted(churn, key=lambda x: x['commit_count'], reverse=True)


def calculate_technical_debt_score(analysis: dict) -> dict:
    """Calculate technical debt score based on multiple factors."""
    factors = {}
    
    # TODO debt
    todo_count = len(analysis.get('todos', []))
    factors['todos'] = min(todo_count * 2, 30)
    
    # Complexity debt
    high_complexity = sum(1 for f in analysis['files'] if f['complexity'] > 15)
    factors['complexity'] = min(high_complexity * 3, 30)
    
    # Duplication debt
    dup_count = len(analysis.get('duplicates', []))
    factors['duplication'] = min(dup_count * 5, 20)
    
    # Security debt
    sec_issues = len(analysis.get('security_issues', []))
    critical_sec = sum(1 for i in analysis.get('security_issues', []) if i['severity'] in ('critical', 'high'))
    factors['security'] = min(critical_sec * 5 + (sec_issues - critical_sec), 25)
    
    # Quality debt
    quality_issues = len(analysis.get('quality_issues', []))
    factors['quality'] = min(quality_issues // 5, 15)
    
    # Coverage debt
    total = analysis['total_lines']['total']
    comment_ratio = analysis['total_lines']['comment'] / max(total, 1)
    if comment_ratio < 0.05:
        factors['coverage'] = 15
    elif comment_ratio < 0.1:
        factors['coverage'] = 10
    elif comment_ratio < 0.2:
        factors['coverage'] = 5
    else:
        factors['coverage'] = 0
    
    total_debt = sum(factors.values())
    max_debt = 120
    
    return {
        'total': min(total_debt, max_debt),
        'max': max_debt,
        'percentage': round(total_debt / max_debt * 100, 1),
        'factors': factors,
        'rating': 'critical' if total_debt > 80 else 'high' if total_debt > 50 else 'moderate' if total_debt > 25 else 'low',
    }


def analyze_naming_conventions(content: str, language: str) -> list:
    """Check naming conventions for the language."""
    issues = []
    if language == 'Python':
        for line_num, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            m = re.match(r'^class\s+([A-Z][a-zA-Z0-9]*)', stripped)
            if not m and re.match(r'^class\s+(\w+)', stripped):
                name = re.match(r'^class\s+(\w+)', stripped).group(1)
                if name[0].islower():
                    issues.append({'line': line_num, 'type': 'naming', 'message': f'Class {name} should use PascalCase'})
            
            m = re.match(r'^def\s+([a-z_]\w*)', stripped)
            if not m and re.match(r'^def\s+(\w+)', stripped):
                name = re.match(r'^def\s+(\w+)', stripped).group(1)
                if name[0].isupper() and name != '__init__':
                    issues.append({'line': line_num, 'type': 'naming', 'message': f'Function {name} should use snake_case'})
            
            m = re.match(r'^([A-Z_][A-Z_0-9]*)\s*=', stripped)
            if not m and re.match(r'^([a-z]\w*)\s*=\s*[0-9]', stripped):
                name = m.group(1) if m else ''
    
    return issues


def analyze_error_handling(content: str, language: str) -> list:
    """Analyze error handling patterns."""
    issues = []
    if language in ('Python', 'Cython'):
        try_blocks = len(re.findall(r'\btry\b', content))
        bare_excepts = len(re.findall(r'\bexcept\s*:', content))
        generic_excepts = len(re.findall(r'\bexcept\s+Exception\b', content))
        specific_excepts = len(re.findall(r'\bexcept\s+\w+Error\b', content))
        
        if bare_excepts > 0:
            issues.append({'type': 'bare_except', 'count': bare_excepts, 'severity': 'medium',
                          'message': f'{bare_excepts} bare except clauses found'})
        if generic_excepts > specific_excepts:
            issues.append({'type': 'generic_except', 'count': generic_excepts,
                          'message': f'Prefer specific exception types over generic Exception'})
        
        has_finally = len(re.findall(r'\bfinally\b', content))
        if try_blocks > 0 and has_finally == 0:
            issues.append({'type': 'no_finally', 'message': 'Consider using finally for cleanup'})
    
    return issues


def compute_coupling_between_modules(import_graph: dict) -> list:
    """Find tightly coupled module pairs."""
    pairs = Counter()
    for module, deps in import_graph.items():
        for dep in deps:
            pair = tuple(sorted([module.split('.')[0], dep.split('.')[0]]))
            if pair[0] != pair[1]:
                pairs[pair] += 1
    
    return [{'modules': list(pair), 'connections': count} 
            for pair, count in pairs.most_common(20)]


def analyze_file_complexity_trend(files_data: list) -> dict:
    """Analyze complexity distribution across files."""
    if not files_data:
        return {'trend': 'unknown', 'distribution': 'unknown'}
    
    complexities = [f['complexity'] for f in files_data]
    avg = sum(complexities) / len(complexities)
    
    above_threshold = sum(1 for c in complexities if c > 10)
    below_threshold = sum(1 for c in complexities if c <= 5)
    
    if above_threshold > len(complexities) * 0.3:
        trend = 'increasing'
    elif below_threshold > len(complexities) * 0.7:
        trend = 'decreasing'
    else:
        trend = 'stable'
    
    p25 = sorted(complexities)[len(complexities)//4]
    p75 = sorted(complexities)[3*len(complexities)//4]
    
    return {
        'trend': trend,
        'mean': round(avg, 2),
        'median': complexities[len(complexities)//2],
        'p25': p25,
        'p75': p75,
        'std_dev': round((sum((c - avg)**2 for c in complexities) / len(complexities))**0.5, 2),
        'files_above_10': above_threshold,
        'files_below_5': below_threshold,
    }


def analyze_module_dependencies_depth(import_graph: dict, max_depth: int = 10) -> list:
    """Find deeply nested dependency chains."""
    chains = []
    
    def dfs(node, path, visited):
        if len(path) > max_depth or node in visited:
            if len(path) > 3:
                chains.append(list(path))
            return
        visited.add(node)
        path.append(node)
        for dep in import_graph.get(node, set()):
            dfs(dep, path, visited)
        path.pop()
        visited.discard(node)
    
    for module in list(import_graph.keys())[:50]:
        dfs(module, [], set())
    
    return sorted(chains, key=len, reverse=True)[:20]


def compute_maintainability_per_file(content: str, language: str) -> float:
    """Compute maintainability index for a single file."""
    lc = count_lines(content, language)
    cc = cyclomatic_complexity(content, language)
    total = lc['total']
    if total == 0:
        return 100.0
    
    comment_ratio = lc['comment'] / total
    halstead_vol = _halstead_volume(content)
    if halstead_vol == 0:
        halstead_vol = 1
    
    import math
    mi = 171.0 - 5.2 * math.log(halstead_vol) - 0.23 * cc - 16.2 * math.log(total)
    mi = max(0, mi)
    mi = mi * (comment_ratio + 1)
    return round(max(0, min(100, mi)), 1)


def analyze_import_patterns(import_details: dict) -> dict:
    """Analyze import patterns across languages."""
    summary = {}
    for lang, details in import_details.items():
        stdlib = details.get('stdlib', [])
        third_party = details.get('third_party', [])
        local = details.get('local', [])
        total = len(stdlib) + len(third_party) + len(local)
        
        if total > 0:
            summary[lang] = {
                'total': total,
                'stdlib_count': len(stdlib),
                'third_party_count': len(third_party),
                'local_count': len(local),
                'stdlib_ratio': round(len(stdlib) / total * 100, 1),
                'third_party_ratio': round(len(third_party) / total * 100, 1),
                'local_ratio': round(len(local) / total * 100, 1),
                'top_third_party': Counter(third_party).most_common(10),
                'top_stdlib': Counter(stdlib).most_common(10),
            }
    return summary


def detect_architectural_patterns(project_path: str, files_data: list, 
                                  import_graph: dict) -> list:
    """Detect common architectural patterns (MVC, MVVM, Clean Architecture, etc.)."""
    patterns = []
    all_names = set()
    
    for f in files_data:
        parts = f['path'].replace(os.sep, '/').split('/')
        all_names.update(parts)
    
    lower_names = {n.lower() for n in all_names}
    
    # MVC
    if 'models' in lower_names and ('views' in lower_names or 'controllers' in lower_names):
        patterns.append({'name': 'MVC', 'confidence': 'high',
                        'evidence': [n for n in all_names if n.lower() in ('models', 'views', 'controllers')]})
    
    # MVVM
    if 'viewmodels' in lower_names and 'views' in lower_names:
        patterns.append({'name': 'MVVM', 'confidence': 'high',
                        'evidence': ['viewmodels', 'views']})
    
    # Repository Pattern
    if 'repositories' in lower_names or 'repository' in lower_names:
        patterns.append({'name': 'Repository', 'confidence': 'medium',
                        'evidence': ['repository/repositories']})
    
    # Service Layer
    if 'services' in lower_names or 'service' in lower_names:
        patterns.append({'name': 'Service Layer', 'confidence': 'medium',
                        'evidence': ['service/services']})
    
    # Clean Architecture
    clean_parts = {'entities', 'usecases', 'controllers', 'adapters', 'frameworks'}
    found_clean = clean_parts & lower_names
    if len(found_clean) >= 3:
        patterns.append({'name': 'Clean Architecture', 'confidence': 'high',
                        'evidence': list(found_clean)})
    
    # Layered
    layers = {'presentation', 'business', 'data', 'domain', 'infrastructure', 'api', 'core'}
    found_layers = layers & lower_names
    if len(found_layers) >= 2:
        patterns.append({'name': 'Layered Architecture', 'confidence': 'medium',
                        'evidence': list(found_layers)})
    
    # Hexagonal
    if 'ports' in lower_names and 'adapters' in lower_names:
        patterns.append({'name': 'Hexagonal/Ports & Adapters', 'confidence': 'high',
                        'evidence': ['ports', 'adapters']})
    
    return patterns


def generate_complexity_report(functions: list) -> dict:
    """Generate a detailed complexity report for all functions."""
    if not functions:
        return {'total': 0, 'average': 0, 'max': 0, 'distribution': {}}
    
    complexities = [f['complexity'] for f in functions]
    total = len(functions)
    avg = sum(complexities) / total
    
    dist = {
        'trivial': sum(1 for c in complexities if c <= 3),
        'simple': sum(1 for c in complexities if 4 <= c <= 7),
        'moderate': sum(1 for c in complexities if 8 <= c <= 12),
        'complex': sum(1 for c in complexities if 13 <= c <= 20),
        'very_complex': sum(1 for c in complexities if 21 <= c <= 40),
        'extreme': sum(1 for c in complexities if c > 40),
    }
    
    cognitive = [f.get('cognitive_complexity', 0) for f in functions if 'cognitive_complexity' in f]
    
    return {
        'total': total,
        'average': round(avg, 2),
        'max': max(complexities) if complexities else 0,
        'median': complexities[len(complexities)//2],
        'distribution': dist,
        'top_complex': sorted(functions, key=lambda x: x['complexity'], reverse=True)[:10],
        'avg_cognitive': round(sum(cognitive) / len(cognitive), 2) if cognitive else 0,
        'high_risk_count': sum(1 for c in complexities if c > 15),
    }


def compute_code_age_analysis(files_data: list, project_path: str) -> list:
    """Analyze the age and evolution of files using git blame."""
    import subprocess
    age_data = []
    
    for f in files_data[:30]:
        rel = f['path']
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%aI', '--', rel],
                cwd=project_path, capture_output=True, text=True, timeout=5
            )
            date_str = result.stdout.strip()
            if date_str:
                age_data.append({
                    'file': rel,
                    'last_modified': date_str[:10],
                    'language': f['language'],
                    'complexity': f['complexity'],
                })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    return sorted(age_data, key=lambda x: x['last_modified'])


def analyze_documentation_coverage(files_data: list) -> dict:
    """Analyze documentation coverage across the codebase."""
    total_files = len(files_data)
    documented = 0
    partially_documented = 0
    undocumented = 0
    
    for f in files_data:
        cr = f.get('comment_ratio', 0)
        if cr >= 0.15:
            documented += 1
        elif cr >= 0.05:
            partially_documented += 1
        else:
            undocumented += 1
    
    return {
        'total_files': total_files,
        'documented': documented,
        'partially_documented': partially_documented,
        'undocumented': undocumented,
        'coverage_pct': round(documented / max(total_files, 1) * 100, 1),
        'partial_pct': round(partially_documented / max(total_files, 1) * 100, 1),
        'undocumented_pct': round(undocumented / max(total_files, 1) * 100, 1),
    }
