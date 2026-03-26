"""Code metrics — maintainability, Halstead, complexity, coupling, cohesion, health."""

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any

from .security import security_score


def calculate_health(analysis: Dict[str, Any]) -> Dict[str, int]:
    """Calculate overall and per-category health scores (0-100)."""
    scores: Dict[str, int] = {}
    total = analysis['total_lines']

    # Readability: comment ratio + complexity penalty
    if total['total'] > 0:
        comment_ratio = total['comment'] / total['total']
    else:
        comment_ratio = 0
    scores['readability'] = min(100, int(comment_ratio * 300 + 50))
    if analysis['avg_complexity'] > 15:
        scores['readability'] = max(0, scores['readability'] - 30)
    elif analysis['avg_complexity'] > 8:
        scores['readability'] = max(0, scores['readability'] - 15)
    long_lines = sum(1 for qi in analysis.get('quality_issues', [])
                     if qi.get('type') in ('long_line', 'very_long_line'))
    scores['readability'] = max(0, scores['readability'] - min(long_lines // 10, 20))

    # Complexity
    avg_cc = analysis['avg_complexity']
    scores['complexity'] = _complexity_score(avg_cc)

    # Duplication
    dup_count = len(analysis['duplicates'])
    file_count = max(analysis.get('total_files', 0), 1)
    dup_ratio = dup_count / file_count
    if dup_ratio < 0.01:
        scores['duplication'] = 95
    elif dup_ratio < 0.05:
        scores['duplication'] = 80
    elif dup_ratio < 0.1:
        scores['duplication'] = 60
    elif dup_ratio < 0.2:
        scores['duplication'] = 35
    else:
        scores['duplication'] = 15

    # Coverage (comment coverage)
    if total['total'] > 0:
        coverage_pct = (total['comment'] / total['total']) * 100
    else:
        coverage_pct = 0
    scores['coverage'] = min(100, int(coverage_pct * 2.5))

    # Security
    scores['security'] = security_score(analysis['security_issues'])

    # Dependencies
    dep_count = len(analysis['dependencies'])
    if dep_count == 0:
        scores['dependencies'] = 100
    elif dep_count <= 10:
        scores['dependencies'] = 90
    elif dep_count <= 30:
        scores['dependencies'] = 70
    elif dep_count <= 50:
        scores['dependencies'] = 50
    else:
        scores['dependencies'] = 30
    if analysis['circular_deps']:
        scores['dependencies'] = max(0, scores['dependencies'] - 20)
    if analysis['unused_imports']:
        scores['dependencies'] = max(0, scores['dependencies'] - 10)

    # Maintainability (composite)
    func_count = len(analysis.get('functions', []))
    avg_maint = 0
    if func_count > 0:
        avg_maint = sum(f.get('maintainability_index', 0)
                        for f in analysis.get('functions', [])) / func_count
    else:
        for f in analysis['files']:
            avg_maint += f.get('maintainability_index', 65)
        avg_maint = avg_maint / max(len(analysis['files']), 1)
    scores['maintainability'] = int(max(0, min(100, avg_maint)))

    # Overall: weighted average
    weights = {
        'readability': 0.15, 'complexity': 0.20, 'duplication': 0.10,
        'coverage': 0.10, 'security': 0.20, 'dependencies': 0.10,
        'maintainability': 0.15,
    }
    overall = sum(scores[k] * weights[k] for k in weights)
    scores['overall'] = int(overall)

    return scores


def _complexity_score(avg_cc: float) -> int:
    """Map average cyclomatic complexity to a 0-100 score."""
    if avg_cc <= 3:
        return 98
    elif avg_cc <= 5:
        return 95
    elif avg_cc <= 8:
        return 85
    elif avg_cc <= 10:
        return 75
    elif avg_cc <= 15:
        return 60
    elif avg_cc <= 20:
        return 45
    elif avg_cc <= 30:
        return 30
    elif avg_cc <= 50:
        return 15
    return 5


def maintainability_index(halstead_volume: float, cc: float,
                          loc: int, comment_ratio: float) -> float:
    """Calculate the Maintainability Index (MI) per the original formula.

    MI = 171 − 5.2 × ln(V) − 0.23 × G − 16.2 × ln(LOC)
    Where V = Halstead Volume, G = Cyclomatic Complexity, LOC = Lines of Code.
    Result is normalized to 0–100 and adjusted by comment ratio.
    """
    if loc == 0 or halstead_volume <= 0:
        return 100.0
    try:
        mi = 171.0 - 5.2 * math.log(halstead_volume) - 0.23 * cc - 16.2 * math.log(loc)
    except (ValueError, ZeroDivisionError):
        mi = 100.0
    mi = max(0, mi)
    mi *= (comment_ratio + 1)
    return round(max(0, min(100, mi)), 1)


def halstead_metrics(content: str, language: Optional[str] = None) -> Dict[str, float]:
    """Calculate Halstead software science metrics.

    Returns: n1 (unique operators), n2 (unique operands),
             N1 (total operators), N2 (total operands),
             N (program length), n (vocabulary),
             V (volume), D (difficulty), E (effort),
             T (time), B (bugs estimate).
    """
    operators = _count_operators(content, language)
    operands = _count_operands(content, language)

    n1 = len(operators)
    n2 = len(operands)
    N1 = sum(operators.values())
    N2 = sum(operands.values())
    N = N1 + N2
    n = n1 + n2

    if n == 0 or N == 0:
        return _empty_halstead()

    try:
        volume = N * math.log2(n)
    except (ValueError, ZeroDivisionError):
        volume = 0

    if n2 == 0:
        difficulty = 0
    else:
        difficulty = (n1 / 2) * (N2 / n2)

    effort = volume * difficulty
    time_est = effort / 18 if effort > 0 else 0
    bugs_est = volume / 3000 if volume > 0 else 0

    return {
        'n1': n1, 'n2': n2,
        'N1': N1, 'N2': N2,
        'N': N, 'n': n,
        'volume': round(volume, 1),
        'difficulty': round(difficulty, 2),
        'effort': round(effort, 1),
        'time': round(time_est, 2),
        'bugs': round(bugs_est, 4),
    }


def _empty_halstead() -> Dict[str, float]:
    return {'n1': 0, 'n2': 0, 'N1': 0, 'N2': 0, 'N': 0, 'n': 0,
            'volume': 0, 'difficulty': 0, 'effort': 0, 'time': 0, 'bugs': 0}


def _count_operators(content: str, language: Optional[str] = None) -> Dict[str, int]:
    """Count unique and total operators."""
    ops: Dict[str, int] = Counter()

    universal_ops = [
        (r'\+', 'add'), (r'-', 'sub'), (r'\*', 'mul'), (r'/', 'div'),
        (r'%', 'mod'), (r'\*\*', 'pow'), (r'//', 'floordiv'),
        (r'<<', 'lshift'), (r'>>', 'rshift'), (r'&', 'bitand'),
        (r'\|', 'bitor'), (r'\^', 'bitxor'), (r'~', 'bitnot'),
        (r'=', 'assign'), (r'==', 'eq'), (r'!=', 'neq'),
        (r'<', 'lt'), (r'>', 'gt'), (r'<=', 'lte'), (r'>=', 'gte'),
        (r'\+=', 'iadd'), (r'-=', 'isub'), (r'\*=', 'imul'), (r'/=', 'idiv'),
        (r'@', 'decorator'), (r':', 'colon'), (r',', 'comma'),
    ]

    if language in ('Python', 'Cython'):
        kw_ops = [
            r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
            r'\band\b', r'\bor\b', r'\bnot\b', r'\bin\b', r'\bis\b',
            r'\bclass\b', r'\bdef\b', r'\bwith\b', r'\bas\b', r'\bimport\b',
            r'\bfrom\b', r'\breturn\b', r'\braise\b', r'\byield\b',
            r'\blambda\b', r'\btry\b', r'\bexcept\b', r'\bfinally\b',
            r'\bassert\b', r'\bdel\b', r'\bglobal\b', r'\bnonlocal\b',
            r'\bawait\b', r'\basync\b',
        ]
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
            r'\bcase\b', r'\bfunction\b', r'\bclass\b', r'\breturn\b',
            r'\bthrow\b', r'\btry\b', r'\bcatch\b', r'\bfinally\b',
            r'\bnew\b', r'\btypeof\b', r'\binstanceof\b', r'\bin\b',
            r'\bof\b', r'\bvoid\b', r'\bdelete\b', r'\byield\b',
            r'\basync\b', r'\bawait\b', r'\bvar\b', r'\blet\b', r'\bconst\b',
        ]
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
            r'\bcase\b', r'\bclass\b', r'\breturn\b', r'\bthrow\b',
            r'\btry\b', r'\bcatch\b', r'\bfinally\b', r'\bnew\b',
            r'\binstanceof\b', r'\bthis\b', r'\bsuper\b',
            r'\bextends\b', r'\bimplements\b', r'\binterface\b',
        ]
    elif language in ('C', 'C++'):
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
            r'\bcase\b', r'\breturn\b', r'\bthrow\b', r'\btry\b',
            r'\bcatch\b', r'\bnew\b', r'\bdelete\b', r'\bthis\b',
            r'\bclass\b', r'\bstruct\b', r'\btemplate\b', r'\btypedef\b',
        ]
    elif language in ('Go',):
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b',
            r'\breturn\b', r'\bgo\b', r'\bchan\b', r'\bselect\b',
            r'\bdefer\b', r'\brange\b', r'\btype\b', r'\bstruct\b',
            r'\binterface\b', r'\bfunc\b', r'\bpackage\b', r'\bimport\b',
            r'\bvar\b', r'\bconst\b', r'\bmap\b',
        ]
    elif language in ('Rust',):
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bloop\b',
            r'\bmatch\b', r'\breturn\b', r'\bfn\b', r'\bstruct\b',
            r'\benum\b', r'\bimpl\b', r'\btrait\b', r'\blet\b', r'\bmut\b',
            r'\bpub\b', r'\buse\b', r'\bmod\b', r'\basync\b', r'\bawait\b',
        ]
    elif language in ('Ruby',):
        kw_ops = [
            r'\bif\b', r'\belif\b', r'\belse\b', r'\bunless\b', r'\bfor\b',
            r'\bwhile\b', r'\buntil\b', r'\bcase\b', r'\bwhen\b',
            r'\bdef\b', r'\bclass\b', r'\bmodule\b', r'\breturn\b',
            r'\byield\b', r'\bbegin\b', r'\brescue\b', r'\bensure\b',
            r'\brequire\b', r'\binclude\b', r'\bextend\b',
        ]
    else:
        kw_ops = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
            r'\bcase\b', r'\breturn\b', r'\bfunction\b', r'\bclass\b',
            r'\btry\b', r'\bcatch\b', r'\bthrow\b', r'\bnew\b',
        ]

    all_ops = universal_ops + [(p, p) for p in kw_ops]
    for pattern, name in all_ops:
        matches = re.findall(pattern, content)
        if matches:
            ops[name] += len(matches)

    if language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte', 'C', 'C++', 'Java', 'Kotlin', 'C#'):
        m = re.findall(r'&&', content)
        if m:
            ops['logical_and'] += len(m)
        m = re.findall(r'\|\|', content)
        if m:
            ops['logical_or'] += len(m)
        m = re.findall(r'\?\?', content)
        if m:
            ops['nullish_coalescing'] += len(m)
        m = re.findall(r'\.\.\.', content)
        if m:
            ops['spread'] += len(m)

    return dict(ops)


