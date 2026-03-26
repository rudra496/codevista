"""Architecture Pattern Detector — identifies architectural patterns and structure.

Detects MVC, MVVM, MVP, Layered, Repository, Service, DI, Observer,
Singleton, Factory, and Strategy patterns from project structure and code.
Generates architecture diagrams and compares actual vs intended architecture.
"""

import ast
import os
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any, Set

from .languages import detect_language, PROGRAMMING
from .utils import read_file_safe, extract_imports, detect_functions


# ── Pattern Definitions ────────────────────────────────────────────────────

ARCHITECTURE_PATTERNS = {
    'MVC': {
        'indicators': ['models', 'views', 'controllers'],
        'min_match': 2,
        'description': 'Model-View-Controller: separates data (Model), UI (View), and logic (Controller).',
    },
    'MVVM': {
        'indicators': ['viewmodels', 'view_models', 'views', 'models'],
        'min_match': 3,
        'description': 'Model-View-ViewModel: adds ViewModel layer between View and Model for data binding.',
    },
    'MVP': {
        'indicators': ['presenters', 'views', 'models'],
        'min_match': 2,
        'description': 'Model-View-Presenter: Presenter handles UI logic, View is passive.',
    },
    'Layered': {
        'indicators': ['presentation', 'business', 'data', 'domain', 'infrastructure',
                       'api', 'core', 'entities', 'services'],
        'min_match': 3,
        'description': 'Layered Architecture: organizes code into horizontal layers with strict dependencies.',
    },
    'Clean Architecture': {
        'indicators': ['entities', 'usecases', 'use_cases', 'controllers', 'adapters',
                       'frameworks', 'interface_adapters'],
        'min_match': 3,
        'description': 'Clean Architecture: dependency rule with inner layers independent of outer layers.',
    },
    'Hexagonal': {
        'indicators': ['ports', 'adapters', 'domain', 'application', 'infrastructure'],
        'min_match': 2,
        'description': 'Hexagonal (Ports & Adapters): domain at center, ports define interfaces, adapters implement them.',
    },
    'Repository': {
        'indicators': ['repositories', 'repository'],
        'min_match': 1,
        'description': 'Repository Pattern: mediates between domain and data mapping layers.',
    },
    'Service Layer': {
        'indicators': ['services', 'service'],
        'min_match': 1,
        'description': 'Service Layer: defines application boundary with operations coordinating domain objects.',
    },
    'CQRS': {
        'indicators': ['commands', 'queries', 'command_handlers', 'query_handlers',
                       'command', 'query'],
        'min_match': 2,
        'description': 'CQRS: separates command (write) and query (read) operations.',
    },
    'Event-Driven': {
        'indicators': ['events', 'event_handlers', 'handlers', 'subscribers',
                       'publishers', 'listeners', 'event_bus'],
        'min_match': 2,
        'description': 'Event-Driven Architecture: components communicate through events.',
    },
    'Microservices': {
        'indicators': ['gateway', 'service', 'api', 'proto', 'grpc',
                       'message_queue', 'broker', 'registry'],
        'min_match': 3,
        'description': 'Microservices: independent services communicating via APIs or messages.',
    },
    'Monolith': {
        'indicators': [],
        'min_match': 0,
        'description': 'Monolithic Architecture: single deployable unit containing all functionality.',
    },
}


# ── Main Analysis Entry Point ──────────────────────────────────────────────

