"""Code Smell Detector — identifies 19 categories of code smells.

Goes beyond typical linters by detecting structural, semantic, and
architectural code smells that indicate deeper design problems.
"""

import ast
import os
import re
import hashlib
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any, Set

from .languages import detect_language, get_comment_syntax
from .utils import read_file_safe, detect_functions, cyclomatic_complexity


# ── Configuration ───────────────────────────────────────────────────────────

SMELL_CONFIG = {
    'god_class_method_threshold': 20,
    'god_class_field_threshold': 15,
    'long_param_list_threshold': 4,
    'message_chain_max_dots': 4,
    'magic_number_exclusions': {0, 1, -1, 2, 10, 100, 1000, 0.0, 1.0, 0.5},
    'magic_number_threshold': 3,
    'copy_paste_min_lines': 6,
    'copy_paste_similarity_threshold': 0.8,
    'dead_file_call_threshold': 0,
    'max_boolean_params': 1,
    'max_isinstance_chain': 3,
    'comment_what_pattern': re.compile(
        r'^\s*#\s+(?:increment|decrement|set|get|check|validate|parse|format|convert|'
        r'initialize|return|assign|update|delete|remove|add|create|build|'
        r'handle|process|compute|calculate|loop|iterate)',
        re.IGNORECASE
    ),
}

SMELL_SEVERITY = {
    'god_class': 'high',
    'long_parameter_list': 'medium',
    'feature_envy': 'medium',
    'divergent_change': 'medium',
    'shotgun_surgery': 'high',
    'parallel_inheritance': 'medium',
    'speculative_generality': 'low',
    'temporary_field': 'medium',
    'message_chain': 'medium',
    'middle_man': 'low',
    'comment_what_not_why': 'low',
    'dead_code': 'medium',
    'magic_numbers': 'medium',
    'copy_paste_code': 'high',
    'missing_error_handling': 'medium',
    'inconsistent_naming': 'low',
    'boolean_parameters': 'low',
    'isinstance_chain': 'medium',
}


# ── Main Analysis Entry Point ──────────────────────────────────────────────