def _count_operands(content: str, language: Optional[str] = None) -> Dict[str, int]:
    """Count unique and total operands (identifiers, literals)."""
    operands: Dict[str, int] = Counter()

    if language in ('Python', 'Cython'):
        keywords = {
            'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return',
            'import', 'from', 'as', 'with', 'try', 'except', 'finally',
            'raise', 'yield', 'lambda', 'pass', 'break', 'continue',
            'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False',
            'self', 'global', 'nonlocal', 'assert', 'del', 'await', 'async',
            'print', 'range', 'len', 'str', 'int', 'float', 'list', 'dict',
            'set', 'tuple', 'bool', 'type', 'super', 'cls',
        }
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        keywords = {
            'if', 'else', 'for', 'while', 'switch', 'case', 'function',
            'return', 'throw', 'try', 'catch', 'finally', 'new', 'typeof',
            'instanceof', 'var', 'let', 'const', 'class', 'export', 'import',
            'from', 'as', 'default', 'async', 'await', 'yield', 'this',
            'super', 'null', 'undefined', 'true', 'false', 'void', 'delete',
            'in', 'of', 'console', 'window', 'document', 'process', 'module',
        }
    elif language in ('Go',):
        keywords = {
            'if', 'else', 'for', 'switch', 'case', 'return', 'go', 'chan',
            'select', 'defer', 'range', 'type', 'struct', 'interface',
            'func', 'package', 'import', 'var', 'const', 'map', 'nil',
            'true', 'false', 'break', 'continue', 'fallthrough', 'make',
            'append', 'len', 'fmt', 'error', 'string', 'int', 'bool',
        }
    elif language in ('Rust',):
        keywords = {
            'if', 'else', 'for', 'while', 'loop', 'match', 'return', 'fn',
            'struct', 'enum', 'impl', 'trait', 'let', 'mut', 'pub', 'use',
            'mod', 'async', 'await', 'self', 'Self', 'super', 'true', 'false',
            'Some', 'None', 'Ok', 'Err', 'String', 'Vec', 'Box', 'Result',
        }
    else:
        keywords = {
            'if', 'else', 'for', 'while', 'return', 'function', 'class',
            'true', 'false', 'null', 'this', 'new', 'var', 'const', 'let',
        }

    identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', content)
    for ident in identifiers:
        if ident not in keywords:
            operands[ident] += 1

    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', content)
    for num in numbers:
        operands[num] += 1

    strings = re.findall(r'r?[f]?"""[\s\S]*?"""|r?[f]?\'\'\'[\s\S]*?\'\'\'|r?[f]?"[^"]*"|r?[f]?\'[^\']*\'', content)
    for s in strings:
        if len(s) > 2:
            operands[s[:30]] += 1

    return dict(operands)