def detect_architecture(project_path: str,
                        files_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Detect architectural patterns and generate architecture analysis.

    Args:
        project_path: Absolute path to the project root.
        files_data: Optional pre-loaded file analysis data.

    Returns:
        Dict with 'patterns', 'structure', 'diagram', 'comparison', 'layers'.
    """
    project_path = os.path.abspath(project_path)

    if files_data is None:
        file_contents = _load_project_files(project_path)
        files_data = _build_files_data(file_contents)
    else:
        file_contents = _load_project_files(project_path, files_data)

    # Detect patterns from directory structure
    dir_names = _collect_directory_names(project_path)
    detected_patterns = _detect_patterns_from_structure(dir_names, files_data)

    # Detect code-level patterns (Singleton, Factory, Strategy, Observer, DI)
    code_patterns = _detect_code_patterns(file_contents, files_data)

    # Build layer analysis
    layers = _analyze_layers(project_path, files_data, file_contents)

    # Generate architecture diagram
    diagram = _generate_architecture_diagram(detected_patterns, layers, files_data)

    # Module dependency analysis
    dependency_graph = _analyze_module_dependencies(files_data, file_contents)

    # Architecture metrics
    metrics = _calculate_architecture_metrics(project_path, files_data, layers, dependency_graph)

    # Architecture quality assessment
    quality = _assess_architecture_quality(metrics, layers, dependency_graph)

    # Combine all patterns
    all_patterns = {p['name']: p for p in detected_patterns}
    for cp in code_patterns:
        name = cp['name']
        if name in all_patterns:
            all_patterns[name]['evidence'].extend(cp.get('evidence', []))
            all_patterns[name]['confidence'] = _merge_confidence(
                all_patterns[name]['confidence'], cp['confidence']
            )
        else:
            all_patterns[name] = cp

    # Add Monolith if no other pattern matches strongly
    strong_patterns = [p for p in all_patterns.values()
                       if p.get('confidence', '') in ('high', 'very-high')]
    if not strong_patterns:
        all_patterns['Monolith'] = {
            'name': 'Monolith',
            'confidence': 'medium',
            'evidence': ['No strong architectural pattern detected'],
            'description': ARCHITECTURE_PATTERNS['Monolith']['description'],
        }

    return {
        'patterns': list(all_patterns.values()),
        'primary_pattern': _determine_primary_pattern(all_patterns),
        'structure': _build_structure_summary(files_data, layers),
        'layers': layers,
        'diagram': diagram,
        'dependency_graph': dependency_graph,
        'metrics': metrics,
        'quality': quality,
        'directory_names': sorted(dir_names),
    }


# ── File Loading ───────────────────────────────────────────────────────────

def _load_project_files(project_path: str,
                        files_data: Optional[List[Dict]] = None) -> Dict[str, str]:
    """Load file contents for the project."""
    contents: Dict[str, str] = {}
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
            if content and content.strip():
                contents[rel] = content
    return contents


def _build_files_data(file_contents: Dict[str, str]) -> List[Dict]:
    """Build minimal files_data from contents dict."""
    return [{'path': rel, 'language': detect_language(rel)} for rel in file_contents]


# ── Directory Structure Analysis ────────────────────────────────────────────

def _collect_directory_names(project_path: str) -> Set[str]:
    """Collect all directory names in the project."""
    dir_names: Set[str] = set()
    for root, dirs, _ in os.walk(project_path):
        for d in dirs:
            if not d.startswith('.') and d not in ('node_modules', '__pycache__',
                                                     'vendor', 'build', 'dist',
                                                     '.venv', 'venv', 'target'):
                dir_names.add(d.lower())
    return dir_names


def _detect_patterns_from_structure(dir_names: Set[str],
                                     files_data: List[Dict]) -> List[Dict]:
    """Detect architecture patterns from directory structure."""
    detected = []

    for pattern_name, pattern_def in ARCHITECTURE_PATTERNS.items():
        if pattern_name == 'Monolith':
            continue
        indicators = [ind.lower() for ind in pattern_def['indicators']]
        matches = dir_names & set(indicators)
        min_match = pattern_def['min_match']

        if len(matches) >= min_match:
            confidence = _calculate_confidence(len(matches), len(indicators))
            detected.append({
                'name': pattern_name,
                'confidence': confidence,
                'evidence': sorted(matches),
                'description': pattern_def['description'],
            })

    return detected


def _calculate_confidence(matched: int, total: int) -> str:
    """Calculate confidence level from match ratio."""
    ratio = matched / max(total, 1)
    if ratio >= 0.8:
        return 'very-high'
    elif ratio >= 0.6:
        return 'high'
    elif ratio >= 0.4:
        return 'medium'
    elif ratio >= 0.2:
        return 'low'
    return 'very-low'


def _merge_confidence(c1: str, c2: str) -> str:
    """Merge two confidence levels, returning the higher one."""
    levels = ['very-low', 'low', 'medium', 'high', 'very-high']
    i1 = levels.index(c1) if c1 in levels else 0
    i2 = levels.index(c2) if c2 in levels else 0
    return levels[max(i1, i2)]


# ── Code-Level Pattern Detection ───────────────────────────────────────────

def _detect_code_patterns(file_contents: Dict[str, str],
                           files_data: List[Dict]) -> List[Dict]:
    """Detect design patterns from code analysis."""
    patterns = []

    patterns.extend(_detect_singleton_pattern(file_contents))
    patterns.extend(_detect_factory_pattern(file_contents))
    patterns.extend(_detect_strategy_pattern(file_contents))
    patterns.extend(_detect_observer_pattern(file_contents))
    patterns.extend(_detect_dependency_injection(file_contents))
    patterns.extend(_detect_decorator_pattern(file_contents))

    return patterns


def _detect_singleton_pattern(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Singleton pattern usage."""
    evidence: List[str] = []
    files_with_singleton = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        if lang in ('Python', 'Cython'):
            # Classic singleton patterns
            if re.search(r'__new__\s*\([^)]*cls[^)]*\)', content):
                if re.search(r'_instance\s*=\s*None', content) or re.search(r'_instances\s*=\s*\{\}', content):
                    evidence.append(f'{filepath.split("/")[-1]}: __new__ singleton')
                    files_with_singleton.append(filepath)

            # Module-level singleton (single instance variable)
            if re.search(r'_[a-z_]+_instance\s*=\s*None', content):
                if re.search(r'def\s+get_instance', content):
                    evidence.append(f'{filepath.split("/")[-1]}: get_instance() singleton')
                    files_with_singleton.append(filepath)

            # Borg pattern
            if re.search(r'__shared_state\s*=\s*\{\}', content) or re.search(r'_shared\b', content):
                if re.search(r'__dict__\s*=', content):
                    evidence.append(f'{filepath.split("/")[-1]}: Borg/Monostate pattern')
                    files_with_singleton.append(filepath)

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'private\s+static\s+\w+\s+instance', content):
                if re.search(r'getInstance\s*\(', content):
                    evidence.append(f'{filepath.split("/")[-1]}: getInstance() singleton')
                    files_with_singleton.append(filepath)

            if re.search(r'@Singleton|@Singleton\b', content):
                evidence.append(f'{filepath.split("/")[-1]}: @Singleton annotation')
                files_with_singleton.append(filepath)

        elif lang in ('JavaScript', 'TypeScript'):
            if re.search(r'getInstance\s*\(', content):
                if re.search(r'(?:static|let)\s+instance', content):
                    evidence.append(f'{filepath.split("/")[-1]}: getInstance() singleton')
                    files_with_singleton.append(filepath)

        elif lang in ('Go',):
            if re.search(r'sync\.Once', content):
                if re.search(r'var\s+\w+\s+\*\w+', content):
                    evidence.append(f'{filepath.split("/")[-1]}: sync.Once singleton')
                    files_with_singleton.append(filepath)

    if evidence:
        return [{
            'name': 'Singleton',
            'confidence': 'high' if len(evidence) >= 2 else 'medium',
            'evidence': evidence[:5],
            'files': files_with_singleton,
            'description': 'Singleton Pattern: ensures a class has only one instance.',
        }]
    return []


