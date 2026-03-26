"""Dependency parsing and analysis for 10+ package formats.

Supports: requirements.txt, pyproject.toml, package.json, Cargo.toml,
go.mod, Gemfile, composer.json, pom.xml, build.gradle, pubspec.yaml,
and mixed project detection. Includes outdated checking, license extraction,
circular dependency detection, and compatibility analysis.
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# ── Format-specific parsers ─────────────────────────────────────────────────

def parse_requirements(filepath: str) -> List[Dict]:
    """Parse requirements.txt format with extras, markers, and comments."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        if line.startswith('#'):
            continue
        if '==' in line:
            parts = line.split('==', 1)
            deps.append({'name': parts[0].strip(), 'spec': f"=={parts[1].strip()}", 'operator': '=='})
        elif '>=' in line:
            parts = line.split('>=', 1)
            deps.append({'name': parts[0].strip(), 'spec': f">={parts[1].strip()}", 'operator': '>='})
        elif '~=' in line:
            parts = line.split('~=', 1)
            deps.append({'name': parts[0].strip(), 'spec': f"~={parts[1].strip()}", 'operator': '~='})
        elif '<=' in line:
            parts = line.split('<=', 1)
            deps.append({'name': parts[0].strip(), 'spec': f"<={parts[1].strip()}", 'operator': '<='})
        elif '>' in line and not line.startswith('>'):
            parts = line.split('>', 1)
            deps.append({'name': parts[0].strip(), 'spec': f">{parts[1].strip()}", 'operator': '>'})
        elif '<' in line and not line.startswith('<'):
            parts = line.split('<', 1)
            deps.append({'name': parts[0].strip(), 'spec': f"<{parts[1].strip()}", 'operator': '<'})
        elif '[' in line:
            m = re.match(r'^([a-zA-Z0-9_-]+)\[', line)
            if m:
                deps.append({'name': m.group(1), 'spec': line[m.end()-1:].split(']')[0] + line.split(']')[-1].strip() or '*', 'operator': 'any'})
        else:
            m = re.match(r'^([a-zA-Z0-9_-]+)', line)
            if m:
                deps.append({'name': m.group(1), 'spec': line[m.end():].strip() or '*', 'operator': 'any'})
    return deps


def parse_package_json(filepath: str) -> List[Dict]:
    """Parse package.json with dependencies, devDependencies, peerDependencies."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    deps = []
    for section in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
        for name, ver in data.get(section, {}).items():
            deps.append({
                'name': name, 'spec': ver,
                'operator': _parse_npm_operator(ver),
                'section': section,
            })
    return deps


def _parse_npm_operator(spec: str) -> str:
    """Parse npm version operator."""
    if spec.startswith('^'):
        return '^'
    if spec.startswith('~'):
        return '~'
    if spec.startswith('>'):
        return '>=' if '>=' in spec else '>'
    if spec.startswith('<'):
        return '<=' if '<=' in spec else '<'
    if spec.startswith('='):
        return '='
    if spec == '*' or not spec:
        return '*'
    return 'exact'


def parse_pyproject_toml(filepath: str) -> List[Dict]:
    """Parse pyproject.toml for project.dependencies and tool.poetry.dependencies."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    in_deps = False
    is_poetry = False
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('['):
            if 'project.dependencies' in stripped:
                in_deps = True
                is_poetry = False
            elif 'tool.poetry.dependencies' in stripped:
                in_deps = True
                is_poetry = True
            else:
                in_deps = False
            continue
        if in_deps and stripped and not stripped.startswith('#'):
            if is_poetry:
                m = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', stripped)
            else:
                m = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', stripped)
            if m:
                deps.append({'name': m.group(1), 'spec': m.group(2), 'operator': '='})
    return deps