def cyclomatic_complexity_per_function(content: str, language: Optional[str] = None) -> List[Dict]:
    """Calculate cyclomatic complexity for each function in the content."""
    from .utils import detect_functions, cyclomatic_complexity

    functions = detect_functions(content, language)
    lines = content.split('\n')
    for func in functions:
        start = func['start_line'] - 1
        end = min(func['end_line'], len(lines))
        func_content = '\n'.join(lines[start:end])
        func['complexity'] = cyclomatic_complexity(func_content, language)
    return functions


def coupling_metrics(import_graph: Dict[str, set], module_files: Dict[str, List[str]]) -> Dict[str, Any]:
    """Calculate module coupling metrics.

    Returns: afferent_coupling (Ca), efferent_coupling (Ce),
             instability (I = Ce / (Ca + Ce)), abstractness.
    """
    if not import_graph:
        return {'instability': 0, 'coupling_ratio': 0, 'avg_fan_out': 0}

    all_modules = set(import_graph.keys())
    for targets in import_graph.values():
        all_modules.update(targets)

    afferent: Dict[str, int] = Counter()
    efferent: Dict[str, int] = Counter()

    for module, targets in import_graph.items():
        efferent[module] = len(targets)
        for t in targets:
            afferent[t] += 1

    instabilities = {}
    for m in all_modules:
        ca = afferent.get(m, 0)
        ce = efferent.get(m, 0)
        total = ca + ce
        if total > 0:
            instabilities[m] = ce / total
        else:
            instabilities[m] = 0

    avg_inst = sum(instabilities.values()) / max(len(instabilities), 1)
    avg_fan = sum(efferent.values()) / max(len(efferent), 1)
    fan_outs = list(efferent.values())
    high_fan = [m for m, fo in efferent.items() if fo > avg_fan * 2]

    return {
        'instability': round(avg_inst, 3),
        'coupling_ratio': round(avg_fan / max(len(all_modules), 1), 3),
        'avg_fan_out': round(avg_fan, 1),
        'high_fan_out_modules': high_fan[:20],
        'afferent': dict(afferent.most_common(20)),
        'efferent': dict(efferent.most_common(20)),
    }