def _detect_factory_pattern(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Factory pattern usage."""
    evidence: List[str] = []
    files_with_factory = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        fname = filepath.split('/')[-1].lower()

        # File name patterns
        if 'factory' in fname:
            evidence.append(f'{filepath.split("/")[-1]}: factory in filename')
            files_with_factory.append(filepath)

        # Code patterns
        if lang in ('Python', 'Cython'):
            if re.search(r'classmethod\s+def\s+create', content):
                evidence.append(f'{filepath.split("/")[-1]}: @classmethod create factory')
                files_with_factory.append(filepath)
            if re.search(r'def\s+(?:create|build|make|from_\w+)\s*\(', content):
                if re.search(r'return\s+\w+\s*\(', content):
                    evidence.append(f'{filepath.split("/")[-1]}: factory method')
                    files_with_factory.append(filepath)

        elif lang in ('JavaScript', 'TypeScript'):
            if re.search(r'(?:create|build|make|factory)\s*\([^)]*\)\s*\{', content):
                if re.search(r'new\s+\w+', content):
                    evidence.append(f'{filepath.split("/")[-1]}: JS factory function')
                    files_with_factory.append(filepath)

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'(?:public|static)\s+\w+\s+(?:create|build|make|factory)', content):
                evidence.append(f'{filepath.split("/")[-1]}: factory method')
                files_with_factory.append(filepath)
            if re.search(r'(?:AbstractFactory|Factory|BuilderFactory)\b', content):
                evidence.append(f'{filepath.split("/")[-1]}: factory interface/class')
                files_with_factory.append(filepath)

    if evidence:
        return [{
            'name': 'Factory',
            'confidence': 'high' if len(evidence) >= 3 else 'medium',
            'evidence': evidence[:5],
            'files': files_with_factory,
            'description': 'Factory Pattern: creates objects without specifying exact class.',
        }]
    return []


def _detect_strategy_pattern(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Strategy pattern usage."""
    evidence: List[str] = []
    files_with_strategy = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        # Interface/base class with multiple implementations
        if lang in ('Python', 'Cython'):
            # Abstract base with multiple concrete implementations
            abstract_matches = re.findall(r'class\s+(\w+)\s*\((\w+)\)', content)
            for child, parent in abstract_matches:
                if parent in ('ABC', 'ABCMeta', 'Strategy', 'Protocol'):
                    evidence.append(f'{filepath.split("/")[-1]}: {child} extends {parent}')
                    files_with_strategy.append(filepath)
                    break

            # Context taking a strategy
            if re.search(r'(?:strategy|handler|processor|algorithm)\s*[=:]', content):
                if re.search(r'def\s+(?:set_|execute|run|process)', content):
                    evidence.append(f'{filepath.split("/")[-1]}: strategy context')
                    files_with_strategy.append(filepath)

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'(?:interface\s+\w*Strategy|abstract\s+class\s+\w*Strategy)', content):
                evidence.append(f'{filepath.split("/")[-1]}: strategy interface')
                files_with_strategy.append(filepath)
            if re.search(r'(?:@FunctionalInterface|@Strategy)', content):
                evidence.append(f'{filepath.split("/")[-1]}: strategy annotation')
                files_with_strategy.append(filepath)

    if evidence:
        return [{
            'name': 'Strategy',
            'confidence': 'medium',
            'evidence': evidence[:5],
            'files': files_with_strategy,
            'description': 'Strategy Pattern: defines a family of algorithms, encapsulates each one.',
        }]
    return []


