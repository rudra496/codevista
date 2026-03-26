"""Utility functions — file discovery, comment detection, code analysis helpers.

Language-aware comment detection, function detection, duplication analysis,
TODO extraction, quality checks, and color schemes. Zero external dependencies.
"""

import os
import re
import hashlib
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any, Set

from .config import should_ignore, DEFAULT_CONFIG
from .languages import detect_language, get_lang_color, get_comment_syntax


def discover_files(project_path: str,
                   max_depth: Optional[int] = None,
                   ignore_patterns: Optional[Set[str]] = None,
                   config: Optional[Dict] = None) -> List[str]:
    """Walk directory tree and return list of source files.
    
    Respects .gitignore, .codevistaignore, binary extensions,
    vendored directories, hidden files, and file size limits.
    """
    if config is None:
        config = DEFAULT_CONFIG
    files: List[str] = []
    for root, dirs, filenames in os.walk(project_path):
        dirs[:] = sorted([d for d in dirs if not should_ignore(
            os.path.join(root, d), project_path, ignore_patterns)])

        if max_depth is not None:
            rel_depth = os.path.relpath(root, project_path).replace('\\', '/').count('/')
            if rel_depth > max_depth:
                dirs[:] = []
                continue

        for fname in sorted(filenames):
            fpath = os.path.join(root, fname)
            if should_ignore(fpath, project_path, ignore_patterns):
                continue
            try:
                if os.path.getsize(fpath) > config['max_file_size']:
                    continue
            except OSError:
                continue
            files.append(fpath)
    return files


def read_file_safe(filepath: str) -> str:
    """Read file with encoding fallback chain."""
    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'ascii', 'cp1252'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError, FileNotFoundError, OSError):
            continue
    return ''