def parse_cargo_toml(filepath: str) -> List[Dict]:
    """Parse Cargo.toml dependencies."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    in_deps = False
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('['):
            in_deps = stripped == '[dependencies]' or stripped.startswith('[dependencies.')
            continue
        if in_deps and stripped and not stripped.startswith('#'):
            m = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', stripped)
            if m:
                deps.append({'name': m.group(1), 'spec': m.group(2), 'operator': '='})
    return deps


def parse_go_mod(filepath: str) -> List[Dict]:
    """Parse go.mod dependencies."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    in_deps = False
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('require ('):
            in_deps = True
            continue
        if in_deps:
            if stripped == ')':
                break
            parts = stripped.split()
            if len(parts) >= 2:
                deps.append({'name': parts[0], 'spec': parts[1], 'operator': '='})
        elif stripped.startswith('require '):
            parts = stripped.split()
            if len(parts) >= 3:
                deps.append({'name': parts[1], 'spec': parts[2], 'operator': '='})
    return deps


def parse_gemfile(filepath: str) -> List[Dict]:
    """Parse Ruby Gemfile."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            continue
        m = re.match(r'''gem\s+['"]([^'"]+)['"]''', stripped)
        if not m:
            m = re.match(r"gem\s+'([^']+)'", stripped)
        if m:
            deps.append({'name': m.group(1), 'spec': '*', 'operator': '*'})
            continue
        m = re.match(r'''gem\s+['"]([^'"]+)['"]\s*,\s*['"]~>\s*([^'"]+)['"]''', stripped)
        if m:
            deps.append({'name': m.group(1), 'spec': f"~> {m.group(2)}", 'operator': '~>'})
    return deps


def parse_composer_json(filepath: str) -> List[Dict]:
    """Parse PHP composer.json."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    deps = []
    for section in ('require', 'require-dev'):
        for name, ver in data.get(section, {}).items():
            deps.append({'name': name, 'spec': ver, 'operator': _parse_npm_operator(ver), 'section': section})
    return deps