def detect_code_smells(project_path: str, files_data: Optional[List[Dict]] = None,
                       file_contents: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run full code smell detection on a project.

    Args:
        project_path: Absolute path to the project root.
        files_data: Optional pre-loaded file analysis data from analyzer.
        file_contents: Optional pre-loaded file contents {rel_path: content}.

    Returns:
        Dict with 'smells', 'summary', 'per_file', 'statistics'.
    """
    project_path = os.path.abspath(project_path)
    all_smells: List[Dict] = []
    per_file: Dict[str, List[Dict]] = defaultdict(list)
    per_type: Counter = Counter()
    per_severity: Counter = Counter()

    # Build file contents if not provided
    if file_contents is None:
        file_contents = _load_project_files(project_path, files_data)

    for rel_path, content in file_contents.items():
        lang = detect_language(os.path.join(project_path, rel_path))
        if not content or not content.strip():
            continue

        file_smells = _analyze_file_smells(content, rel_path, lang)
        all_smells.extend(file_smells)
        per_file[rel_path] = file_smells
        for smell in file_smells:
            per_type[smell['type']] += 1
            per_severity[smell['severity']] += 1

    # Cross-file analysis
    cross_file_smells = _cross_file_analysis(file_contents)
    for smell in cross_file_smells:
        all_smells.append(smell)
        per_type[smell['type']] += 1
        per_severity[smell['severity']] += 1
        for fp in smell.get('files', [smell.get('file', '')]):
            per_file[fp].append(smell)

    # Calculate risk score
    risk_score = _calculate_smell_risk_score(per_type, per_severity)

    statistics = _build_statistics(per_type, per_severity, per_file, file_contents)

    return {
        'smells': all_smells,
        'summary': {
            'total_smells': len(all_smells),
            'unique_types': len(per_type),
            'affected_files': len(per_file),
            'total_files': len(file_contents),
            'risk_score': risk_score,
        },
        'per_type': dict(per_type.most_common()),
        'per_severity': dict(per_severity.most_common()),
        'per_file': dict(per_file),
        'statistics': statistics,
        'top_smelly_files': sorted(
            per_file.items(), key=lambda x: len(x[1]), reverse=True
        )[:20],
    }


# ── File-Level Analysis ────────────────────────────────────────────────────

def _load_project_files(project_path: str,
                        files_data: Optional[List[Dict]] = None) -> Dict[str, str]:
    """Load file contents for the project."""
    contents = {}
    if files_data:
        for fd in files_data:
            rel = fd.get('path', '')
            if not rel:
                continue
            fpath = os.path.join(project_path, rel)
            content = read_file_safe(fpath)
            if content:
                contents[rel] = content
        return contents

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ('node_modules', '__pycache__', '.git', 'vendor', 'build', 'dist',
                    '.venv', 'venv', 'target', '.tox', '.next', '.nuxt')]
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, project_path)
            content = read_file_safe(fpath)
            if content and len(content.strip()) > 0:
                contents[rel] = content
    return contents


def _analyze_file_smells(content: str, filepath: str,
                         language: Optional[str]) -> List[Dict]:
    """Run all single-file smell detectors."""
    smells: List[Dict] = []

    if language in ('Python', 'Cython'):
        smells.extend(_detect_python_smells(content, filepath))
    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte'):
        smells.extend(_detect_js_smells(content, filepath))
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        smells.extend(_detect_java_smells(content, filepath))
    elif language in ('Go',):
        smells.extend(_detect_go_smells(content, filepath))
    elif language in ('Ruby',):
        smells.extend(_detect_ruby_smells(content, filepath))

    # Language-agnostic detectors
    smells.extend(_detect_magic_numbers(content, filepath, language))
    smells.extend(_detect_long_param_lists(content, filepath, language))
    smells.extend(_detect_message_chains(content, filepath))
    smells.extend(_detect_comment_smells(content, filepath, language))
    smells.extend(_detect_dead_code(content, filepath, language))
    smells.extend(_detect_boolean_parameters(content, filepath, language))
    smells.extend(_detect_inconsistent_naming(content, filepath, language))
    smells.extend(_detect_missing_error_handling(content, filepath, language))
    smells.extend(_detect_copy_paste_within_file(content, filepath))

    return smells


# ── Python-Specific Smells ─────────────────────────────────────────────────

def _detect_python_smells(content: str, filepath: str) -> List[Dict]:
    """Detect Python-specific code smells using AST analysis."""
    smells: List[Dict] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return smells

    # God class detection
    smells.extend(_detect_god_classes(tree, filepath))

    # Feature envy detection
    smells.extend(_detect_feature_envy_python(tree, filepath))

    # Middle man detection
    smells.extend(_detect_middle_man_python(tree, filepath))

    # Speculative generality
    smells.extend(_detect_speculative_generality_python(tree, filepath))

    # Temporary field detection
    smells.extend(_detect_temporary_fields_python(tree, filepath, content))

    # Shotgun surgery / divergent change
    smells.extend(_detect_divergent_change_python(tree, filepath))

    # isinstance chains
    smells.extend(_detect_isinstance_chains_python(tree, filepath))

    return smells


def _detect_god_classes(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect God classes with too many methods or responsibilities."""
    smells = []
    cfg = SMELL_CONFIG

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        dunder_methods = [m for m in methods if m.name.startswith('__') and m.name.endswith('__')]
        regular_methods = [m for m in methods if not (m.name.startswith('__') and m.name.endswith('__'))]
        fields = set()

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        fields.add(target.id)

        # Count responsibilities by analyzing what modules/packages methods interact with
        external_modules = set()
        for method in regular_methods:
            for child in ast.walk(method):
                if isinstance(child, ast.Attribute):
                    if isinstance(child.value, ast.Name):
                        external_modules.add(child.value.id)
                elif isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        external_modules.add(child.func.id)

        responsibilities = len(external_modules)

        is_god = False
        reasons = []

        if len(regular_methods) > cfg['god_class_method_threshold']:
            is_god = True
            reasons.append(f'{len(regular_methods)} methods (>{cfg["god_class_method_threshold"]})')

        if len(fields) > cfg['god_class_field_threshold']:
            is_god = True
            reasons.append(f'{len(fields)} fields (>{cfg["god_class_field_threshold"]})')

        if responsibilities > 10:
            is_god = True
            reasons.append(f'{responsibilities} external dependencies')

        if is_god:
            smells.append({
                'type': 'god_class',
                'severity': SMELL_SEVERITY['god_class'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Class "{node.name}" is a God class',
                'details': ', '.join(reasons),
                'remediation': (
                    f'Extract responsibilities from "{node.name}" into separate classes using '
                    'Single Responsibility Principle. Consider splitting into smaller, '
                    'focused components.'
                ),
            })

    return smells


def _detect_feature_envy_python(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect methods that use another class's data more than their own.

    A method has feature envy when it accesses more attributes/calls on
    external objects than on self.
    """
    smells = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith('__'):
                continue

            self_accesses = 0
            external_accesses = 0
            self_attrs = set()
            external_classes: Counter = Counter()

            for child in ast.walk(item):
                # Count self.attribute accesses
                if isinstance(child, ast.Attribute):
                    if isinstance(child.value, ast.Name) and child.value.id == 'self':
                        self_accesses += 1
                        self_attrs.add(child.attr)
                    elif isinstance(child.value, ast.Name):
                        external_accesses += 1
                        external_classes[child.value.id] += 1
                # Count calls on external objects
                elif isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if isinstance(child.func.value, ast.Name) and child.func.value.id != 'self':
                            external_accesses += 1
                            external_classes[child.func.value.id] += 1

            total_accesses = self_accesses + external_accesses
            if total_accesses > 5 and external_accesses > self_accesses * 1.5:
                top_external = external_classes.most_common(1)[0]
                smells.append({
                    'type': 'feature_envy',
                    'severity': SMELL_SEVERITY['feature_envy'],
                    'file': filepath,
                    'line': item.lineno,
                    'message': f'Method "{item.name}" has feature envy for "{top_external[0]}"',
                    'details': (
                        f'{external_accesses} external accesses vs {self_accesses} self accesses. '
                        f'Consider moving this method to class "{top_external[0]}".'
                    ),
                    'remediation': (
                        f'The method "{item.name}" relies heavily on "{top_external[0]}". '
                        f'Consider moving it to that class or using Move Method refactoring.'
                    ),
                })

    return smells


def _detect_middle_man_python(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect classes that only delegate to other classes.

    A middle man class has most methods that simply call another object's method
    without adding any real logic.
    """
    smells = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and not n.name.startswith('__')]

        if len(methods) < 2:
            continue

        delegating_methods = 0
        total_methods = len(methods)

        for method in methods:
            body_lines = [n for n in ast.walk(method) if isinstance(n, (ast.Expr, ast.Return, ast.Assign))]
            call_count = sum(1 for n in ast.walk(method) if isinstance(n, ast.Call))
            has_logic = False

            for child in ast.walk(method):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    has_logic = True
                    break
                if isinstance(child, (ast.BoolOp, ast.Compare)):
                    has_logic = True
                    break

            if not has_logic and call_count == 1 and len(body_lines) <= 3:
                delegating_methods += 1

        delegation_ratio = delegating_methods / total_methods if total_methods > 0 else 0
        if delegation_ratio > 0.6 and total_methods >= 3:
            smells.append({
                'type': 'middle_man',
                'severity': SMELL_SEVERITY['middle_man'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Class "{node.name}" is mostly a middle man',
                'details': (
                    f'{delegating_methods}/{total_methods} methods are simple delegations. '
                    'Consider removing the middle man and having callers use the delegate directly.'
                ),
                'remediation': (
                    f'Class "{node.name}" primarily delegates to other objects. '
                    'Consider using Inlining or hiding the delegate.'
                ),
            })

    return smells


def _detect_speculative_generality_python(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect unused abstractions: unused parameters, unused abstract methods, empty overrides."""
    smells = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check for abstract methods that may never be overridden
        abstract_methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.body and len(item.body) == 1:
                    stmt = item.body[0]
                    if isinstance(stmt, ast.Raise):
                        if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                            if stmt.value.func.id == 'NotImplementedError':
                                abstract_methods.append(item.name)
                    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                        if isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == 'abstractmethod':
                            abstract_methods.append(item.name)
                    elif isinstance(stmt, (ast.Pass,)):
                        # Check if this is in a class that has no subclasses
                        abstract_methods.append(item.name)

        if len(abstract_methods) >= 3:
            smells.append({
                'type': 'speculative_generality',
                'severity': SMELL_SEVERITY['speculative_generality'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Class "{node.name}" has many abstract/empty methods',
                'details': f'Found {len(abstract_methods)} abstract methods: {", ".join(abstract_methods[:5])}',
                'remediation': 'Remove unused abstractions or implement the methods you actually need.',
            })

    # Check for functions with unused parameters
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        all_args = set()
        for arg in node.args.args:
            all_args.add(arg.arg)
        for arg in node.args.posonlyargs:
            all_args.add(arg.arg)
        for arg in node.args.kwonlyargs:
            all_args.add(arg.arg)

        if node.args.vararg:
            all_args.discard(node.args.vararg.arg)
        if node.args.kwarg:
            all_args.discard(node.args.kwarg.arg)

        # Skip self/cls
        all_args.discard('self')
        all_args.discard('cls')

        # Find used names in the function body
        used_names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                used_names.add(child.id)

        unused_params = all_args - used_names
        # But default None params are common in Python APIs, don't flag those as speculative
        truly_unused = []
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            if arg.arg in unused_params:
                has_default = arg.default is not None
                if not has_default:
                    truly_unused.append(arg.arg)

        if len(truly_unused) >= 2:
            smells.append({
                'type': 'speculative_generality',
                'severity': SMELL_SEVERITY['speculative_generality'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Function "{node.name}" has unused parameters',
                'details': f'Unused parameters: {", ".join(truly_unused[:5])}',
                'remediation': 'Remove unused parameters or use *args/**kwargs if flexibility is needed.',
            })

    return smells


def _detect_temporary_fields_python(tree: ast.AST, filepath: str,
                                   content: str) -> List[Dict]:
    """Detect instance variables that are only set in certain methods.

    Temporary fields indicate that the class is doing too much or has
    poorly defined state management.
    """
    smells = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Collect self.X = Y assignments per method
        field_assignments: Dict[str, Set[str]] = defaultdict(set)
        field_reads: Dict[str, Set[str]] = defaultdict(set)
        method_names: Set[str] = set()

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith('__'):
                method_names.add(item.name)

            for child in ast.walk(item):
                if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                    if child.value.id == 'self':
                        if isinstance(child.ctx, ast.Store):
                            field_assignments[child.attr].add(item.name)
                        elif isinstance(child.ctx, ast.Load):
                            field_reads[child.attr].add(item.name)

        # A temporary field is set in only one method but read elsewhere
        temp_fields = []
        for field, assigners in field_assignments.items():
            if field.startswith('_'):
                continue
            if len(assigners) == 1 and len(field_reads.get(field, set())) > 0:
                setter = next(iter(assigners))
                readers = field_reads[field] - assigners
                if readers:
                    temp_fields.append((field, setter, readers))

        if temp_fields:
            field_names = [f[0] for f in temp_fields[:5]]
            smells.append({
                'type': 'temporary_field',
                'severity': SMELL_SEVERITY['temporary_field'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Class "{node.name}" has temporary fields',
                'details': (
                    f'Fields set only in specific methods: {", ".join(field_names)}. '
                    'Consider extracting these into a separate data class or using parameters.'
                ),
                'remediation': (
                    'Temporary fields make state hard to understand. Consider extracting '
                    'related state into a dedicated class or passing data as method parameters.'
                ),
            })

    return smells


def _detect_divergent_change_python(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect classes that need to be modified for multiple, unrelated reasons.

    Measures change categories by analyzing what kinds of operations methods perform:
    - Data access (get/set attributes, dict/list operations)
    - Business logic (computations, conditionals, external calls)
    - UI/display (string formatting, print, logging)
    - Persistence (file I/O, database calls)
    """
    smells = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and not n.name.startswith('__')]

        if len(methods) < 4:
            continue

        categories: Dict[str, List[str]] = defaultdict(list)

        for method in methods:
            cats = set()
            for child in ast.walk(method):
                if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                    attr = child.attr
                    # Persistence indicators
                    if attr in ('save', 'load', 'write', 'read', 'commit', 'execute',
                                'cursor', 'fetch', 'query', 'insert', 'update', 'delete'):
                        cats.add('persistence')
                    # UI/display indicators
                    elif attr in ('render', 'display', 'format', 'print', 'send', 'emit',
                                  'notify', 'show', 'hide', 'draw', 'paint'):
                        cats.add('display')
                    # Data access indicators
                    elif attr in ('get', 'set', 'append', 'extend', 'pop', 'remove',
                                  'items', 'values', 'keys', 'find', 'search', 'filter'):
                        cats.add('data_access')
                    # External service indicators
                    elif attr in ('request', 'post', 'fetch', 'call', 'invoke', 'dispatch',
                                  'publish', 'subscribe'):
                        cats.add('external_service')

                # Persistence from function names
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id in ('open', 'exec', 'eval', 'subprocess'):
                        cats.add('persistence')
                    elif child.func.id in ('print', 'logging', 'logger'):
                        cats.add('display')
                    elif child.func.id in ('requests', 'urllib'):
                        cats.add('external_service')

            for cat in cats:
                categories[cat].append(method.name)

        # If the class has methods in 3+ different change categories
        if len(categories) >= 3:
            cat_desc = '; '.join(f'{cat}: {len(ms)} methods' for cat, ms in sorted(categories.items()))
            smells.append({
                'type': 'divergent_change',
                'severity': SMELL_SEVERITY['divergent_change'],
                'file': filepath,
                'line': node.lineno,
                'message': f'Class "{node.name}" changes for multiple reasons',
                'details': cat_desc,
                'remediation': (
                    'Split this class by change category. Each class should have one reason to change '
                    '(Single Responsibility Principle).'
                ),
            })

    return smells


def _detect_isinstance_chains_python(tree: ast.AST, filepath: str) -> List[Dict]:
    """Detect chains of isinstance checks that indicate missing polymorphism."""
    smells = []
    cfg = SMELL_CONFIG

    for node in ast.walk(tree):
        if not isinstance(node, (ast.If,)):
            continue

        # Count isinstance calls in the if/elif chain
        isinstance_types = []
        current = node

        while current is not None:
            if isinstance(current, ast.If):
                test = current.test
                if isinstance(test, ast.Call):
                    if isinstance(test.func, ast.Name) and test.func.id == 'isinstance':
                        if len(test.args) == 2 and isinstance(test.args[1], ast.Name):
                            isinstance_types.append(test.args[1].id)
                        elif len(test.args) == 2 and isinstance(test.args[1], (ast.Tuple,)):
                            for elt in test.args[1].elts:
                                if isinstance(elt, ast.Name):
                                    isinstance_types.append(elt.id)
                # Check orelse for elif patterns
                if current.orelse and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    current = current.orelse[0]
                    continue
            break

        if len(isinstance_types) >= cfg['max_isinstance_chain']:
            smells.append({
                'type': 'isinstance_chain',
                'severity': SMELL_SEVERITY['isinstance_chain'],
                'file': filepath,
                'line': node.lineno,
                'message': f'isinstance chain with {len(isinstance_types)} types',
                'details': f'Types checked: {", ".join(isinstance_types[:6])}',
                'remediation': (
                    'Long isinstance chains suggest missing polymorphism. '
                    'Consider using a common base class with a shared method, '
                    'a visitor pattern, or double dispatch.'
                ),
            })

    return smells


# ── JavaScript-Specific Smells ─────────────────────────────────────────────

def _detect_js_smells(content: str, filepath: str) -> List[Dict]:
    """Detect code smells in JavaScript/TypeScript files."""
    smells = []

    # God objects (large object literals or classes with many methods)
    class_matches = re.findall(r'class\s+(\w+)\s*\{', content)
    for class_name in class_matches:
        class_block = _extract_js_class_block(content, class_name)
        if class_block:
            methods = re.findall(r'(?:async\s+)?(?:get\s+|set\s+)?(\w+)\s*\([^)]*\)\s*\{', class_block)
            if len(methods) > SMELL_CONFIG['god_class_method_threshold']:
                smells.append({
                    'type': 'god_class',
                    'severity': SMELL_SEVERITY['god_class'],
                    'file': filepath,
                    'line': content.find(f'class {class_name}') + 1,
                    'message': f'Class "{class_name}" has {len(methods)} methods',
                    'details': f'{len(methods)} methods (>{SMELL_CONFIG["god_class_method_threshold"]})',
                    'remediation': 'Split this class into smaller, focused components.',
                })

    # isinstance / typeof chains
    typeof_chains = re.findall(
        r'(?:typeof\s+\w+\s*===?\s*["\'][^"\']+["\']\s*\|\|?\s*){3,}',
        content
    )
    if typeof_chains:
        line_num = content.find(typeof_chains[0]) + 1
        smells.append({
            'type': 'isinstance_chain',
            'severity': SMELL_SEVERITY['isinstance_chain'],
            'file': filepath,
            'line': line_num,
            'message': f'Long typeof chain detected',
            'details': 'Consider using polymorphism or a type map instead.',
            'remediation': 'Replace typeof chains with polymorphic dispatch or a strategy pattern.',
        })

    return smells


def _extract_js_class_block(content: str, class_name: str) -> Optional[str]:
    """Extract the body of a JS/TS class definition."""
    pattern = rf'class\s+{re.escape(class_name)}[^{{]*\{{'
    m = re.search(pattern, content)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
        i += 1
    return content[start:i - 1]


# ── Java/JVM Smells ────────────────────────────────────────────────────────

def _detect_java_smells(content: str, filepath: str) -> List[Dict]:
    """Detect code smells in Java/Kotlin/C#/Scala files."""
    smells = []

    # God class
    class_pattern = re.findall(r'(?:public|private|protected)?\s*(?:abstract\s+)?(?:class|interface)\s+(\w+)', content)
    for class_name in class_pattern:
        class_start = content.find(class_name)
        if class_start < 0:
            continue
        # Count methods
        nearby = content[class_start:class_start + 5000]
        method_count = len(re.findall(r'(?:public|private|protected)\s+\S+\s+\w+\s*\([^)]*\)\s*\{', nearby))
        if method_count > SMELL_CONFIG['god_class_method_threshold']:
            line_num = content[:class_start].count('\n') + 1
            smells.append({
                'type': 'god_class',
                'severity': SMELL_SEVERITY['god_class'],
                'file': filepath,
                'line': line_num,
                'message': f'Class "{class_name}" has ~{method_count} methods',
                'details': f'~{method_count} methods detected (>{SMELL_CONFIG["god_class_method_threshold"]})',
                'remediation': 'Apply Single Responsibility Principle to split this class.',
            })

    # instanceof chains
    instance_of_chains = re.findall(
        r'(?:\w+\s+instanceof\s+\w+\s*\|\|?\s*){3,}',
        content
    )
    if instance_of_chains:
        line_num = content.find(instance_of_chains[0]) + 1
        smells.append({
            'type': 'isinstance_chain',
            'severity': SMELL_SEVERITY['isinstance_chain'],
            'file': filepath,
            'line': line_num,
            'message': 'Long instanceof chain detected',
            'details': 'Replace with polymorphism or visitor pattern.',
            'remediation': 'Use polymorphism instead of instanceof chains.',
        })

    return smells


# ── Go Smells ──────────────────────────────────────────────────────────────

def _detect_go_smells(content: str, filepath: str) -> List[Dict]:
    """Detect code smells in Go files."""
    smells = []

    # God struct - struct with many methods
    struct_methods: Dict[str, int] = Counter()
    for m in re.finditer(r'func\s+\([^)]+\)\s*\*(\w+)\s*\w+\s*\(', content):
        struct_methods[m.group(1)] += 1

    for struct_name, count in struct_methods.items():
        if count > SMELL_CONFIG['god_class_method_threshold']:
            line_num = content.find(f'type {struct_name}') + 1
            smells.append({
                'type': 'god_class',
                'severity': SMELL_SEVERITY['god_class'],
                'file': filepath,
                'line': max(line_num, 1),
                'message': f'Struct "{struct_name}" has {count} methods',
                'details': f'{count} methods (>{SMELL_CONFIG["god_class_method_threshold"]})',
                'remediation': 'Split the struct and its methods into smaller types.',
            })

    return smells


# ── Ruby Smells ────────────────────────────────────────────────────────────

def _detect_ruby_smells(content: str, filepath: str) -> List[Dict]:
    """Detect code smells in Ruby files."""
    smells = []

    # God class
    class_matches = re.findall(r'class\s+(\w+)', content)
    for class_name in class_matches:
        class_start = content.find(f'class {class_name}')
        class_end = content.find('\nend', class_start) if class_start >= 0 else -1
        if class_start < 0 or class_end < 0:
            class_end = class_start + 5000
        class_body = content[class_start:class_end]
        method_count = len(re.findall(r'\bdef\s+\w+', class_body))
        if method_count > SMELL_CONFIG['god_class_method_threshold']:
            line_num = content[:class_start].count('\n') + 1
            smells.append({
                'type': 'god_class',
                'severity': SMELL_SEVERITY['god_class'],
                'file': filepath,
                'line': line_num,
                'message': f'Class "{class_name}" has {method_count} methods',
                'details': f'{method_count} methods (>{SMELL_CONFIG["god_class_method_threshold"]})',
                'remediation': 'Apply Single Responsibility Principle and split this class.',
            })

    # Boolean parameters
    for m in re.finditer(r'\bdef\s+(\w+)\s*\(([^)]*)\)', content):
        params = m.group(2).split(',')
        bool_params = [p.strip() for p in params if p.strip().rstrip('?').rstrip('=') in
                       ('true', 'false', 'enabled', 'disabled', 'flag', 'verbose', 'debug')]
        if len(bool_params) > SMELL_CONFIG['max_boolean_params']:
            line_num = content[:m.start()].count('\n') + 1
            smells.append({
                'type': 'boolean_parameters',
                'severity': SMELL_SEVERITY['boolean_parameters'],
                'file': filepath,
                'line': line_num,
                'message': f'Method "{m.group(1)}" has {len(bool_params)} boolean parameters',
                'details': f'Boolean params: {", ".join(bool_params[:5])}',
                'remediation': 'Replace boolean parameters with enums or separate methods.',
            })

    return smells


# ── Language-Agnostic Smells ──────────────────────────────────────────────

def _detect_magic_numbers(content: str, filepath: str,
                          language: Optional[str]) -> List[Dict]:
    """Detect magic numbers — numeric literals not assigned to named constants."""
    smells = []
    cfg = SMELL_CONFIG

    lines = content.split('\n')
    exclusions = cfg['magic_number_exclusions']

    # Find constant definitions to exclude
    constant_names = set()
    if language in ('Python', 'Cython'):
        constant_names.update(re.findall(r'^([A-Z_][A-Z_0-9]*)\s*=\s*\d', content, re.MULTILINE))
    elif language in ('JavaScript', 'TypeScript'):
        constant_names.update(re.findall(r'(?:const|let|var)\s+([A-Z_][A-Z_0-9]*)\s*=\s*\d', content))
    elif language in ('Java', 'Kotlin', 'C#', 'Scala'):
        constant_names.update(
            re.findall(r'(?:static\s+)?(?:final\s+)?(?:\w+\s+)([A-Z_][A-Z_0-9]*)\s*=\s*\d', content)
        )
    elif language in ('Go',):
        constant_names.update(re.findall(r'(?:const|var)\s+([A-Z_][A-Z_0-9]*)\s*=\s*\d', content))

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
            continue

        # Find numeric literals
        numbers = re.findall(r'(?<![A-Za-z_]\.)(?<![A-Za-z_])(?<![.\w])(\b\d+\.?\d*\b)(?!\w*[.:=])', stripped)
        for num_str in numbers:
            try:
                num = float(num_str)
            except ValueError:
                continue

            if num in exclusions:
                continue

            # Skip numbers in constant definitions
            if any(c in line for c in constant_names):
                continue

            # Skip numbers in string literals
            in_string = False
            quote_count = 0
            for ch in line[:line.index(num_str)]:
                if ch in ('"', "'", '`'):
                    quote_count += 1
            if quote_count % 2 == 1:
                continue

            smells.append({
                'type': 'magic_numbers',
                'severity': SMELL_SEVERITY['magic_numbers'],
                'file': filepath,
                'line': line_num,
                'message': f'Magic number: {num_str}',
                'details': f'The literal {num_str} should be extracted to a named constant.',
                'remediation': f'Extract {num_str} into a named constant with a descriptive name.',
            })

    # Deduplicate: only report first occurrence of each number per file
    seen_numbers = set()
    deduped = []
    for smell in smells:
        num_key = smell['message'].split(': ')[-1]
        if num_key not in seen_numbers:
            seen_numbers.add(num_key)
            deduped.append(smell)

    return deduped[:20]


def _detect_long_param_lists(content: str, filepath: str,
                              language: Optional[str]) -> List[Dict]:
    """Detect functions with too many parameters, especially with default None."""
    smells = []
    cfg = SMELL_CONFIG

    functions = detect_functions(content, language)
    for func in functions:
        param_count = func.get('param_count', 0)
        if param_count <= cfg['long_param_list_threshold']:
            continue

        params = func.get('params', [])
        none_defaults = [p for p in params if '=None' in p or '= null' in p or '=nil' in p]

        msg = f'Function "{func["name"]}" has {param_count} parameters'
        details = f'{param_count} params (>{cfg["long_param_list_threshold"]})'

        if len(none_defaults) >= 2:
            msg += ' with multiple default None values'
            details += f', {len(none_defaults)} have default None (missing data class?)'

        smells.append({
            'type': 'long_parameter_list',
            'severity': SMELL_SEVERITY['long_parameter_list'],
            'file': filepath,
            'line': func['start_line'],
            'message': msg,
            'details': details,
            'remediation': (
                'Consider using a dataclass, typed dict, or configuration object to group '
                'related parameters. This improves readability and makes it easier to add '
                'optional parameters in the future.'
            ),
        })

    return smells


def _detect_message_chains(content: str, filepath: str) -> List[Dict]:
    """Detect message chains (a.b.c.d.e) that are too long."""
    smells = []
    cfg = SMELL_CONFIG

    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
            continue

        # Count dot chains (excluding things like 0.5, x.y.z in imports, etc.)
        chain_pattern = re.findall(r'(\w+(?:\.\w+){' + str(cfg['message_chain_max_dots']) + r',})', stripped)
        for chain in chain_pattern:
            dot_count = chain.count('.')
            parts = chain.split('.')
            # Filter out known false positives
            if any(p in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') for p in parts):
                continue
            if 'import' in stripped or 'from' in stripped:
                continue

            smells.append({
                'type': 'message_chain',
                'severity': SMELL_SEVERITY['message_chain'],
                'file': filepath,
                'line': line_num,
                'message': f'Message chain with {dot_count} dots',
                'details': f'Chain: {chain}',
                'remediation': (
                    'Long message chains violate the Law of Demeter. Consider extracting '
                    'intermediate results into well-named variables.'
                ),
            })

    return smells[:15]


def _detect_comment_smells(content: str, filepath: str,
                            language: Optional[str]) -> List[Dict]:
    """Detect comments that describe WHAT the code does, not WHY."""
    smells = []
    cfg = SMELL_CONFIG
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue

        comment = None
        for prefix in ('#', '//', '--', '%'):
            if stripped.startswith(prefix + ' '):
                comment = stripped[len(prefix):].strip()
                break
            elif stripped.startswith(prefix) and len(stripped) > len(prefix):
                comment = stripped[len(prefix):].strip()
                break

        if not comment:
            continue

        # Skip known good comment patterns
        if re.match(r'^(TODO|FIXME|HACK|XXX|NOTE|BUG|OPTIMIZE|REVIEW)\b', comment, re.IGNORECASE):
            continue
        if re.match(r'^(Copyright|License|SPDX|MIT|Apache|GPL)', comment, re.IGNORECASE):
            continue
        if re.match(r'^\S+:\s', comment):  # Section headers like "Args:", "Returns:"
            continue
        if len(comment) < 10:
            continue

        # Check for "what" patterns
        if cfg['comment_what_pattern'].match(comment):
            smells.append({
                'type': 'comment_what_not_why',
                'severity': SMELL_SEVERITY['comment_what_not_why'],
                'file': filepath,
                'line': line_num,
                'message': 'Comment describes WHAT, not WHY',
                'details': f'Comment: "{comment[:80]}"',
                'remediation': (
                    'Good comments explain WHY, not WHAT. The code itself should describe WHAT. '
                    'Consider removing this comment or rewriting it to explain the reasoning.'
                ),
            })

    return smells[:10]


def _detect_dead_code(content: str, filepath: str,
                       language: Optional[str]) -> List[Dict]:
    """Detect dead code: variables assigned but never read, unreachable code."""
    smells = []
    lines = content.split('\n')

    # Find assigned variables and check if they're read
    if language in ('Python', 'Cython', 'Ruby', 'Go', 'JavaScript', 'TypeScript'):
        assigned_vars: Dict[str, int] = {}
        read_vars: Set[str] = set()

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or not stripped:
                continue

            # Find assignments
            assign_match = re.match(r'^\s*(\w+)\s*=', stripped)
            if assign_match:
                var_name = assign_match.group(1)
                if var_name not in assigned_vars:
                    assigned_vars[var_name] = line_num

            # Find reads (but not in assignment LHS)
            for m in re.finditer(r'(?<![.\w])(\b[a-zA-Z_]\w*\b)', stripped):
                name = m.group(1)
                read_vars.add(name)

        # Find variables that are assigned but never read
        keywords = {
            'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return', 'import',
            'from', 'as', 'with', 'try', 'except', 'raise', 'yield', 'lambda', 'pass',
            'break', 'continue', 'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False',
            'self', 'cls', 'print', 'range', 'len', 'str', 'int', 'float', 'list', 'dict',
            'set', 'tuple', 'bool', 'type', 'super', 'function', 'var', 'let', 'const',
            'new', 'this', 'null', 'undefined', 'func', 'package', 'return', 'err',
            'fmt', 'string', 'error', 'make', 'append', 'func', 'interface',
        }
        dead_vars = []
        for var, ln in assigned_vars.items():
            if var not in read_vars and var not in keywords and len(var) > 1:
                dead_vars.append((var, ln))

        if dead_vars:
            for var, ln in dead_vars[:5]:
                smells.append({
                    'type': 'dead_code',
                    'severity': SMELL_SEVERITY['dead_code'],
                    'file': filepath,
                    'line': ln,
                    'message': f'Variable "{var}" assigned but never read',
                    'details': 'This variable is assigned a value but never used afterward.',
                    'remediation': f'Remove the unused variable "{var}" or use it in the code.',
                })

    # Find functions that are never called (within the same file)
    if language in ('Python', 'Cython'):
        defined_funcs = set(re.findall(r'^\s*def\s+(\w+)', content, re.MULTILINE))
        called_funcs = set(re.findall(r'\b(\w+)\s*\(', content))
        # Remove self-references and common patterns
        uncalled = defined_funcs - called_funcs - {'__init__', '__repr__', '__str__',
                                                    '__eq__', '__hash__', '__len__',
                                                    '__getitem__', '__setitem__',
                                                    '__iter__', '__next__', '__enter__',
                                                    '__exit__', '__call__', '__del__',
                                                    '__contains__', '__bool__',
                                                    '__getattr__', '__setattr__',
                                                    '__get__', '__set__'}
        for func in sorted(uncalled)[:5]:
            line_num = content.find(f'def {func}')
            if line_num >= 0:
                ln = content[:line_num].count('\n') + 1
                smells.append({
                    'type': 'dead_code',
                    'severity': SMELL_SEVERITY['dead_code'],
                    'file': filepath,
                    'line': ln,
                    'message': f'Function "{func}" may never be called',
                    'details': 'Defined but no calls found in this file.',
                    'remediation': f'Verify if "{func}" is used elsewhere, or remove it.',
                })

    return smells[:10]


def _detect_boolean_parameters(content: str, filepath: str,
                                language: Optional[str]) -> List[Dict]:
    """Detect boolean parameters that indicate a method should be split."""
    smells = []
    cfg = SMELL_CONFIG
    functions = detect_functions(content, language)

    for func in functions:
        params = func.get('params', [])
        bool_params = []

        for p in params:
            p_lower = p.lower().strip()
            is_bool = False

            # Python: flag=True, flag=False, flag: bool
            if language in ('Python', 'Cython'):
                if any(x in p_lower for x in ('=true', '=false', ': bool', ':bool')):
                    is_bool = True
                elif p_lower in ('true', 'false', 'verbose', 'debug', 'quiet',
                                  'dry_run', 'force', 'enabled', 'disabled',
                                  'silent', 'strict', 'allow', 'skip', 'confirm'):
                    is_bool = True
            elif language in ('JavaScript', 'TypeScript'):
                if any(x in p_lower for x in (': boolean', ':boolean', '=true', '=false')):
                    is_bool = True
            elif language in ('Java', 'Kotlin', 'C#'):
                if 'boolean' in p_lower or 'Boolean' in p_lower:
                    is_bool = True
            elif language in ('Go',):
                if p_lower in ('true', 'false', 'verbose', 'debug'):
                    is_bool = True
            elif language in ('Ruby',):
                if p_lower in ('true', 'false', 'verbose', 'debug'):
                    is_bool = True

            if is_bool:
                bool_params.append(p.strip().split('=')[0].split(':')[0].strip())

        if len(bool_params) > cfg['max_boolean_params']:
            smells.append({
                'type': 'boolean_parameters',
                'severity': SMELL_SEVERITY['boolean_parameters'],
                'file': filepath,
                'line': func['start_line'],
                'message': f'Function "{func["name"]}" has {len(bool_params)} boolean parameters',
                'details': f'Boolean params: {", ".join(bool_params[:5])}',
                'remediation': (
                    'Boolean parameters make the call site hard to read. '
                    'Consider splitting the method, using an enum, or using a configuration object.'
                ),
            })

    return smells


def _detect_inconsistent_naming(content: str, filepath: str,
                                  language: Optional[str]) -> List[Dict]:
    """Detect inconsistent naming conventions (mixing camelCase and snake_case)."""
    smells = []

    if language in ('Python', 'Cython'):
        # In Python, functions/variables should be snake_case
        # Classes should be PascalCase
        names = re.findall(r'\bdef\s+(\w+)', content) + re.findall(r'(\w+)\s*=', content)
        camel_case = [n for n in names if re.match(r'^[a-z]+[A-Z]', n) and not n.startswith('__')]
        if len(camel_case) >= 3:
            examples = camel_case[:5]
            smells.append({
                'type': 'inconsistent_naming',
                'severity': SMELL_SEVERITY['inconsistent_naming'],
                'file': filepath,
                'line': 1,
                'message': f'{len(camel_case)} camelCase names in Python file',
                'details': f'Python convention is snake_case. Examples: {", ".join(examples)}',
                'remediation': 'Rename camelCase identifiers to snake_case per PEP 8.',
            })

    elif language in ('JavaScript', 'TypeScript', 'Vue', 'Svelte', 'Java',
                       'Kotlin', 'C#', 'Scala', 'Dart'):
        # In JS/TS/Java, functions/variables should be camelCase
        names = re.findall(r'\b(?:function|const|let|var)\s+(\w+)', content)
        snake_case = [n for n in names if '_' in n and not n.upper() == n
                      and not n.startswith('_')]
        if len(snake_case) >= 3:
            examples = snake_case[:5]
            smells.append({
                'type': 'inconsistent_naming',
                'severity': SMELL_SEVERITY['inconsistent_naming'],
                'file': filepath,
                'line': 1,
                'message': f'{len(snake_case)} snake_case names in camelCase language',
                'details': f'Convention is camelCase. Examples: {", ".join(examples)}',
                'remediation': 'Rename snake_case identifiers to camelCase per language convention.',
            })

    elif language in ('Go',):
        # Go uses MixedCaps for exported, mixedCaps for unexported
        names = re.findall(r'\bfunc\s+(\w+)', content)
        snake_case = [n for n in names if '_' in n and not n.startswith('_')]
        if len(snake_case) >= 3:
            examples = snake_case[:5]
            smells.append({
                'type': 'inconsistent_naming',
                'severity': SMELL_SEVERITY['inconsistent_naming'],
                'file': filepath,
                'line': 1,
                'message': f'{len(snake_case)} snake_case names in Go file',
                'details': f'Go convention is MixedCaps. Examples: {", ".join(examples)}',
                'remediation': 'Rename snake_case identifiers to MixedCaps per Go conventions.',
            })

    return smells


def _detect_missing_error_handling(content: str, filepath: str,
                                     language: Optional[str]) -> List[Dict]:
    """Detect I/O operations without error handling."""
    smells = []

    io_operations = []

    if language in ('Python', 'Cython'):
        # open() without try/except or with statement
        for m in re.finditer(r'(?<!\w)open\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            # Check surrounding context for try or with
            nearby = content[max(0, m.start() - 200):m.start()]
            if 'try' not in nearby and 'with' not in nearby:
                io_operations.append(('file open', line_num))

        # subprocess calls without try
        for m in re.finditer(r'(?:subprocess|os\.system|os\.popen|exec)\s*\.\s*\w+\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            nearby = content[max(0, m.start() - 200):m.start()]
            if 'try' not in nearby:
                io_operations.append(('subprocess call', line_num))

        # requests/network calls without try
        for m in re.finditer(r'(?:requests\.\w+|urllib|httpx|aiohttp)\s*\.\s*\w+\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            nearby = content[max(0, m.start() - 200):m.start()]
            if 'try' not in nearby:
                io_operations.append(('network request', line_num))

    elif language in ('JavaScript', 'TypeScript'):
        # fs operations
        for m in re.finditer(r'(?:fs\.\w+|readFile|writeFile|unlink)\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            nearby = content[max(0, m.start() - 200):m.start()]
            if 'try' not in nearby and 'catch' not in nearby and '.catch' not in nearby:
                io_operations.append(('file I/O', line_num))

        # fetch without catch
        for m in re.finditer(r'fetch\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            nearby_after = content[m.start():m.start() + 500]
            if 'catch' not in nearby_after and '.catch' not in nearby_after:
                io_operations.append(('fetch call', line_num))

    elif language in ('Go',):
        # os.Open without if err check nearby
        for m in re.finditer(r'(?:os\.Open|os\.Create|os\.Remove|ioutil)\.\w+\s*\(', content):
            line_num = content[:m.start()].count('\n') + 1
            nearby = content[m.start():m.start() + 300]
            if 'if err' not in nearby and 'err != nil' not in nearby:
                io_operations.append(('file I/O', line_num))

    for op_type, line_num in io_operations[:10]:
        smells.append({
            'type': 'missing_error_handling',
            'severity': SMELL_SEVERITY['missing_error_handling'],
            'file': filepath,
            'line': line_num,
            'message': f'IO operation without error handling ({op_type})',
            'details': f'A {op_type} operation at line {line_num} lacks try/catch or error check.',
            'remediation': 'Wrap I/O operations in error handling blocks to prevent crashes on failure.',
        })

    return smells


def _detect_copy_paste_within_file(content: str, filepath: str) -> List[Dict]:
    """Detect near-duplicate code blocks within a single file."""
    smells = []
    cfg = SMELL_CONFIG
    lines = content.split('\n')
    min_lines = cfg['copy_paste_min_lines']

    # Normalize lines for comparison
    normalized = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//') or not stripped:
            normalized.append('')
        else:
            normalized.append(re.sub(r'\s+', ' ', stripped).lower())

    # Check blocks of min_lines for similarity
    block_hashes: Dict[str, List[int]] = defaultdict(list)
    for i in range(len(normalized) - min_lines + 1):
        block = '\n'.join(normalized[i:i + min_lines])
        if not block.strip():
            continue
        bh = hashlib.md5(block.encode()).hexdigest()
        block_hashes[bh].append(i + 1)

    reported_pairs = set()
    for bh, occurrences in block_hashes.items():
        if len(occurrences) < 2:
            continue
        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                pair = (min(occurrences[i], occurrences[j]), max(occurrences[i], occurrences[j]))
                if pair not in reported_pairs:
                    reported_pairs.add(pair)
                    smells.append({
                        'type': 'copy_paste_code',
                        'severity': SMELL_SEVERITY['copy_paste_code'],
                        'file': filepath,
                        'line': pair[0],
                        'message': f'Duplicate {min_lines}-line block at lines {pair[0]} and {pair[1]}',
                        'details': f'Identical code blocks found at lines {pair[0]}-{pair[0]+min_lines-1} and {pair[1]}-{pair[1]+min_lines-1}',
                        'remediation': 'Extract the duplicated code into a shared function.',
                    })

    return smells[:5]


# ── Cross-File Analysis ────────────────────────────────────────────────────

def _cross_file_analysis(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect cross-file code smells like copy-paste and parallel inheritance."""
    smells = []

    # Copy-paste detection across files
    smells.extend(_detect_cross_file_copy_paste(file_contents))

    # Parallel inheritance hierarchies
    smells.extend(_detect_parallel_inheritance(file_contents))

    # Shotgun surgery detection
    smells.extend(_detect_shotgun_surgery(file_contents))

    return smells


def _detect_cross_file_copy_paste(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect near-duplicate code blocks across files."""
    smells = []
    cfg = SMELL_CONFIG
    min_lines = cfg['copy_paste_min_lines']

    # Hash all blocks of min_lines across all files
    all_blocks: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

    for filepath, content in file_contents.items():
        lines = content.split('\n')
        normalized = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or not stripped:
                normalized.append('')
            else:
                normalized.append(re.sub(r'\s+', ' ', stripped).lower())

        for i in range(len(normalized) - min_lines + 1):
            block = '\n'.join(normalized[i:i + min_lines])
            if not block.strip():
                continue
            bh = hashlib.md5(block.encode()).hexdigest()
            all_blocks[bh].append((filepath, i + 1))

    reported = set()
    for bh, occurrences in all_blocks.items():
        unique_files = set(fp for fp, _ in occurrences)
        if len(unique_files) < 2:
            continue

        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                fp1, ln1 = occurrences[i]
                fp2, ln2 = occurrences[j]
                if fp1 == fp2:
                    continue
                pair_key = tuple(sorted([fp1, fp2]))
                if pair_key in reported:
                    continue
                reported.add(pair_key)

                smells.append({
                    'type': 'copy_paste_code',
                    'severity': SMELL_SEVERITY['copy_paste_code'],
                    'file': fp1,
                    'line': ln1,
                    'files': [fp1, fp2],
                    'message': f'Duplicate code between {fp1.split("/")[-1]} and {fp2.split("/")[-1]}',
                    'details': f'Lines {ln1}-{ln1+min_lines-1} in {fp1} ≈ lines {ln2}-{ln2+min_lines-1} in {fp2}',
                    'remediation': 'Extract shared logic into a common utility module.',
                })

    return smells[:15]


def _detect_parallel_inheritance(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect parallel inheritance hierarchies.

    When adding a subclass of A requires also adding a subclass of B,
    you have parallel inheritance.
    """
    smells = []

    # Collect inheritance relationships
    inheritance_map: Dict[str, Set[str]] = defaultdict(set)

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang in ('Python', 'Cython'):
            for m in re.finditer(r'class\s+(\w+)\s*\(([^)]*)\)', content):
                parent = m.group(2).strip()
                child = m.group(1)
                if parent and parent != 'object':
                    inheritance_map[parent].add(child)

    # Check for parallel hierarchies
    parents = list(inheritance_map.keys())
    for i in range(len(parents)):
        for j in range(i + 1, len(parents)):
            p1, p2 = parents[i], parents[j]
            children1 = inheritance_map[p1]
            children2 = inheritance_map[p2]
            if len(children1) < 2 or len(children2) < 2:
                continue

            # Check if there's a naming pattern that suggests parallelism
            common_suffixes = set()
            for c1 in children1:
                for c2 in children2:
                    # Check if they share a suffix/prefix pattern
                    if c1.replace(p1, '') == c2.replace(p2, ''):
                        common_suffixes.add(c1.replace(p1, ''))

            if len(common_suffixes) >= 2:
                smells.append({
                    'type': 'parallel_inheritance',
                    'severity': SMELL_SEVERITY['parallel_inheritance'],
                    'file': list(file_contents.keys())[0],
                    'line': 1,
                    'message': f'Parallel hierarchy between {p1} and {p2}',
                    'details': f'Shared patterns: {", ".join(common_suffixes[:5])}',
                    'remediation': 'Consider merging the hierarchies or using composition instead.',
                })
                break

    return smells[:5]


def _detect_shotgun_surgery(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect shotgun surgery: when a single change requires edits to many classes.

    We approximate this by finding methods with similar names across many files,
    suggesting the same logical operation is scattered.
    """
    smells = []

    # Collect method names across files
    method_locations: Dict[str, List[str]] = defaultdict(list)
    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if not lang or lang in ('HTML', 'CSS', 'JSON', 'YAML', 'Markdown', 'XML'):
            continue

        if lang in ('Python', 'Cython'):
            methods = re.findall(r'def\s+(validate|parse|serialize|format|render|handle|process|sanitize|normalize|transform)\w*', content)
        elif lang in ('JavaScript', 'TypeScript'):
            methods = re.findall(r'(?:async\s+)?(?:function|const|let)\s+(validate|parse|serialize|format|render|handle|process|sanitize|normalize|transform)\w*', content)
        else:
            methods = re.findall(r'(?:def|function|fn)\s+(validate|parse|serialize|format|render|handle|process|sanitize|normalize|transform)\w*', content)

        for method in methods:
            method_locations[method].append(filepath)

    # Methods found in many files
    threshold = 4
    for method, files in method_locations.items():
        if len(set(files)) >= threshold:
            unique_files = sorted(set(files))
            smells.append({
                'type': 'shotgun_surgery',
                'severity': SMELL_SEVERITY['shotgun_surgery'],
                'file': unique_files[0],
                'line': 1,
                'files': unique_files,
                'message': f'Method pattern "{method}" scattered across {len(unique_files)} files',
                'details': f'Found in: {", ".join(f.split("/")[-1] for f in unique_files[:5])}',
                'remediation': (
                    f'Centralize "{method}" logic into a shared module. '
                    'Scattered implementations make changes error-prone.'
                ),
            })

    return smells[:5]


# ── Statistics & Risk Scoring ───────────────────────────────────────────────

def _calculate_smell_risk_score(per_type: Counter,
                                 per_severity: Counter) -> int:
    """Calculate an overall risk score from detected smells (0-100)."""
    if not per_type:
        return 0

    weights = {
        'critical': 15, 'high': 10, 'medium': 5, 'low': 2,
    }
    raw = sum(per_severity.get(sev, 0) * weight for sev, weight in weights.items())
    return min(int(raw), 100)


def _build_statistics(per_type: Counter, per_severity: Counter,
                      per_file: Dict[str, List[Dict]],
                      file_contents: Dict[str, str]) -> Dict[str, Any]:
    """Build aggregate statistics about code smells."""
    total_smells = sum(per_type.values())
    total_files = len(file_contents)
    affected_files = len(per_file)
    avg_smells_per_file = total_smells / max(total_files, 1)
    avg_smells_per_affected = total_smells / max(affected_files, 1)

    # Smell density (smells per 1000 lines)
    total_loc = sum(len(content.split('\n')) for content in file_contents.values())
    smell_density = (total_smells / max(total_loc, 1)) * 1000

    # Most common smell type
    most_common = per_type.most_common(1)[0] if per_type else ('none', 0)

    return {
        'total_smells': total_smells,
        'total_files': total_files,
        'affected_files': affected_files,
        'affected_pct': round(affected_files / max(total_files, 1) * 100, 1),
        'avg_smells_per_file': round(avg_smells_per_file, 2),
        'avg_smells_per_affected': round(avg_smells_per_affected, 2),
        'smell_density': round(smell_density, 2),
        'most_common_type': most_common[0],
        'most_common_count': most_common[1],
        'types_detected': len(per_type),
    }


# ── Terminal Output Helpers ─────────────────────────────────────────────────

def format_smells_terminal(smell_data: Dict[str, Any]) -> str:
    """Format smell detection results for terminal output."""
    summary = smell_data['summary']
    lines = [
        '',
        '─' * 55,
        '  👃 Code Smell Detection Results',
        '─' * 55,
        f'  Total smells:     {summary["total_smells"]}',
        f'  Unique types:     {summary["unique_types"]}',
        f'  Affected files:   {summary["affected_files"]}/{summary["total_files"]}',
        f'  Risk score:       {summary["risk_score"]}/100',
        '',
    ]

    # Per-severity breakdown
    sev_icons = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}
    for sev, count in smell_data.get('per_severity', {}).items():
        icon = sev_icons.get(sev, '❓')
        lines.append(f'  {icon} {sev.upper():10s} {count}')
    lines.append('')

    # Per-type breakdown
    for smell_type, count in smell_data.get('per_type', {}).items():
        lines.append(f'  • {smell_type.replace("_", " ").title():30s} {count}')

    # Top smelly files
    if smell_data.get('top_smelly_files'):
        lines.append('')
        lines.append('  📁 Top Smelly Files:')
        for filepath, file_smells in smell_data['top_smelly_files'][:10]:
            fname = filepath.split('/')[-1]
            lines.append(f'    • {fname:<35s} {len(file_smells)} smells')

    lines.append('─' * 55)
    return '\n'.join(lines)


def generate_smell_recommendations(smell_data: Dict[str, Any]) -> List[Dict]:
    """Generate prioritized recommendations from smell data."""
    recs: List[Dict] = []
    per_type = smell_data.get('per_type', {})

    if per_type.get('god_class', 0) > 0:
        recs.append({
            'icon': '🏗️', 'category': 'God Classes', 'priority': 'high',
            'message': f'Found {per_type["god_class"]} God classes. Apply SRP to split them into focused components.',
        })

    if per_type.get('copy_paste_code', 0) > 0:
        recs.append({
            'icon': '♻️', 'category': 'Code Duplication', 'priority': 'high',
            'message': f'Found {per_type["copy_paste_code"]} copy-paste instances. Extract shared logic into utility functions.',
        })

    if per_type.get('dead_code', 0) > 0:
        recs.append({
            'icon': '🧹', 'category': 'Dead Code', 'priority': 'medium',
            'message': f'Found {per_type["dead_code"]} dead code instances. Remove unused variables and functions.',
        })

    if per_type.get('magic_numbers', 0) > 0:
        recs.append({
            'icon': '🔢', 'category': 'Magic Numbers', 'priority': 'low',
            'message': f'Found {per_type["magic_numbers"]} magic numbers. Extract them into named constants.',
        })

    if per_type.get('feature_envy', 0) > 0:
        recs.append({
            'icon': '转移', 'category': 'Feature Envy', 'priority': 'medium',
            'message': f'Found {per_type["feature_envy"]} feature envy cases. Move methods closer to the data they use.',
        })

    if per_type.get('missing_error_handling', 0) > 0:
        recs.append({
            'icon': '⚠️', 'category': 'Error Handling', 'priority': 'high',
            'message': f'Found {per_type["missing_error_handling"]} I/O operations without error handling.',
        })

    if per_type.get('long_parameter_list', 0) > 0:
        recs.append({
            'icon': '📝', 'category': 'Long Parameter Lists', 'priority': 'medium',
            'message': f'Found {per_type["long_parameter_list"]} functions with too many parameters. Use data classes.',
        })

    if per_type.get('shotgun_surgery', 0) > 0:
        recs.append({
            'icon': '🔫', 'category': 'Shotgun Surgery', 'priority': 'high',
            'message': f'Found {per_type["shotgun_surgery"]} patterns suggesting scattered logic. Centralize shared operations.',
        })

    if not recs:
        recs.append({
            'icon': '✨', 'category': 'Code Smells', 'priority': 'low',
            'message': 'No significant code smells detected. Codebase looks clean!',
        })

    return recs