def is_binary_file(filepath: str) -> bool:
    """Check if a file appears to be binary by reading first 8192 bytes."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(8192)
        if b'\x00' in chunk:
            return True
        text_chars = set(range(32, 127)) | {9, 10, 13}
        non_text = sum(1 for b in chunk if b not in text_chars)
        return non_text / max(len(chunk), 1) > 0.3
    except OSError:
        return True


def count_lines(content: str, language: Optional[str] = None) -> Dict[str, int]:
    """Count total, code, blank, and comment lines with language-aware detection."""
    lines = content.split('\n')
    total = max(len(lines) - (1 if lines and lines[-1] == '' else 0), 0)
    blank = sum(1 for l in lines if not l.strip())
    if lines and lines[-1] == '':
        blank -= 1

    comment = 0
    if language:
        line_prefixes, block_open, block_close = get_comment_syntax(language)
        in_block = False
        for line in lines:
            stripped = line.strip()
            if in_block:
                if block_close and block_close in stripped:
                    in_block = False
                comment += 1
                continue
            if block_open and block_close:
                if block_open in stripped and block_close in stripped[len(block_open):]:
                    comment += 1
                    continue
                if block_open in stripped:
                    in_block = True
                    comment += 1
                    continue
            if line_prefixes:
                for prefix in line_prefixes:
                    if stripped.startswith(prefix):
                        comment += 1
                        break
    else:
        comment = sum(1 for l in lines if _is_generic_comment(l))

    code = max(total - blank - comment, 0)
    return {'total': total, 'code': code, 'blank': blank, 'comment': comment}


def is_comment_line(line: str, language: Optional[str] = None) -> bool:
    """Check if a single line is a comment."""
    stripped = line.strip()
    if not stripped:
        return False
    if language:
        prefixes, _, _ = get_comment_syntax(language)
        if prefixes:
            return any(stripped.startswith(p) for p in prefixes)
    return _is_generic_comment(stripped)


def _is_generic_comment(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return (s.startswith('#') or s.startswith('//') or
            s.startswith('/*') or s.startswith('*') or s.startswith('--') or
            s.startswith('<!--') or s.startswith('%') or s.startswith(';'))


def cyclomatic_complexity(content: str, language: Optional[str] = None) -> int:
    """Calculate cyclomatic complexity (McCabe metric).

    Counts branching points (if, for, while, except, case, &&, ||, etc.)
    minus function definitions + 1. Returns 1 for non-code files.
    """
    non_code = ('HTML', 'CSS', 'SCSS', 'Less', 'JSON', 'YAML', 'TOML', 'XML',
                'Markdown', 'INI', 'Lockfile', 'CSV', 'Text', 'Dockerfile',
                'Makefile', 'CMake', 'GraphQL', 'Protocol Buffers', 'PostCSS')
    if language in non_code:
        return 0

    if not content.strip():
        return 0

    if language in ('Python', 'Cython'):
        branch_pats = [r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
                       r'\bexcept\b', r'\bwith\b', r'\band\b', r'\bor\b', r'\blambda\b']
        func_pat = r'\bdef\b'
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        branch_pats = [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                       r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|', r'\?']
        func_pat = r'\bfunction\b|\b(?:const|let|var)\s+\w+\s*='
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        branch_pats = [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                       r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|']
        func_pat = r'\b(?:public|private|protected|static|void)\s+\w+'
    elif language in ('Go',):
        branch_pats = [r'\bif\b', r'\bfor\b', r'\bcase\b', r'&&', r'\|\|', r'\bselect\b']
        func_pat = r'\bfunc\b'
    elif language in ('Rust',):
        branch_pats = [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                       r'\bloop\b', r'\bmatch\b', r'&&', r'\|\|']
        func_pat = r'\bfn\b'
    elif language in ('C', 'C++'):
        branch_pats = [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                       r'\bcase\b', r'&&', r'\|\|', r'\?']
        func_pat = r'\b(?:def|fn|func)\b'
    elif language in ('Ruby',):
        branch_pats = [r'\bif\b', r'\belif\b', r'\bunless\b', r'\bwhile\b',
                       r'\bfor\b', r'\bwhen\b', r'&&', r'\|\|']
        func_pat = r'\bdef\b'
    else:
        branch_pats = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
                       r'\bcase\b', r'\bcatch\b', r'\bexcept\b', r'\band\b',
                       r'\bor\b', r'&&', r'\|\|']
        func_pat = r'\b(?:def|function|fn|func)\b'

    pattern = '|'.join(branch_pats)
    branch_count = len(re.findall(pattern, content))
    func_count = len(re.findall(func_pat, content))
    # Per-function: CC = 1 + decision points
    # For whole file: CC = decision_points + number_of_functions
    if func_count > 0:
        return max(branch_count + 1, 1)
    return branch_count + 1 if content.strip() else 0


def cognitive_complexity(content: str, language: Optional[str] = None) -> int:
    """Calculate cognitive complexity based on nesting depth and logical operators.

    Unlike cyclomatic complexity, cognitive complexity accounts for nesting
    and structural breaks, giving a more accurate measure of code difficulty.
    """
    non_code = ('HTML', 'CSS', 'SCSS', 'Less', 'JSON', 'YAML', 'TOML', 'XML',
                'Markdown', 'INI', 'Lockfile', 'CSV', 'Text')
    if language in non_code:
        return 0

    complexity = 0
    nesting = 0
    nesting_kw = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
                  r'\bexcept\b', r'\bwith\b', r'\bcase\b', r'\bcatch\b', r'\bmatch\b']
    increment_kw = [r'\band\b', r'\bor\b', r'&&', r'\|\|']

    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('//'):
            continue

        found_nesting = False
        for pat in nesting_kw:
            if re.search(pat, stripped):
                nesting += 1
                complexity += nesting
                found_nesting = True
                break

        if not found_nesting:
            for pat in increment_kw:
                if re.search(pat, stripped):
                    complexity += 1
                    break

        if stripped.startswith('}') or stripped.startswith('end') or stripped.startswith('fi') or stripped.startswith('done'):
            nesting = max(0, nesting - 1)

    return complexity


def extract_imports(content: str, language: Optional[str] = None) -> List[str]:
    """Extract import statements from source code.

    Supports Python, JavaScript/TypeScript, Go, Java, C/C++, Ruby,
    Rust, Swift, Dart, PHP, Kotlin, Scala, OCaml, Lua, and others.
    """
    imports: List[str] = []
    if language in ('Python', 'Cython'):
        imports = re.findall(r'^(?:from|import)\s+([^\s;,#]+)', content, re.MULTILINE)
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        imports = re.findall(r'(?:import|require)\s*[\(\'"]?([^\'")\s;]+)', content)
    elif language == 'Go':
        imports = re.findall(r'import\s+"([^"]+)"', content)
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        imports = re.findall(r'import\s+([^\s;]+)', content)
    elif language in ('C', 'C++'):
        imports = re.findall(r'#include\s*[<"]([^>"]+)[>"]', content)
    elif language in ('Ruby',):
        imports = re.findall(r'(?:require|gem)\s+[\'"]([^\'"]+)[\'"]', content)
    elif language == 'Rust':
        imports = re.findall(r'use\s+([^\s;]+)', content)
    elif language == 'Swift':
        imports = re.findall(r'import\s+([^\s;]+)', content)
    elif language == 'Dart':
        imports = re.findall(r"import\s+['\"]([^'\"]+)['\"]", content)
    elif language == 'PHP':
        imports = re.findall(r'(?:use|require|include)\s+[\'"]?([^\'";\s]+)', content)
    elif language == 'Lua':
        imports = re.findall(r'require\s*[("\']?([^"\'\s]+)', content)
    elif language in ('Elixir',):
        imports = re.findall(r'(?:require|import|alias|use)\s+([^\s]+)', content)
    elif language in ('Haskell',):
        imports = re.findall(r'^import\s+(?:qualified\s+)?([A-Z][\w.]*)', content, re.MULTILINE)
    return imports


def normalize_import(imp: str) -> str:
    """Normalize import to base module/package name."""
    base = imp.split('.')[0].split('/')[0].split('\\')[0].lower()
    return base.replace('-', '_')


def is_stdlib_import(imp: str, language: str) -> bool:
    """Check if an import is from the standard library."""
    stdlib = {
        'Python': {'os', 'sys', 're', 'json', 'math', 'time', 'datetime', 'collections',
                    'itertools', 'functools', 'typing', 'pathlib', 'io', 'abc', 'copy',
                    'hashlib', 'logging', 'argparse', 'subprocess', 'threading', 'multiprocessing',
                    'socket', 'http', 'urllib', 'email', 'html', 'xml', 'csv', 'sqlite3',
                    'unittest', 'dataclasses', 'enum', 'struct', 'array', 'decimal',
                    'fractions', 'random', 'statistics', 'string', 'textwrap', 'difflib',
                    'pprint', 'operator', 'pickle', 'shutil', 'glob', 'fnmatch', 'traceback',
                    'warnings', 'contextlib', 'atexit', 'asyncio', 'concurrent', 'ssl',
                    'signal', 'mmap', 'ctypes', 'weakref', 'types', 'builtins', 'ast',
                    'token', 'tokenize', 'configparser', 'base64', 'binascii', 'tempfile',
                    'linecache', 'dis', 'inspect', 'code', 'encodings', 'codecs', 'unicodedata',
                    'gettext', 'locale', 'calendar', 'sched', 'gzip', 'bz2', 'lzma', 'zipfile',
                    'tarfile', 'zlib', 'queue', 'selectors', 'socketserver'},
        'JavaScript': {'fs', 'path', 'http', 'https', 'url', 'util', 'stream', 'crypto',
                       'os', 'events', 'child_process', 'cluster', 'net', 'dns', 'tls',
                       'assert', 'buffer', 'console', 'process', 'vm', 'zlib'},
        'Go': {'fmt', 'os', 'io', 'net', 'http', 'time', 'sync', 'encoding', 'json',
               'strings', 'strconv', 'math', 'flag', 'log', 'path', 'regexp', 'sort',
               'container', 'context', 'crypto', 'database', 'debug', 'errors', 'runtime',
               'testing', 'text', 'unicode', 'unsafe', 'bufio', 'bytes', 'reflect'},
        'Java': {'java.lang', 'java.util', 'java.io', 'java.net', 'java.math', 'java.time',
                 'java.text', 'java.nio', 'java.sql', 'java.awt', 'java.swing',
                 'java.util.concurrent', 'java.util.stream', 'java.util.function'},
        'Rust': {'std', 'core', 'alloc', 'proc_macro'},
    }
    base = normalize_import(imp)
    return base in stdlib.get(language, set())


def compute_file_hash(content: str) -> str:
    """Hash file content for duplicate detection."""
    return hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()


def normalize_for_duplication(content: str) -> str:
    """Normalize code for duplication: strip strings, comments, whitespace."""
    content = re.sub(r'r?"""[\s\S]*?"""', '""', content)
    content = re.sub(r"r?'''[\s\S]*?'''", "''", content)
    content = re.sub(r"""r?f?'''[\s\S]*?'''""", '""', content)
    content = re.sub(r'r?f?"""[\s\S]*?"""', '""', content)
    content = re.sub(r'''r?f?"(?:[^"\\]|\\.)*"''', '""', content)
    content = re.sub(r"""r?f?'(?:[^'\\]|\\.)*'""", '""', content)
    content = re.sub(r'#[^\n]*', '', content)
    content = re.sub(r'//[^\n]*', '', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'\s+', ' ', content).strip()
    return content