def parse_pubspec_yaml(filepath: str) -> List[Dict]:
    """Parse Dart/Flutter pubspec.yaml."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    in_deps = False
    in_dev = False
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped == 'dependencies:':
            in_deps = True
            in_dev = False
            continue
        if stripped == 'dev_dependencies:':
            in_dev = True
            in_deps = False
            continue
        if stripped and stripped[0].islower() and not stripped.startswith('#'):
            if in_deps or in_dev:
                m = re.match(r'^([a-zA-Z_][\w-]*):\s*(.+)', stripped)
                if m:
                    deps.append({'name': m.group(1), 'spec': m.group(2).strip(), 'operator': '='})
        elif stripped and stripped[0].isupper():
            in_deps = False
            in_dev = False
    return deps


def parse_build_gradle(filepath: str) -> List[Dict]:
    """Parse Gradle build files (simplified)."""
    deps = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return deps

    for m in re.finditer(
        r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation|testCompileOnly)\s*\(?['\"]([^'\"]+)['\"]",
        content
    ):
        deps.append({'name': m.group(1), 'spec': '*', 'operator': '*'})
    return deps


def parse_pom_xml(filepath: str) -> List[Dict]:
    """Parse Maven pom.xml (simplified)."""
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except OSError:
        return []

    deps = []
    for m in re.finditer(r'<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>\s*<version>([^<]*)</version>', content):
        deps.append({
            'name': f"{m.group(1)}:{m.group(2)}",
            'spec': m.group(3) or '*',
            'operator': '=',
        })
    return deps


# ── Discovery ───────────────────────────────────────────────────────────────

def find_dependencies(project_path: str) -> Tuple[List[Dict], Optional[str]]:
    """Find and parse all dependency files in a project.

    Returns (deps_list, package_manager_name).
    """
    deps = []
    pkg_manager = None

    # Python
    for fname in ('requirements.txt', 'requirements-dev.txt', 'requirements/prod.txt',
                  'requirements/base.txt'):
        fpath = os.path.join(project_path, fname)
        if os.path.isfile(fpath):
            pkg_manager = 'pip'
            deps.extend(parse_requirements(fpath))

    pyproject = os.path.join(project_path, 'pyproject.toml')
    if os.path.isfile(pyproject):
        pkg_manager = pkg_manager or 'pip'
        deps.extend(parse_pyproject_toml(pyproject))

    pipfile = os.path.join(project_path, 'Pipfile')
    if os.path.isfile(pipfile):
        pkg_manager = 'pipenv'

    # JavaScript/TypeScript
    pkg_json = os.path.join(project_path, 'package.json')
    if os.path.isfile(pkg_json):
        pkg_manager = 'npm'
        deps.extend(parse_package_json(pkg_json))

    # Rust
    cargo = os.path.join(project_path, 'Cargo.toml')
    if os.path.isfile(cargo):
        pkg_manager = 'cargo'
        deps.extend(parse_cargo_toml(cargo))

    # Go
    gomod = os.path.join(project_path, 'go.mod')
    if os.path.isfile(gomod):
        pkg_manager = 'go'
        deps.extend(parse_go_mod(gomod))

    # Ruby
    gemfile = os.path.join(project_path, 'Gemfile')
    if os.path.isfile(gemfile):
        pkg_manager = 'bundler'
        deps.extend(parse_gemfile(gemfile))

    # PHP
    composer = os.path.join(project_path, 'composer.json')
    if os.path.isfile(composer):
        pkg_manager = 'composer'
        deps.extend(parse_composer_json(composer))

    # Dart/Flutter
    pubspec = os.path.join(project_path, 'pubspec.yaml')
    if os.path.isfile(pubspec):
        pkg_manager = 'pub'
        deps.extend(parse_pubspec_yaml(pubspec))

    # Java/Gradle
    for gradle in ('build.gradle', 'build.gradle.kts'):
        gpath = os.path.join(project_path, gradle)
        if os.path.isfile(gpath):
            pkg_manager = 'gradle'
            deps.extend(parse_build_gradle(gpath))
            break

    # Maven
    pom = os.path.join(project_path, 'pom.xml')
    if os.path.isfile(pom):
        pkg_manager = 'maven'
        deps.extend(parse_pom_xml(pom))

    return deps, pkg_manager


# ── Analysis ────────────────────────────────────────────────────────────────

def detect_circular_imports(import_graph: Dict[str, set]) -> List[List[str]]:
    """Detect circular dependencies using DFS cycle detection."""
    visited = set()
    path = []
    path_set = set()
    cycles = []

    def dfs(node: str):
        if node in path_set:
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for dep in import_graph.get(node, set()):
            if len(cycles) < 50:
                dfs(dep)
        path.pop()
        path_set.discard(node)

    for node in list(import_graph.keys())[:1000]:
        if len(cycles) >= 50:
            break
        dfs(node)

    unique_cycles = []
    seen = set()
    for cycle in cycles:
        key = tuple(sorted(set(cycle)))
        if key not in seen:
            seen.add(key)
            unique_cycles.append(cycle)
    return unique_cycles[:20]


def detect_unused_imports(project_path: str, source_files: List[str],
                          import_graph: Dict[str, set]) -> List[Dict]:
    """Detect imports that are never referenced by other modules."""
    all_imported = set()
    all_used_as_module = set()
    for module, targets in import_graph.items():
        all_imported.update(targets)
        all_used_as_module.add(module)

    unused = []
    for imp in all_imported:
        if imp not in all_used_as_module:
            unused.append({'name': imp, 'type': 'unused_import', 'confidence': 'low'})
    return unused[:50]


def check_outdated_deps(deps: List[Dict], pkg_manager: str = 'pip') -> List[Dict]:
    """Check for outdated dependencies using free public APIs.

    Returns list of {name, current, latest} dicts.
    Only checks a limited number to avoid rate limiting.
    """
    if not deps:
        return []

    results = []
    checked = 0
    max_checks = 10

    for dep in deps[:max_checks * 3]:
        if checked >= max_checks:
            break
        name = dep['name']
        current = dep.get('spec', '*')

        if pkg_manager in ('pip', 'pipenv', 'poetry'):
            result = _check_pypi(name, current)
        elif pkg_manager in ('npm', 'yarn', 'pnpm'):
            result = _check_npm(name, current)
        else:
            continue

        if result:
            results.append(result)
            checked += 1

    return results


def _check_pypi(name: str, current: str) -> Optional[Dict]:
    """Check PyPI for latest version."""
    try:
        url = f'https://pypi.org/pypi/{name}/json'
        req = Request(url, headers={'User-Agent': 'CodeVista/1.0'})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        latest = data['info']['version']
        return {'name': name, 'current': current, 'latest': latest}
    except (URLError, HTTPError, OSError, KeyError, json.JSONDecodeError):
        return None


def _check_npm(name: str, current: str) -> Optional[Dict]:
    """Check npm registry for latest version."""
    try:
        url = f'https://registry.npmjs.org/{name}'
        req = Request(url, headers={'User-Agent': 'CodeVista/1.0'})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        latest = data.get('dist-tags', {}).get('latest', 'unknown')
        return {'name': name, 'current': current, 'latest': latest}
    except (URLError, HTTPError, OSError, KeyError, json.JSONDecodeError):
        return None


def extract_licenses(deps: List[Dict], pkg_manager: str = 'pip') -> List[Dict]:
    """Extract license information for dependencies."""
    results = []
    checked = 0
    for dep in deps[:15]:
        if checked >= 10:
            break
        name = dep['name']
        license_info = _get_license(name, pkg_manager)
        if license_info:
            results.append({'name': name, **license_info})
            checked += 1
    return results


def _get_license(name: str, pkg_manager: str) -> Optional[Dict]:
    """Get license for a package from its registry."""
    try:
        if pkg_manager in ('pip', 'pipenv', 'poetry'):
            url = f'https://pypi.org/pypi/{name}/json'
            req = Request(url, headers={'User-Agent': 'CodeVista/1.0'})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            info = data.get('info', {})
            return {
                'license': info.get('license', 'Unknown'),
                'license_url': info.get('license_files', ''),
                'source': 'PyPI',
            }
        elif pkg_manager in ('npm', 'yarn', 'pnpm'):
            url = f'https://registry.npmjs.org/{name}'
            req = Request(url, headers={'User-Agent': 'CodeVista/1.0'})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latest = data.get('dist-tags', {}).get('latest', '')
            version_data = data.get('versions', {}).get(latest, {})
            return {
                'license': version_data.get('license', 'Unknown') or 'Unknown',
                'license_url': '',
                'source': 'npm',
            }
    except (URLError, HTTPError, OSError, KeyError, json.JSONDecodeError):
        return None


def build_dependency_tree(deps: List[Dict]) -> Dict:
    """Build a nested dependency tree structure."""
    tree = {'name': 'root', 'children': {}}
    for dep in deps:
        name = dep['name']
        parts = name.split('/')
        current = tree['children']
        for part in parts[:-1]:
            if part not in current:
                current[part] = {'name': part, 'children': {}}
            current = current[part]['children']
        current[parts[-1]] = {
            'name': name, 'version': dep.get('spec', '*'),
            'children': {},
        }
    return tree


def analyze_dependency_health(deps: List[Dict], pkg_manager: str) -> Dict:
    """Analyze overall dependency health."""
    total = len(deps)
    sections = Counter(d.get('section', 'main') for d in deps)

    pinned = sum(1 for d in deps if d.get('operator') in ('==', '=', 'exact'))
    ranged = sum(1 for d in deps if d.get('operator') in ('>=', '~=', '>', '<', '<='))
    wildcard = sum(1 for d in deps if d.get('operator') in ('*', 'any'))

    pin_rate = pinned / max(total, 1) * 100

    if pin_rate >= 90:
        pin_score = 95
    elif pin_rate >= 70:
        pin_score = 80
    elif pin_rate >= 50:
        pin_score = 60
    else:
        pin_score = 40

    if wildcard > total * 0.3:
        pin_score = min(pin_score, 50)

    return {
        'total': total,
        'pinned': pinned,
        'ranged': ranged,
        'wildcard': wildcard,
        'pin_rate': round(pin_rate, 1),
        'sections': dict(sections),
        'pin_score': pin_score,
    }