def _detect_observer_pattern(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Observer/Pub-Sub pattern usage."""
    evidence: List[str] = []
    files_with_observer = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        fname = filepath.split('/')[-1].lower()

        # Directory/file name patterns
        if any(kw in fname for kw in ('event', 'observer', 'subscriber', 'listener',
                                        'publisher', 'emitter', 'handler')):
            evidence.append(f'{filepath.split("/")[-1]}: observer-related filename')
            files_with_observer.append(filepath)
            continue

        # Code patterns
        if lang in ('Python', 'Cython'):
            if re.search(r'(?:subscribe|register|attach|add_listener|on\()', content):
                if re.search(r'(?:notify|emit|dispatch|publish|trigger|fire)', content):
                    evidence.append(f'{filepath.split("/")[-1]}: observer pattern')
                    files_with_observer.append(filepath)

            if re.search(r'(?:@property|Observable|Signal|Event)', content):
                evidence.append(f'{filepath.split("/")[-1]}: observable pattern')
                files_with_observer.append(filepath)

        elif lang in ('JavaScript', 'TypeScript'):
            if re.search(r'(?:addEventListener|\.on\(|\.emit\(|EventEmitter)', content):
                evidence.append(f'{filepath.split("/")[-1]}: event system')
                files_with_observer.append(filepath)

            if re.search(r'(?:Rx\.|Observable|Subject|subscribe)', content):
                evidence.append(f'{filepath.split("/")[-1]}: reactive/observer')
                files_with_observer.append(filepath)

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'(?:@Subscribe|@Observer|@EventListener|@Listener)', content):
                evidence.append(f'{filepath.split("/")[-1]}: observer annotation')
                files_with_observer.append(filepath)

            if re.search(r'(?:Observable|Observer|Listener|EventBus)\b', content):
                evidence.append(f'{filepath.split("/")[-1]}: observer class/interface')
                files_with_observer.append(filepath)

    if evidence:
        return [{
            'name': 'Observer',
            'confidence': 'high' if len(evidence) >= 3 else 'medium',
            'evidence': evidence[:5],
            'files': files_with_observer,
            'description': 'Observer Pattern: one-to-many dependency, changes notify dependents.',
        }]
    return []


def _detect_dependency_injection(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Dependency Injection patterns."""
    evidence: List[str] = []
    files_with_di = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        if lang in ('Python', 'Cython'):
            # Constructor injection
            if re.search(r'def\s+__init__\s*\([^)]*(?:repository|service|client|handler|provider)', content):
                evidence.append(f'{filepath.split("/")[-1]}: constructor injection')
                files_with_di.append(filepath)

            # DI framework markers
            if re.search(r'(?:@inject|@provide|Inject|Provides|dependency_injector|injector)', content):
                evidence.append(f'{filepath.split("/")[-1]}: DI framework')
                files_with_di.append(filepath)

            # Container/registry pattern
            if re.search(r'(?:container|registry|provider)\s*[=:]', content):
                if re.search(r'(?:register|bind|provide|wire)', content):
                    evidence.append(f'{filepath.split("/")[-1]}: DI container')
                    files_with_di.append(filepath)

        elif lang in ('JavaScript', 'TypeScript'):
            if re.search(r'(?:@Inject|@Injectable|@Component|@Service)\b', content):
                evidence.append(f'{filepath.split("/")[-1]}: DI decorator')
                files_with_di.append(filepath)

            if re.search(r'(?:createContainer|inject|provideIn|useFactory)', content):
                evidence.append(f'{filepath.split("/")[-1]}: DI framework')
                files_with_di.append(filepath)

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'(?:@Inject|@Autowired|@Component|@Service|@Repository|@Bean)\b', content):
                evidence.append(f'{filepath.split("/")[-1]}: DI annotation')
                files_with_di.append(filepath)

            if re.search(r'(?:Inject|@Inject|ApplicationContext|BeanFactory)', content):
                evidence.append(f'{filepath.split("/")[-1]}: DI framework')
                files_with_di.append(filepath)

    if evidence:
        return [{
            'name': 'Dependency Injection',
            'confidence': 'high' if len(evidence) >= 3 else 'medium',
            'evidence': evidence[:5],
            'files': files_with_di,
            'description': 'Dependency Injection: decouples components by injecting dependencies.',
        }]
    return []


