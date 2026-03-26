"""Configuration loading, ignore patterns, and defaults.

Handles .codevistaignore files, .editorconfig integration,
.gitignore support, and project-level settings.
"""

import os
import re
from typing import Dict, List, Optional, Set, Tuple, Any


DEFAULT_CONFIG: Dict[str, Any] = {
    'max_file_size': 1_000_000,
    'max_depth': None,
    'include_hidden': False,
    'include_vendored': False,
    'complexity_threshold': 10,
    'cognitive_complexity_threshold': 15,
    'max_line_length': 88,
    'max_line_length_warn': 120,
    'max_function_length': 50,
    'max_function_args': 5,
    'max_nesting_depth': 4,
    'duplication_block_size': 6,
    'duplication_min_lines': 50,
    'duplication_threshold': 0.3,
    'binary_extensions': {
        '.pyc', '.pyo', '.class', '.o', '.so', '.dll', '.dylib', '.a', '.lib',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.zst',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.wav', '.ogg',
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        '.exe', '.msi', '.dmg', '.app', '.deb', '.rpm',
        '.sqlite', '.db', '.bak', '.wasm', '.nib', '.storyboard',
        '.xib', '.pbxproj', '.parquet', '.arrow', '.feather', '.pyd', '.node',
    },
    'vendored_dirs': {
        'node_modules', 'vendor', '.venv', 'venv', 'env',
        '__pycache__', '.tox', '.eggs', '*.egg-info',
        'dist', 'build', '.next', '.nuxt', 'target',
        '.mypy_cache', '.pytest_cache', '.ruff_cache', '.cache',
        '.gradle', '.idea', '.vscode', 'coverage',
        '.terraform', '.serverless', '.turbo',
        'bower_components', '.cache', '.parcel-cache',
        '.nx', '.dart_tool', '.pub-cache',
        'Pods', 'Carthage', '.bundle',
    },
    'ignore_patterns': [
        '.git', '.svn', '.hg', '.codevistaignore',
    ],
}


def load_config(project_path: str) -> Set[str]:
    """Load ignore patterns from .codevistaignore, .gitignore, and defaults."""
    patterns = set(DEFAULT_CONFIG['ignore_patterns'])

    codevista_ignore = os.path.join(project_path, '.codevistaignore')
    if os.path.isfile(codevista_ignore):
        patterns.update(_parse_ignore_file(codevista_ignore))

    gitignore = os.path.join(project_path, '.gitignore')
    if os.path.isfile(gitignore):
        patterns.update(_parse_ignore_file(gitignore))

    parent = os.path.dirname(project_path)
    while parent and parent != project_path:
        parent_ignore = os.path.join(parent, '.gitignore')
        if os.path.isfile(parent_ignore):
            patterns.update(_parse_ignore_file(parent_ignore))
        new_parent = os.path.dirname(parent)
        if new_parent == parent:
            break
        parent = new_parent

    return patterns