def block_hash(content: str, block_size: int = 6) -> List[str]:
    """Create rolling hashes of code blocks for duplication detection."""
    lines = content.split('\n')
    blocks: List[str] = []
    for i in range(len(lines) - block_size + 1):
        block = '\n'.join(lines[i:i + block_size])
        normalized = normalize_for_duplication(block)
        if len(normalized) > 50:
            blocks.append(hashlib.md5(normalized.encode()).hexdigest())
    return blocks


def detect_functions(content: str, language: Optional[str] = None) -> List[Dict]:
    """Detect function/method definitions with metadata.

    Returns list of dicts with: name, start_line, end_line, line_count,
    complexity, cognitive_complexity, params, param_count, nesting_depth.
    Supports 15+ languages.
    """
    functions: List[Dict] = []
    lines = content.split('\n')

    patterns = _get_function_pattern(language)
    if not patterns:
        return functions

    pattern = re.compile(patterns, re.MULTILINE)
    for m in pattern.finditer(content):
        name = m.group('name') or m.group(3) or '<anonymous>'
        params_str = m.group('params') or ''
        params = [p.strip() for p in params_str.split(',') if p.strip()]
        line_num = content[:m.start()].count('\n') + 1
        end_line = _find_function_end(lines, line_num - 1, language)
        func_lines = lines[line_num - 1:end_line]
        func_content = '\n'.join(func_lines)
        cc = cyclomatic_complexity(func_content, language)
        cog = cognitive_complexity(func_content, language)
        max_nest = _max_nesting_depth(func_content)

        functions.append({
            'name': name,
            'file': '',
            'start_line': line_num,
            'end_line': end_line,
            'line_count': end_line - line_num + 1,
            'params': params,
            'param_count': len(params),
            'complexity': cc,
            'cognitive_complexity': cog,
            'nesting_depth': max_nest,
        })

    return functions