def _detect_decorator_pattern(file_contents: Dict[str, str]) -> List[Dict]:
    """Detect Decorator pattern usage."""
    evidence: List[str] = []

    for filepath, content in file_contents.items():
        lang = detect_language(filepath)
        if lang not in PROGRAMMING:
            continue

        if lang in ('Python', 'Cython'):
            decorator_count = len(re.findall(r'@\w+', content))
            if decorator_count >= 5:
                evidence.append(f'{filepath.split("/")[-1]}: {decorator_count} decorators used')

        elif lang in ('JavaScript', 'TypeScript'):
            if re.search(r'(?:@decorator|higher-order function|HOC|compose\()', content):
                evidence.append(f'{filepath.split("/")[-1]}: decorator/HOC pattern')

        elif lang in ('Java', 'Kotlin', 'C#', 'Scala'):
            if re.search(r'@Decorator\b|implements\s+\w+Decorator', content):
                evidence.append(f'{filepath.split("/")[-1]}: decorator pattern')

    if len(evidence) >= 2:
        return [{
            'name': 'Decorator',
            'confidence': 'medium',
            'evidence': evidence[:5],
            'description': 'Decorator Pattern: attaches additional responsibilities dynamically.',
        }]
    return []


# ── Layer Analysis ─────────────────────────────────────────────────────────

def _analyze_layers(project_path: str, files_data: List[Dict],
                     file_contents: Dict[str, str]) -> Dict[str, Any]:
    """Analyze the project's layer structure."""
    layers: Dict[str, Dict] = {}

    # Map files to layers based on directory structure
    layer_mapping = {
        'presentation': {'dirs': {'views', 'controllers', 'presenters', 'ui', 'pages',
                                    'components', 'screens', 'templates', 'handlers', 'routes'},
                          'files': set()},
        'business': {'dirs': {'services', 'service', 'usecases', 'use_cases', 'logic',
                                'domain', 'core', 'business', 'workflows'},
                      'files': set()},
        'data': {'dirs': {'models', 'entities', 'repositories', 'repository',
                           'data', 'dal', 'mappers', 'schemas'},
                 'files': set()},
        'infrastructure': {'dirs': {'config', 'utils', 'helpers', 'common', 'shared',
                                     'infrastructure', 'adapters', 'clients', 'lib'},
                            'files': set()},
        'api': {'dirs': {'api', 'routes', 'endpoints', 'rest', 'graphql',
                          'controllers', 'middleware'},
                'files': set()},
    }

    for fd in files_data:
        rel = fd.get('path', '')
        parts = rel.replace('\\', '/').split('/')
        assigned = False

        for layer_name, layer_def in layer_mapping.items():
            for part in parts:
                if part.lower() in layer_def['dirs']:
                    layer_def['files'].add(rel)
                    assigned = True
                    break
            if assigned:
                break

    # Build layer results
    for layer_name, layer_def in layer_mapping.items():
        if layer_def['files']:
            file_list = list(layer_def['files'])
            total_loc = sum(
                len(file_contents.get(f, '').split('\n'))
                for f in file_list
            )
            langs = Counter()
            for f in file_list:
                lang = detect_language(f)
                if lang:
                    langs[lang] += 1

            layers[layer_name] = {
                'file_count': len(file_list),
                'files': sorted(file_list)[:20],
                'total_loc': total_loc,
                'languages': dict(langs.most_common()),
                'directories': sorted(layer_def['dirs'] & {p.lower() for rel in file_list for p in rel.split('/')}),
            }

    return layers