def load_editorconfig(project_path: str) -> Dict[str, Any]:
    """Parse .editorconfig and return relevant settings."""
    config_path = os.path.join(project_path, '.editorconfig')
    settings: Dict[str, Any] = {}
    if not os.path.isfile(config_path):
        return settings
    try:
        with open(config_path, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return settings

    current_section = '*'
    sections: Dict[str, Dict[str, str]] = {'*': {}}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            current_section = m.group(1).strip()
            sections[current_section] = sections.get(current_section, {})
            continue
        m = re.match(r'^(\w+)\s*=\s*(.+)$', line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            sections.setdefault(current_section, {})[key] = val

    star = sections.get('*', {})
    if 'indent_style' in star:
        settings['indent_style'] = star['indent_style']
    if 'indent_size' in star:
        try:
            settings['indent_size'] = int(star['indent_size'])
        except ValueError:
            settings['indent_size'] = None
    if 'max_line_length' in star:
        try:
            settings['max_line_length'] = int(star['max_line_length'])
        except ValueError:
            pass
    if 'end_of_line' in star:
        settings['end_of_line'] = star['end_of_line']
    if 'charset' in star:
        settings['charset'] = star['charset']
    if 'trim_trailing_whitespace' in star:
        settings['trim_trailing_whitespace'] = star['trim_trailing_whitespace'].lower() == 'true'
    if 'insert_final_newline' in star:
        settings['insert_final_newline'] = star['insert_final_newline'].lower() == 'true'

    return settings


def parse_codevista_config(project_path: str) -> Dict[str, Any]:
    """Parse .codevista.json or .codevista.yaml for project settings."""
    config: Dict[str, Any] = {}
    for fname in ('.codevista.json', '.codevista.yaml', '.codevista.yml'):
        fpath = os.path.join(project_path, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, 'r', errors='ignore') as f:
                content = f.read()
            if fname.endswith('.json'):
                import json
                config = json.loads(content)
            else:
                config = _parse_yaml_simple(content)
            break
        except (OSError, ValueError, KeyError):
            continue

    result = dict(DEFAULT_CONFIG)
    for key in ('max_line_length', 'max_line_length_warn', 'max_function_length',
                'max_function_args', 'max_nesting_depth', 'max_depth',
                'complexity_threshold', 'cognitive_complexity_threshold'):
        if key in config and isinstance(config[key], (int, float)):
            result[key] = config[key]
    if isinstance(config.get('include_hidden'), bool):
        result['include_hidden'] = config['include_hidden']
    if isinstance(config.get('include_vendored'), bool):
        result['include_vendored'] = config['include_vendored']
    if isinstance(config.get('binary_extensions'), list):
        result['binary_extensions'].update(config['binary_extensions'])
    if isinstance(config.get('vendored_dirs'), list):
        result['vendored_dirs'].update(config['vendored_dirs'])

    return result


def _parse_yaml_simple(content: str) -> Dict[str, Any]:
    """Minimal YAML parser for flat key-value configs."""
    result: Dict[str, Any] = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.lower() in ('true', 'yes', 'on'):
                result[key] = True
            elif val.lower() in ('false', 'no', 'off'):
                result[key] = False
            elif val.startswith('[') and val.endswith(']'):
                result[key] = [s.strip().strip('"\'') for s in val[1:-1].split(',') if s.strip()]
            else:
                try:
                    result[key] = int(val)
                except ValueError:
                    try:
                        result[key] = float(val)
                    except ValueError:
                        result[key] = val.strip('"\'')
    return result


def _parse_ignore_file(filepath: str) -> Set[str]:
    """Parse a gitignore-style file."""
    patterns: Set[str] = set()
    try:
        with open(filepath, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('!'):
                    patterns.discard(line[1:])
                else:
                    patterns.add(line)
    except OSError:
        pass
    return patterns


def should_ignore(filepath: str, project_path: str,
                  ignore_patterns: Optional[Set[str]] = None) -> bool:
    """Check if a file/directory should be ignored."""
    rel = os.path.relpath(filepath, project_path)
    parts = rel.replace('\\', '/').split('/')
    cfg = DEFAULT_CONFIG
    if ignore_patterns is None:
        ignore_patterns = load_config(project_path)

    for part in parts:
        if part in ignore_patterns:
            return True
        if not cfg['include_vendored'] and part in cfg['vendored_dirs']:
            return True
        if not cfg['include_hidden'] and part.startswith('.'):
            return True

    _, ext = os.path.splitext(filepath)
    if ext.lower() in cfg['binary_extensions']:
        return True

    for pattern in ignore_patterns:
        if _match_gitignore_pattern(pattern, rel):
            return True

    return False


def _match_gitignore_pattern(pattern: str, path: str) -> bool:
    """Simple gitignore-style pattern matching."""
    pattern = pattern.strip().rstrip('/')
    if not pattern or pattern.startswith('#'):
        return False
    if pattern.startswith('**/'):
        pattern = pattern[3:]
    if pattern.startswith('*/'):
        pattern = pattern[2:]
    if pattern.endswith('/**'):
        pattern = pattern[:-3]
    if pattern.endswith('/*'):
        pattern = pattern[:-2]

    fnmatch_re = _glob_to_regex(pattern)
    parts = path.replace('\\', '/').split('/')
    for i, part in enumerate(parts):
        if re.fullmatch(fnmatch_re, part, re.IGNORECASE):
            return True
    if re.fullmatch(fnmatch_re, path, re.IGNORECASE):
        return True
    return False


def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern to a regex string."""
    result = ''
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '*':
            if i + 1 < len(pattern) and pattern[i + 1] == '*':
                result += '.*'
                i += 2
                continue
            result += '[^/]*'
        elif c == '?':
            result += '[^/]'
        elif c == '[':
            j = pattern.index(']', i) if ']' in pattern[i:] else len(pattern)
            bracket = pattern[i:j + 1]
            if bracket.startswith('[!') or bracket.startswith('[^'):
                result += '[^' + bracket[2:]
            else:
                result += '[' + bracket[1:]
            i = j
        elif c in '.+^${}()|\\':
            result += '\\' + c
        else:
            result += c
        i += 1
    return result


def get_effective_config(project_path: str) -> Tuple[Set[str], Dict[str, Any]]:
    """Get both ignore patterns and resolved config for a project."""
    ignore = load_config(project_path)
    config = parse_codevista_config(project_path)
    editorconfig = load_editorconfig(project_path)
    if 'max_line_length' in editorconfig:
        config['max_line_length'] = editorconfig['max_line_length']
    if 'indent_size' in editorconfig:
        config['indent_size'] = editorconfig['indent_size']
    if 'indent_style' in editorconfig:
        config['indent_style'] = editorconfig['indent_style']
    return ignore, config