def _get_function_pattern(language):
    """Get regex pattern for function definitions per language."""
    if language in ('Python', 'Cython'):
        return r'(?m)^\s*(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        return r'(?m)(?:export\s+)?(?:async\s+)?function\s*(?P<name>\w*)\s*\((?P<params>[^)]*)\)'
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        return r'(?m)(?:public|private|protected|static|abstract|synchronized|override)?\s*[\w<>\[\]]+\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('C', 'C++'):
        return r'(?m)[\w<>\[\]&*:]+\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('Go',):
        return r'(?m)func\s+(?:\([^)]*\)\s+)?(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('Rust',):
        return r'(?m)fn\s+(?P<name>\w+)\s*(?:<[^>]*>)?\s*\((?P<params>[^)]*)\)'
    elif language in ('Ruby',):
        return r'(?m)def\s+(?:self\.)?(?P<name>\w+)\s*(?:\((?P<params>[^)]*)\))?'
    elif language in ('Swift',):
        return r'(?m)func\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('PHP',):
        return r'(?m)function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
    elif language in ('Dart',):
        return r'(?m)(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?:\{|async)'
    return None


def _find_function_end(lines: List[str], start_idx: int, language: Optional[str]) -> int:
    """Find approximate end line of a function."""
    if language in ('Python', 'Cython', 'Ruby'):
        if start_idx >= len(lines):
            return len(lines)
        base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        for i in range(start_idx + 1, len(lines)):
            if lines[i].strip() and not lines[i].strip().startswith('#'):
                curr_indent = len(lines[i]) - len(lines[i].lstrip())
                if curr_indent <= base_indent:
                    return i
        return len(lines)
    else:
        depth = 0
        started = False
        for i in range(start_idx, min(start_idx + 500, len(lines))):
            for ch in lines[i]:
                if ch == '{':
                    depth += 1
                    started = True
                elif ch == '}':
                    depth -= 1
                    if started and depth <= 0:
                        return i + 1
        return min(start_idx + 100, len(lines))


def _max_nesting_depth(content: str) -> int:
    """Calculate maximum nesting depth using indentation levels."""
    max_depth = 0
    current = 0
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('//'):
            continue
        indent = len(line) - len(line.lstrip())
        level = indent // 4
        if level > current:
            current = level
        elif level < current:
            current = level
        max_depth = max(max_depth, current)
    return max_depth


def extract_todos(content: str) -> List[Dict]:
    """Extract TODO/FIXME/HACK/XXX/NOTE/BUG comments."""
    todos: List[Dict] = []
    pattern = re.compile(
        r'(?:(?:#|//|<!--|/\*)\s*)?(TODO|FIXME|HACK|XXX|NOTE|BUG|OPTIMIZE|REVIEW)\b[:\s]*(.*)',
        re.IGNORECASE
    )
    for line_num, line in enumerate(content.split('\n'), 1):
        for m in pattern.finditer(line):
            tag = m.group(1).upper()
            text = m.group(2).strip()
            todos.append({'tag': tag, 'text': text, 'line': line_num})
    return todos