# ── Module Dependency Analysis ─────────────────────────────────────────────

def _analyze_module_dependencies(files_data: List[Dict],
                                   file_contents: Dict[str, str]) -> Dict[str, Any]:
    """Analyze dependencies between modules."""
    import_graph: Dict[str, Set[str]] = defaultdict(set)
    module_graph: Dict[str, Set[str]] = defaultdict(set)

    for fd in files_data:
        rel = fd.get('path', '')
        content = file_contents.get(rel, '')
        if not content:
            continue

        parts = rel.replace('\\', '/').split('/')
        module = parts[0] if len(parts) > 1 else '_root'

        lang = detect_language(rel)
        imports = extract_imports(content, lang)

        for imp in imports:
            imp_parts = imp.replace('.', '/').split('/')
            target_module = imp_parts[0].lower()

            if target_module != module and target_module not in ('os', 'sys', 're', 'json',
                                                                    'math', 'time', 'typing',
                                                                    'collections', 'itertools',
                                                                    'functools', 'pathlib',
                                                                    'abc', 'io', 'hashlib',
                                                                    'logging', 'argparse',
                                                                    'subprocess', 'threading'):
                module_graph[module].add(target_module)

    # Find strongly coupled modules
    coupling: List[Dict] = []
    seen_pairs = set()
    for src, targets in module_graph.items():
        for tgt in targets:
            pair = tuple(sorted([src, tgt]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                coupling.append({
                    'modules': list(pair),
                    'connections': 1,
                })

    # Sort by module importance (most depended on)
    dependency_counts: Counter = Counter()
    for targets in module_graph.values():
        for t in targets:
            dependency_counts[t] += 1

    return {
        'modules': dict(module_graph),
        'coupling': sorted(coupling, key=lambda x: x['modules'][0])[:30],
        'most_depended_on': dependency_counts.most_common(10),
        'total_modules': len(module_graph),
    }


# ── Architecture Metrics ───────────────────────────────────────────────────

def _calculate_architecture_metrics(project_path: str, files_data: List[Dict],
                                     layers: Dict[str, Any],
                                     dep_graph: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate architecture-level metrics."""
    total_files = len(files_data)
    module_count = dep_graph.get('total_modules', 0)

    # Layer distribution
    layer_files = sum(l['file_count'] for l in layers.values())
    unlayered = total_files - layer_files

    # Average files per module
    avg_files_per_module = total_files / max(module_count, 1)

    # Coupling metrics
    total_couplings = len(dep_graph.get('coupling', []))
    coupling_density = total_couplings / max(module_count * (module_count - 1) / 2, 1)

    # Depth and breadth of directory tree
    max_depth = 0
    for fd in files_data:
        depth = fd.get('path', '').replace('\\', '/').count('/')
        max_depth = max(max_depth, depth)

    top_modules = set()
    for fd in files_data:
        parts = fd.get('path', '').replace('\\', '/').split('/')
        if len(parts) > 1:
            top_modules.add(parts[0])

    return {
        'total_files': total_files,
        'module_count': module_count,
        'layer_count': len(layers),
        'layered_files': layer_files,
        'unlayered_files': unlayered,
        'layered_pct': round(layer_files / max(total_files, 1) * 100, 1),
        'avg_files_per_module': round(avg_files_per_module, 1),
        'max_depth': max_depth,
        'breadth': len(top_modules),
        'coupling_count': total_couplings,
        'coupling_density': round(coupling_density, 3),
        'most_depended_on': dep_graph.get('most_depended_on', [])[:5],
    }


# ── Architecture Quality Assessment ─────────────────────────────────────────

def _assess_architecture_quality(metrics: Dict[str, Any],
                                   layers: Dict[str, Any],
                                   dep_graph: Dict[str, Any]) -> Dict[str, Any]:
    """Assess overall architecture quality."""
    scores: Dict[str, int] = {}

    # Layer organization score
    layered_pct = metrics.get('layered_pct', 0)
    if layered_pct >= 80:
        scores['organization'] = 90
    elif layered_pct >= 60:
        scores['organization'] = 70
    elif layered_pct >= 40:
        scores['organization'] = 50
    else:
        scores['organization'] = 30

    # Coupling score (lower is better)
    coupling_density = metrics.get('coupling_density', 0)
    if coupling_density < 0.1:
        scores['coupling'] = 90
    elif coupling_density < 0.3:
        scores['coupling'] = 70
    elif coupling_density < 0.5:
        scores['coupling'] = 50
    else:
        scores['coupling'] = 30

    # Modularity score
    avg_files = metrics.get('avg_files_per_module', 0)
    if 5 <= avg_files <= 20:
        scores['modularity'] = 85
    elif 2 <= avg_files <= 50:
        scores['modularity'] = 65
    else:
        scores['modularity'] = 40

    # Balance score (files distributed evenly across layers)
    if layers:
        file_counts = [l['file_count'] for l in layers.values()]
        if file_counts:
            avg_lc = sum(file_counts) / len(file_counts)
            max_lc = max(file_counts)
            balance = avg_lc / max(max_lc, 1)
            scores['balance'] = int(balance * 100)
        else:
            scores['balance'] = 50
    else:
        scores['balance'] = 20

    # Overall
    scores['overall'] = int(
        scores['organization'] * 0.3 +
        scores['coupling'] * 0.25 +
        scores['modularity'] * 0.25 +
        scores['balance'] * 0.2
    )

    return scores


# ── Architecture Diagram Generation ────────────────────────────────────────

def _generate_architecture_diagram(patterns: List[Dict], layers: Dict[str, Any],
                                    files_data: List[Dict]) -> str:
    """Generate a text-based architecture diagram."""
    diagram_lines = ['┌─────────────────────────────────────────┐']
    diagram_lines.append('│         Architecture Overview          │')
    diagram_lines.append('└─────────────────────────────────────────┘')
    diagram_lines.append('')

    # Detected patterns
    if patterns:
        diagram_lines.append('Patterns Detected:')
        for p in sorted(patterns, key=lambda x: _confidence_score(x.get('confidence', '')),
                        reverse=True):
            bar = _confidence_bar(p.get('confidence', ''))
            diagram_lines.append(f'  [{bar}] {p["name"]} ({p["confidence"]})')
        diagram_lines.append('')

    # Layer structure
    if layers:
        diagram_lines.append('Layer Structure:')
        max_files = max(l['file_count'] for l in layers.values())
        for layer_name in ('api', 'presentation', 'business', 'data', 'infrastructure'):
            if layer_name not in layers:
                continue
            layer = layers[layer_name]
            bar_len = int(layer['file_count'] / max(max_files, 1) * 20)
            bar = '█' * bar_len
            diagram_lines.append(f'  {layer_name.upper():16s} │{bar}│ {layer["file_count"]} files')
        diagram_lines.append('')

    # Top modules
    top_modules = Counter()
    for fd in files_data:
        parts = fd.get('path', '').replace('\\', '/').split('/')
        if len(parts) > 1:
            top_modules[parts[0]] += 1

    if top_modules:
        diagram_lines.append('Top Modules:')
        for name, count in top_modules.most_common(10):
            bar_len = min(int(count / max(top_modules.values()) * 15), 15)
            bar = '▓' * bar_len
            diagram_lines.append(f'  {name:<20s} {bar} {count}')
        diagram_lines.append('')

    return '\n'.join(diagram_lines)


def _confidence_score(confidence: str) -> int:
    levels = {'very-low': 1, 'low': 2, 'medium': 3, 'high': 4, 'very-high': 5}
    return levels.get(confidence, 0)


def _confidence_bar(confidence: str) -> str:
    score = _confidence_score(confidence)
    filled = score * 2
    return '█' * filled + '░' * (10 - filled)


def _determine_primary_pattern(patterns: Dict[str, Dict]) -> str:
    """Determine the primary architecture pattern."""
    if not patterns:
        return 'Unknown'
    best = max(patterns.values(), key=lambda p: _confidence_score(p.get('confidence', '')))
    return best['name']


def _build_structure_summary(files_data: List[Dict],
                               layers: Dict[str, Any]) -> Dict[str, Any]:
    """Build a summary of the project structure."""
    total_loc = 0
    lang_dist: Counter = Counter()

    for fd in files_data:
        lang = fd.get('language', 'Unknown')
        if lang:
            lang_dist[lang] += 1

    return {
        'total_files': len(files_data),
        'top_languages': dict(lang_dist.most_common(10)),
        'layers_identified': list(layers.keys()),
    }


# ── Compare Architecture ───────────────────────────────────────────────────

def compare_architecture(arch1: Dict, arch2: Dict) -> Dict[str, Any]:
    """Compare two architecture analyses."""
    patterns1 = {p['name']: p['confidence'] for p in arch1.get('patterns', [])}
    patterns2 = {p['name']: p['confidence'] for p in arch2.get('patterns', [])}

    all_pattern_names = sorted(set(list(patterns1.keys()) + list(patterns2.keys())))

    shared = []
    only_1 = []
    only_2 = []

    for name in all_pattern_names:
        if name in patterns1 and name in patterns2:
            shared.append(name)
        elif name in patterns1:
            only_1.append(name)
        else:
            only_2.append(name)

    metrics1 = arch1.get('metrics', {})
    metrics2 = arch2.get('metrics', {})

    comparison = {
        'shared_patterns': shared,
        'only_first': only_1,
        'only_second': only_2,
        'pattern_similarity': round(len(shared) / max(len(all_pattern_names), 1) * 100, 1),
        'metrics_comparison': {
            'modules': (metrics1.get('module_count', 0), metrics2.get('module_count', 0)),
            'layers': (metrics1.get('layer_count', 0), metrics2.get('layer_count', 0)),
            'coupling': (metrics1.get('coupling_count', 0), metrics2.get('coupling_count', 0)),
            'max_depth': (metrics1.get('max_depth', 0), metrics2.get('max_depth', 0)),
            'breadth': (metrics1.get('breadth', 0), metrics2.get('breadth', 0)),
        },
    }

    quality1 = arch1.get('quality', {})
    quality2 = arch2.get('quality', {})
    comparison['quality_comparison'] = {
        k: (quality1.get(k, 0), quality2.get(k, 0))
        for k in set(list(quality1.keys()) + list(quality2.keys()))
    }

    return comparison


# ── Terminal Output ─────────────────────────────────────────────────────────

def format_architecture_terminal(arch_data: Dict[str, Any]) -> str:
    """Format architecture analysis for terminal output."""
    lines = [
        '',
        '─' * 55,
        '  🏗️ Architecture Analysis',
        '─' * 55,
        f'  Primary Pattern: {arch_data.get("primary_pattern", "Unknown")}',
        f'  Modules:         {arch_data.get("metrics", {}).get("module_count", 0)}',
        f'  Layers:          {arch_data.get("metrics", {}).get("layer_count", 0)}',
        f'  Coupling:        {arch_data.get("metrics", {}).get("coupling_count", 0)} pairs',
        '',
    ]

    # Patterns
    lines.append('  Detected Patterns:')
    for p in arch_data.get('patterns', []):
        bar = _confidence_bar(p.get('confidence', ''))
        lines.append(f'    [{bar}] {p["name"]}')
    lines.append('')

    # Quality scores
    quality = arch_data.get('quality', {})
    if quality:
        lines.append('  Quality Scores:')
        for cat, score in quality.items():
            bar_len = score // 5
            bar = '█' * bar_len + '░' * (20 - bar_len)
            color = '✅' if score >= 70 else '⚠️' if score >= 50 else '❌'
            lines.append(f'    {color} {cat.replace("_", " ").title():18s} {score:3d}/100 [{bar}]')
        lines.append('')

    # Diagram
    diagram = arch_data.get('diagram', '')
    if diagram:
        for line in diagram.split('\n'):
            lines.append(f'  {line}')

    lines.append('─' * 55)
    return '\n'.join(lines)