def cohesion_metric(content: str, language: Optional[str] = None) -> float:
    """Estimate LCOM (Lack of Cohesion of Methods) for a class/module.

    Returns 0 (highly cohesive) to 1 (low cohesion).
    """
    from .utils import detect_functions

    functions = detect_functions(content, language)
    if len(functions) < 2:
        return 0.0

    all_identifiers = set()
    func_identifiers: List[set] = []
    for func in functions:
        lines = content.split('\n')
        start = func['start_line'] - 1
        end = min(func['end_line'], len(lines))
        func_content = '\n'.join(lines[start:end])
        idents = set(re.findall(r'\b[a-zA-Z_]\w*\b', func_content))
        keywords = {
            'if', 'else', 'for', 'while', 'return', 'def', 'class', 'import',
            'from', 'as', 'with', 'try', 'except', 'raise', 'yield', 'lambda',
            'pass', 'break', 'continue', 'and', 'or', 'not', 'in', 'is',
            'None', 'True', 'False', 'self', 'print', 'range', 'len', 'str',
            'int', 'float', 'list', 'dict', 'set', 'tuple', 'bool', 'type',
            'super', 'cls', 'const', 'let', 'var', 'function', 'new', 'this',
            'true', 'false', 'null', 'undefined', 'async', 'await', 'return',
        }
        idents -= keywords
        func_identifiers.append(idents)
        all_identifiers.update(idents)

    if not all_identifiers:
        return 0.0

    shared_pairs = 0
    total_pairs = 0
    n = len(func_identifiers)
    for i in range(n):
        for j in range(i + 1, n):
            shared = func_identifiers[i] & func_identifiers[j]
            total = func_identifiers[i] | func_identifiers[j]
            if total:
                shared_pairs += len(shared)
                total_pairs += len(total)

    if total_pairs == 0:
        return 0.0
    lcom = 1 - (shared_pairs / total_pairs)
    return round(max(0, min(1, lcom)), 3)