def detect_quality_issues(content: str, language: Optional[str] = None,
                         filepath: str = '') -> List[Dict]:
    """Detect code quality issues across multiple categories."""
    issues: List[Dict] = []
    lines = content.split('\n')
    max_line = DEFAULT_CONFIG.get('max_line_length', 88)
    warn_line = DEFAULT_CONFIG.get('max_line_length_warn', 120)

    for i, line in enumerate(lines, 1):
        line_len = len(line)
        if line_len > warn_line:
            issues.append({'type': 'very_long_line', 'severity': 'high',
                          'line': i, 'message': f'Line is {line_len} chars (>{warn_line})', 'file': filepath})
        elif line_len > max_line:
            issues.append({'type': 'long_line', 'severity': 'medium',
                          'line': i, 'message': f'Line is {line_len} chars (>{max_line})', 'file': filepath})
        if line != line.rstrip():
            issues.append({'type': 'trailing_whitespace', 'severity': 'low',
                          'line': i, 'message': 'Trailing whitespace', 'file': filepath})
        if '\t' in line and '    ' in line:
            issues.append({'type': 'mixed_indent', 'severity': 'medium',
                          'line': i, 'message': 'Mixed tabs and spaces', 'file': filepath})

    # Language-specific checks
    if language in ('Python', 'Cython'):
        for m in re.finditer(r'except\s*[\w,\s]*:\s*$', content, re.MULTILINE):
            line_num = content[:m.start()].count('\n') + 1
            issues.append({'type': 'empty_except', 'severity': 'medium',
                          'line': line_num, 'message': 'Empty except block', 'file': filepath})
        for m in re.finditer(r'^\s*except\s*:', content, re.MULTILINE):
            line_num = content[:m.start()].count('\n') + 1
            issues.append({'type': 'bare_except', 'severity': 'medium',
                          'line': line_num, 'message': 'Bare except (too broad)', 'file': filepath})
        for m in re.finditer(r'def\s+\w+\s*\([^)]*(=\s*\[\]|=\s*\{\}|=\s*set\(\))', content):
            line_num = content[:m.start()].count('\n') + 1
            issues.append({'type': 'mutable_default', 'severity': 'medium',
                          'line': line_num, 'message': 'Mutable default argument', 'file': filepath})
        for m in re.finditer(r'from\s+[\w.]+\s+import\s+\*', content):
            line_num = content[:m.start()].count('\n') + 1
            issues.append({'type': 'star_import', 'severity': 'medium',
                          'line': line_num, 'message': 'Star import (from x import *)', 'file': filepath})
        # Dead code after return/raise
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('return ') or stripped.startswith('raise '):
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('#') and not next_line.startswith('def ') and next_line != '':
                        issues.append({'type': 'dead_code', 'severity': 'low',
                                      'line': j + 1, 'message': 'Code after return/raise may be unreachable', 'file': filepath})
                        break
                    if not next_line:
                        continue
                    break

    return issues


def find_duplicate_strings(content: str, min_length: int = 20,
                           min_occurrences: int = 3) -> List[Dict]:
    """Find duplicate string literals in code."""
    string_pattern = re.compile(r'r?[f]?["\']([^"\']{20,})["\']')
    strings = [m.group(1) for m in string_pattern.finditer(content)]
    counter = Counter(strings)
    return [{'string': s[:50] + '...' if len(s) > 50 else s,
             'count': c, 'length': len(s)}
            for s, c in counter.most_common(20) if c >= min_occurrences]


# ── Color Schemes ────────────────────────────────────────────────────────────

COLORS = {
    'bg': '#0a0a1a', 'surface': '#12122a', 'surface2': '#1a1a3e',
    'text': '#eeeef5', 'text2': '#8888aa', 'text3': '#5a5a7a',
    'primary': '#7f5af0', 'primary_light': '#a78bfa',
    'green': '#2cb67d', 'accent': '#e53170', 'warning': '#ff8906',
    'info': '#38bdf8', 'teal': '#14b8a6',
}

SEVERITY_COLORS = {
    'critical': '#e53170', 'high': '#ff8906', 'medium': '#7f5af0',
    'low': '#a7a9be', 'info': '#72757e',
}

TREND_COLORS = {
    'good': '#2cb67d', 'warning': '#ff8906', 'critical': '#e53170',
}