def get_trend(score: int) -> str:
    """Get trend indicator for a score."""
    if score >= 80:
        return 'good'
    elif score >= 50:
        return 'warning'
    return 'critical'


def generate_recommendations(analysis: Dict, scores: Dict[str, int]) -> List[Dict]:
    """Generate prioritized improvement recommendations."""
    recs: List[Dict] = []

    if scores.get('readability', 100) < 60:
        recs.append({
            'icon': '📖', 'category': 'Readability', 'priority': 'high',
            'message': f"Average complexity is {analysis['avg_complexity']:.1f}. Consider breaking down complex functions into smaller, focused units.",
        })

    if scores.get('coverage', 100) < 50:
        total = analysis['total_lines']
        pct = (total['comment'] / total['total'] * 100) if total['total'] > 0 else 0
        recs.append({
            'icon': '💬', 'category': 'Documentation', 'priority': 'medium',
            'message': f"Comment coverage is only {pct:.1f}%. Add docstrings and inline comments to improve maintainability.",
        })

    if analysis.get('duplicates'):
        recs.append({
            'icon': '♻️', 'category': 'Duplication', 'priority': 'high',
            'message': f"Found {len(analysis['duplicates'])} duplicated code blocks. Extract shared logic into reusable functions.",
        })

    if analysis.get('security_issues'):
        crit = sum(1 for i in analysis['security_issues'] if i['severity'] == 'critical')
        high = sum(1 for i in analysis['security_issues'] if i['severity'] == 'high')
        recs.append({
            'icon': '🔒', 'category': 'Security', 'priority': 'critical',
            'message': f"Found {len(analysis['security_issues'])} security issues ({crit} critical, {high} high). Move secrets to environment variables and fix dangerous patterns.",
        })

    if analysis.get('circular_deps'):
        recs.append({
            'icon': '🔄', 'category': 'Dependencies', 'priority': 'high',
            'message': f"Detected {len(analysis['circular_deps'])} circular import chains. Refactor module structure to break cycles.",
        })

    if len(analysis.get('dependencies', [])) > 30:
        recs.append({
            'icon': '📦', 'category': 'Dependencies', 'priority': 'medium',
            'message': f"Project has {len(analysis['dependencies'])} dependencies. Audit for unused packages to reduce attack surface.",
        })

    if analysis['max_complexity'] > 20:
        complex_files = [f for f in analysis['files'] if f['complexity'] > 20][:5]
        names = ', '.join(f['path'] for f in complex_files)
        recs.append({
            'icon': '⚠️', 'category': 'Complexity', 'priority': 'high',
            'message': f"Highest complexity score: {analysis['max_complexity']}. Hot spots: {names}",
        })

    if scores.get('maintainability', 100) < 50:
        recs.append({
            'icon': '🔧', 'category': 'Maintainability', 'priority': 'high',
            'message': "Maintainability index is low. Consider refactoring complex modules, improving documentation, and reducing function sizes.",
        })

    long_funcs = [f for f in analysis.get('functions', []) if f['line_count'] > 50]
    if len(long_funcs) > 5:
        recs.append({
            'icon': '📏', 'category': 'Function Size', 'priority': 'medium',
            'message': f"{len(long_funcs)} functions exceed 50 lines. Consider splitting them for better readability and testability.",
        })

    deep_funcs = [f for f in analysis.get('functions', []) if f['nesting_depth'] > 4]
    if len(deep_funcs) > 3:
        recs.append({
            'icon': '↕️', 'category': 'Nesting Depth', 'priority': 'medium',
            'message': f"{len(deep_funcs)} functions have nesting depth > 4. Use early returns and extract methods to reduce nesting.",
        })

    many_args = [f for f in analysis.get('functions', []) if f['param_count'] > 5]
    if len(many_args) > 3:
        recs.append({
            'icon': '📝', 'category': 'Function Arguments', 'priority': 'low',
            'message': f"{len(many_args)} functions have more than 5 parameters. Consider using dataclasses or configuration objects.",
        })

    todo_count = len(analysis.get('todos', []))
    if todo_count > 10:
        recs.append({
            'icon': '📋', 'category': 'Technical Debt', 'priority': 'low',
            'message': f"Found {todo_count} TODO/FIXME/HACK comments. Consider addressing these to reduce technical debt.",
        })

    if not recs:
        recs.append({
            'icon': '✨', 'category': 'Overall', 'priority': 'low',
            'message': "Codebase looks healthy! Keep up the good work.",
        })

    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    recs.sort(key=lambda r: priority_order.get(r['priority'], 4))
    return recs
