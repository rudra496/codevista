"""CodeDNA Fingerprinter — creates unique fingerprints for codebases."""

import os
import hashlib
import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional


# Language extensions mapping
LANG_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".java": "Java", ".c": "C", ".cpp": "C++", ".cc": "C++",
    ".cxx": "C++", ".h": "C/C++ Header", ".hpp": "C++ Header", ".cs": "C#",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala", ".r": "R", ".R": "R",
    ".m": "Objective-C", ".mm": "Objective-C++", ".pl": "Perl", ".pm": "Perl",
    ".lua": "Lua", ".vim": "VimScript", ".sh": "Shell", ".bash": "Shell",
    ".zsh": "Shell", ".fish": "Shell", ".ps1": "PowerShell", ".bat": "Batch",
    ".sql": "SQL", ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".sass": "Sass", ".less": "Less", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".xml": "XML", ".md": "Markdown", ".rst": "reStructuredText",
    ".tex": "LaTeX", ".dockerfile": "Dockerfile", ".makefile": "Makefile",
    ".cmake": "CMake", ".gradle": "Gradle", ".proto": "Protocol Buffers",
    ".graphql": "GraphQL", ".vue": "Vue", ".svelte": "Svelte", ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".hrl": "Erlang",
    ".clj": "Clojure", ".cljs": "ClojureScript", ".hs": "Haskell", ".lhs": "Haskell",
    ".ml": "OCaml", ".mli": "OCaml", ".fs": "F#", ".fsi": "F#",
    ".zig": "Zig", "nim": "Nim", ".v": "V", ".jl": "Julia", ".tf": "HCL",
    ".coffee": "CoffeeScript", ".groovy": "Groovy",
}

# Comment patterns per language family
COMMENT_PATTERNS = {
    "hash_line": [r'^\s*#'],                   # Python, Ruby, Shell, etc.
    "slash_line": [r'^\s*//'],                 # JS, TS, Java, C++, Go, etc.
    "block_c": [(r'/\*', r'\*/')],             # C, Java, JS, etc.
    "block_hash": [(r'=begin', r'=end')],       # Ruby
    "doc_py": [(r'"""', r'"""'), (r"'''", r"'''")],  # Python docstrings
    "doc_js": [(r'/\*\*', r'\*/')],            # JSDoc
    "html_comment": [(r'<!--', r'-->')],
    "sql_comment": [r'^\s*--'],
    "vim_comment": [r'^\s*"'],
    "latex_comment": [r'^\s*%'],
    "batch_comment": [r'^\s*REM\b', r'^\s*::'],
}

SKIP_DIRS = {
    'node_modules', '__pycache__', '.git', '.svn', 'vendor', 'build', 'dist',
    '.venv', 'venv', 'target', '.tox', '.next', '.nuxt', '.eggs', '*.egg-info',
    'coverage', '.mypy_cache', '.pytest_cache', '.idea', '.vscode',
}


class CodeDNA:
    """Creates unique DNA fingerprints for codebases."""

    def __init__(self, project_path: str = "."):
        self.project_path = os.path.abspath(project_path)
        self.fingerprint = {}

    def _should_skip(self, dirpath: str) -> bool:
        """Check if a directory should be skipped."""
        dirname = os.path.basename(dirpath)
        return dirname in SKIP_DIRS or dirname.startswith('.')

    def _scan_files(self) -> List[Dict]:
        """Walk the project tree and collect file info."""
        files = []
        for root, dirs, filenames in os.walk(self.project_path):
            # Prune skipped directories in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            for fname in filenames:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.project_path)
                try:
                    stat = os.stat(full_path)
                    files.append({
                        "path": rel_path,
                        "full_path": full_path,
                        "size": stat.st_size,
                        "extension": os.path.splitext(fname)[1].lower(),
                        "name": fname,
                    })
                except OSError:
                    continue
        return files

    def _read_file_lines(self, filepath: str) -> List[str]:
        """Read file lines, handling encoding errors."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.readlines()
        except (OSError, IOError):
            return []

    def _get_language(self, extension: str) -> str:
        """Map file extension to language name."""
        return LANG_MAP.get(extension, "Other")

    def _detect_comment_style(self, filepath: str, lines: List[str]) -> str:
        """Detect which comment style a file uses."""
        for line in lines[:50]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                return "hash_line"
            if stripped.startswith('//'):
                return "slash_line"
            if stripped.startswith('<!--'):
                return "html_comment"
            if stripped.startswith('--') and not stripped.startswith('---'):
                return "sql_comment"
            if stripped.startswith('REM ') or stripped.startswith('::'):
                return "batch_comment"
            if stripped.startswith('%'):
                return "latex_comment"
            if stripped.startswith('"'):
                return "vim_comment"
        return "unknown"

    def generate_fingerprint(self) -> Dict:
        """Generate complete DNA fingerprint for the project."""
        files = self._scan_files()

        self.fingerprint = {
            "project": os.path.basename(self.project_path),
            "hash_patterns": self._hash_patterns(files),
            "language_distribution": self._language_distribution(files),
            "complexity_distribution": self._complexity_distribution(files),
            "dependency_topology": self._dependency_topology(files),
            "naming_conventions": self._naming_conventions(files),
            "comment_density": self._comment_density(files),
            "function_size_distribution": self._function_size_distribution(files),
            "file_size_distribution": self._file_size_distribution(files),
            "total_files": len(files),
            "generated_at": __import__('datetime').datetime.now().isoformat(),
        }

        return self.fingerprint

    def _hash_patterns(self, files: List[Dict] = None) -> str:
        """Hash-based profile of code patterns."""
        if files is None:
            files = self._scan_files()

        # Collect code hashes for structural patterns
        pattern_hashes = []

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt', '.scala', '.ex', '.hs'}

        for f in files:
            if f["extension"] not in code_extensions:
                continue
            lines = self._read_file_lines(f["full_path"])
            # Hash structural patterns: function definitions, class definitions
            for line in lines:
                stripped = line.strip()
                if re.match(r'^(def |function |func |fn |class |struct |enum |interface |trait |impl |pub fn |pub struct )', stripped):
                    # Normalize and hash
                    normalized = re.sub(r'\s+', ' ', stripped).lower()
                    h = hashlib.md5(normalized.encode()).hexdigest()[:8]
                    pattern_hashes.append(h)

        # Create a meta-hash from all pattern hashes
        pattern_hashes.sort()
        combined = "|".join(pattern_hashes)
        meta_hash = hashlib.sha256(combined.encode()).hexdigest()[:16] if combined else "empty"
        return meta_hash

    def _language_distribution(self, files: List[Dict] = None) -> Dict:
        """Language distribution signature."""
        if files is None:
            files = self._scan_files()

        lang_lines = defaultdict(int)
        lang_files = defaultdict(int)

        code_extensions = {ext for ext, _ in LANG_MAP.items()}

        for f in files:
            lang = self._get_language(f["extension"])
            if f["extension"] not in code_extensions:
                continue
            lang_files[lang] += 1
            # Count lines
            try:
                with open(f["full_path"], 'r', encoding='utf-8', errors='ignore') as fh:
                    line_count = sum(1 for _ in fh)
                lang_lines[lang] += line_count
            except (OSError, IOError):
                pass

        total_lines = sum(lang_lines.values()) or 1
        distribution = {}
        for lang, lines in sorted(lang_lines.items(), key=lambda x: -x[1]):
            distribution[lang] = {
                "files": lang_files[lang],
                "lines": lines,
                "percentage": round(lines / total_lines * 100, 1),
            }

        return distribution

    def _count_complexity(self, lines: List[str]) -> int:
        """Count cyclomatic complexity from lines of code."""
        complexity = 1
        for line in lines:
            stripped = line.strip()
            for kw in ['if', 'elif', 'else', 'for', 'while', 'and', 'or', 'except', 'case', 'catch']:
                if re.search(rf'\b{kw}\b', stripped):
                    complexity += 1
        return complexity

    def _complexity_distribution(self, files: List[Dict] = None) -> Dict:
        """Complexity distribution signature."""
        if files is None:
            files = self._scan_files()

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt', '.scala', '.ex', '.hs'}
        complexities = []
        total_complexity = 0
        max_complexity = 0

        for f in files:
            if f["extension"] not in code_extensions:
                continue
            lines = self._read_file_lines(f["full_path"])
            cc = self._count_complexity(lines)
            complexities.append({"file": f["path"], "complexity": cc})
            total_complexity += cc
            if cc > max_complexity:
                max_complexity = cc

        # Distribution buckets
        buckets = {"trivial (1-5)": 0, "simple (6-10)": 0, "moderate (11-20)": 0,
                   "complex (21-50)": 0, "very complex (50+)": 0}
        for c in complexities:
            cc = c["complexity"]
            if cc <= 5:
                buckets["trivial (1-5)"] += 1
            elif cc <= 10:
                buckets["simple (6-10)"] += 1
            elif cc <= 20:
                buckets["moderate (11-20)"] += 1
            elif cc <= 50:
                buckets["complex (21-50)"] += 1
            else:
                buckets["very complex (50+)"] += 1

        avg = total_complexity / len(complexities) if complexities else 0

        # Hash the distribution for fingerprinting
        dist_str = "|".join(f"{k}:{v}" for k, v in sorted(buckets.items()))
        dist_hash = hashlib.md5(dist_str.encode()).hexdigest()[:12]

        return {
            "buckets": buckets,
            "average": round(avg, 1),
            "max": max_complexity,
            "files_analyzed": len(complexities),
            "top_complex_files": sorted(complexities, key=lambda x: -x["complexity"])[:5],
            "signature_hash": dist_hash,
        }

    def _dependency_topology(self, files: List[Dict] = None) -> Dict:
        """Dependency graph topology signature."""
        if files is None:
            files = self._scan_files()

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt'}
        imports = defaultdict(set)  # file -> set of modules it depends on
        import_patterns = [
            r'import\s+([\w.]+)',
            r'from\s+([\w.]+)\s+import',
            r'require\s*[("\']([\w./]+)',
            r'use\s+([\w:]+)',
        ]

        for f in files:
            if f["extension"] not in code_extensions:
                continue
            lines = self._read_file_lines(f["full_path"])
            for line in lines:
                for pattern in import_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        module = match.split(".")[0].split("/")[0]
                        if module:
                            imports[f["path"]].add(module)

        # Build adjacency info
        all_modules = set()
        for deps in imports.values():
            all_modules.update(deps)

        # Topological signature: count in-degree and out-degree distribution
        in_degree = defaultdict(int)
        for source, deps in imports.items():
            for dep in deps:
                in_degree[dep] += 1

        total_imports = sum(len(deps) for deps in imports.values())
        avg_deps = total_imports / len(imports) if imports else 0
        max_deps = max((len(deps) for deps in imports.values()), default=0)

        # Hash the dependency structure
        dep_str = "|".join(sorted(f"{k}:{v}" for k, v in in_degree.items()))
        dep_hash = hashlib.md5(dep_str.encode()).hexdigest()[:12] if dep_str else "empty"

        # Most depended-on modules
        top_modules = sorted(in_degree.items(), key=lambda x: -x[1])[:10]

        return {
            "total_files_with_imports": len(imports),
            "total_imports": total_imports,
            "avg_dependencies": round(avg_deps, 1),
            "max_dependencies": max_deps,
            "unique_modules": len(all_modules),
            "top_modules": [{"module": m, "imported_by": c} for m, c in top_modules],
            "signature_hash": dep_hash,
        }

    def _naming_conventions(self, files: List[Dict] = None) -> Dict:
        """camelCase vs snake_case ratio fingerprint."""
        if files is None:
            files = self._scan_files()

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt', '.scala', '.ex', '.hs'}

        snake_count = 0
        camel_count = 0
        pascal_count = 0
        upper_count = 0
        total_identifiers = 0

        for f in files:
            if f["extension"] not in code_extensions:
                continue
            lines = self._read_file_lines(f["full_path"])
            for line in lines:
                # Find identifiers: word patterns
                identifiers = re.findall(r'\b([a-zA-Z_]\w*)\b', line)
                # Skip language keywords
                keywords = {'if', 'else', 'elif', 'for', 'while', 'in', 'not', 'and',
                            'or', 'def', 'class', 'import', 'from', 'return', 'try',
                            'except', 'finally', 'with', 'as', 'is', 'None', 'True',
                            'False', 'self', 'function', 'var', 'let', 'const', 'new',
                            'this', 'typeof', 'instanceof', 'void', 'null', 'true',
                            'false', 'struct', 'enum', 'impl', 'fn', 'pub', 'use',
                            'mod', 'crate', 'mut', 'ref', 'int', 'str', 'bool', 'float',
                            'print', 'println', 'echo', 'puts', 'end', 'do', 'then',
                            'package', 'module', 'require', 'include', 'extend',
                            'async', 'await', 'yield', 'raise', 'throw', 'catch',
                            'super', 'static', 'final', 'abstract', 'interface',
                            'public', 'private', 'protected', 'override', 'get', 'set'}
                for ident in identifiers:
                    if ident in keywords or len(ident) < 2:
                        continue
                    total_identifiers += 1
                    if ident.startswith('_'):
                        ident = ident.lstrip('_')
                        if not ident:
                            continue
                    if ident.isupper():
                        upper_count += 1
                    elif '_' in ident and not ident[0].isupper():
                        snake_count += 1
                    elif ident[0].isupper():
                        pascal_count += 1
                    elif any(c.isupper() for c in ident[1:]):
                        camel_count += 1

        if total_identifiers == 0:
            return {"dominant": "unknown", "ratios": {}, "total_identifiers": 0}

        ratios = {
            "snake_case": round(snake_count / total_identifiers * 100, 1),
            "camelCase": round(camel_count / total_identifiers * 100, 1),
            "PascalCase": round(pascal_count / total_identifiers * 100, 1),
            "UPPER_CASE": round(upper_count / total_identifiers * 100, 1),
        }

        dominant = max(ratios, key=ratios.get)

        return {
            "dominant": dominant,
            "ratios": ratios,
            "total_identifiers": total_identifiers,
            "snake_count": snake_count,
            "camel_count": camel_count,
            "pascal_count": pascal_count,
            "upper_count": upper_count,
        }

    def _comment_density(self, files: List[Dict] = None) -> Dict:
        """Comment density fingerprint."""
        if files is None:
            files = self._scan_files()

        code_extensions = {ext for ext, _ in LANG_MAP.items()}
        total_comment_lines = 0
        total_code_lines = 0
        file_densities = []

        for f in files:
            if f["extension"] not in code_extensions:
                continue
            lines = self._read_file_lines(f["full_path"])
            if not lines:
                continue

            comment_lines = 0
            code_lines = 0
            in_block_comment = False

            comment_style = self._detect_comment_style(f["full_path"], lines)

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                if comment_style == "hash_line":
                    if stripped.startswith('#'):
                        comment_lines += 1
                    else:
                        code_lines += 1
                elif comment_style == "slash_line":
                    if stripped.startswith('//'):
                        comment_lines += 1
                    elif stripped.startswith('/*') or stripped.endswith('*/'):
                        comment_lines += 1
                    else:
                        code_lines += 1
                elif comment_style == "html_comment":
                    if stripped.startswith('<!--') or stripped.endswith('-->'):
                        comment_lines += 1
                    else:
                        code_lines += 1
                elif comment_style == "sql_comment":
                    if stripped.startswith('--'):
                        comment_lines += 1
                    else:
                        code_lines += 1
                else:
                    # Generic: try common patterns
                    if stripped.startswith(('#', '//', '/*', '*')):
                        comment_lines += 1
                    elif stripped.startswith('"""') or stripped.startswith("'''"):
                        comment_lines += 1
                    else:
                        code_lines += 1

            total_comment_lines += comment_lines
            total_code_lines += code_lines

            total = comment_lines + code_lines
            if total > 0:
                density = comment_lines / total
                file_densities.append({"file": f["path"], "density": round(density, 3)})

        overall_density = total_comment_lines / (total_comment_lines + total_code_lines) if (total_comment_lines + total_code_lines) > 0 else 0

        # Distribution
        low_doc = sum(1 for d in file_densities if d["density"] < 0.05)
        medium_doc = sum(1 for d in file_densities if 0.05 <= d["density"] < 0.20)
        high_doc = sum(1 for d in file_densities if d["density"] >= 0.20)

        return {
            "overall_density": round(overall_density, 3),
            "total_comment_lines": total_comment_lines,
            "total_code_lines": total_code_lines,
            "files_analyzed": len(file_densities),
            "low_documentation": low_doc,
            "medium_documentation": medium_doc,
            "high_documentation": high_doc,
            "least_documented": sorted(file_densities, key=lambda x: x["density"])[:5],
        }

    def _function_size_distribution(self, files: List[Dict] = None) -> Dict:
        """Function size distribution."""
        if files is None:
            files = self._scan_files()

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt', '.scala'}
        func_sizes = []

        func_patterns = {
            '.py': (r'^\s*def\s+\w+', r'^\s*(class\s|def\s|\Z)'),
            '.js': (r'^\s*(?:async\s+)?function\s+\w+|^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\()', None),
            '.ts': (r'^\s*(?:async\s+)?function\s+\w+|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*[:=]', None),
            '.java': (r'^\s*(?:public|private|protected|static|\w+\s+)*\s+\w+\s*\(', r'^\s*\}'),
            '.go': (r'^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+', r'^\s*\}'),
            '.rs': (r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+\w+', r'^\s*\}'),
            '.rb': (r'^\s*def\s+\w+', r'^\s*end'),
            '.php': (r'^\s*(?:public|private|protected|static)?\s*function\s+\w+', r'^\s*\}'),
            '.swift': (r'^\s*(?:public|private|static)?\s*func\s+\w+', r'^\s*\}'),
            '.kt': (r'^\s*(?:fun|internal|public|private)\s+\w+', r'^\s*\}'),
        }

        for f in files:
            ext = f["extension"]
            if ext not in func_patterns:
                continue
            lines = self._read_file_lines(f["full_path"])
            start_pattern, end_pattern = func_patterns[ext]

            in_func = False
            func_start = 0
            for i, line in enumerate(lines):
                if re.match(start_pattern, line):
                    in_func = True
                    func_start = i
                elif in_func:
                    if end_pattern and re.match(end_pattern, line):
                        size = i - func_start + 1
                        if size > 0:
                            func_sizes.append({"file": f["path"], "line": func_start + 1, "size": size})
                        in_func = False
                    elif not end_pattern and (re.match(r'^\s*def\s+\w+', line) or re.match(r'^\s*(?:async\s+)?function\s', line) or re.match(r'^\s*class\s', line)):
                        size = i - func_start
                        if size > 0:
                            func_sizes.append({"file": f["path"], "line": func_start + 1, "size": size})
                        func_start = i

        if not func_sizes:
            return {"average": 0, "max": 0, "total": 0, "distribution": {}}

        sizes = [f["size"] for f in func_sizes]
        avg = sum(sizes) / len(sizes)
        max_size = max(sizes)

        buckets = {"tiny (1-10)": 0, "small (11-25)": 0, "medium (26-50)": 0,
                   "large (51-100)": 0, "huge (100+)": 0}
        for s in sizes:
            if s <= 10:
                buckets["tiny (1-10)"] += 1
            elif s <= 25:
                buckets["small (11-25)"] += 1
            elif s <= 50:
                buckets["medium (26-50)"] += 1
            elif s <= 100:
                buckets["large (51-100)"] += 1
            else:
                buckets["huge (100+)"] += 1

        return {
            "average": round(avg, 1),
            "max": max_size,
            "total": len(func_sizes),
            "distribution": buckets,
            "largest_functions": sorted(func_sizes, key=lambda x: -x["size"])[:5],
        }

    def _file_size_distribution(self, files: List[Dict] = None) -> Dict:
        """File size distribution."""
        if files is None:
            files = self._scan_files()

        if not files:
            return {"average": 0, "max": 0, "total_files": 0, "distribution": {}}

        sizes = [f["size"] for f in files]
        avg = sum(sizes) / len(sizes)
        max_size = max(sizes)
        total = sum(sizes)

        buckets = {"tiny (<1KB)": 0, "small (1-10KB)": 0, "medium (10-50KB)": 0,
                   "large (50-200KB)": 0, "huge (200KB+)": 0}
        for s in sizes:
            if s < 1024:
                buckets["tiny (<1KB)"] += 1
            elif s < 10240:
                buckets["small (1-10KB)"] += 1
            elif s < 51200:
                buckets["medium (10-50KB)"] += 1
            elif s < 204800:
                buckets["large (50-200KB)"] += 1
            else:
                buckets["huge (200KB+)"] += 1

        return {
            "average": round(avg, 0),
            "max": max_size,
            "total_size": total,
            "total_files": len(files),
            "distribution": buckets,
            "largest_files": sorted(files, key=lambda x: -x["size"])[:5],
        }

    def compare_fingerprints(self, fp1: Dict, fp2: Dict) -> Dict:
        """Compare two fingerprints, show similarity percentage."""
        if not fp1 or not fp2:
            return {"error": "Both fingerprints must be non-empty", "similarity": 0}

        scores = {}

        # Compare language distribution
        lang1 = fp1.get("language_distribution", {})
        lang2 = fp2.get("language_distribution", {})
        langs1 = set(lang1.keys())
        langs2 = set(lang2.keys())
        common_langs = langs1 & langs2
        if langs1 | langs2:
            jaccard_langs = len(common_langs) / len(langs1 | langs2)
        else:
            jaccard_langs = 1.0
        # Also compare percentages
        pct_diff = 0
        for lang in common_langs:
            pct1 = lang1[lang].get("percentage", 0) if isinstance(lang1[lang], dict) else lang1[lang]
            pct2 = lang2[lang].get("percentage", 0) if isinstance(lang2[lang], dict) else lang2[lang]
            pct_diff += abs(pct1 - pct2)
        max_pct_diff = sum(max(
            lang1.get(l, {}).get("percentage", 0) if isinstance(lang1.get(l), dict) else lang1.get(l, 0),
            lang2.get(l, {}).get("percentage", 0) if isinstance(lang2.get(l), dict) else lang2.get(l, 0)
        ) for l in langs1 | langs2) or 1
        pct_similarity = 1.0 - (pct_diff / max_pct_diff)
        scores["languages"] = round((jaccard_langs + pct_similarity) / 2 * 100, 1)

        # Compare complexity distribution
        c1 = fp1.get("complexity_distribution", {})
        c2 = fp2.get("complexity_distribution", {})
        buckets1 = c1.get("buckets", {}) if isinstance(c1, dict) else {}
        buckets2 = c2.get("buckets", {}) if isinstance(c2, dict) else {}
        if buckets1 and buckets2:
            all_keys = set(buckets1.keys()) | set(buckets2.keys())
            total1 = sum(buckets1.values()) or 1
            total2 = sum(buckets2.values()) or 1
            diff = sum(abs(buckets1.get(k, 0) / total1 - buckets2.get(k, 0) / total2) for k in all_keys)
            scores["complexity"] = round((1 - diff / 2) * 100, 1)
        else:
            scores["complexity"] = 50.0

        # Compare naming conventions
        n1 = fp1.get("naming_conventions", {})
        n2 = fp2.get("naming_conventions", {})
        ratios1 = n1.get("ratios", {}) if isinstance(n1, dict) else {}
        ratios2 = n2.get("ratios", {}) if isinstance(n2, dict) else {}
        if ratios1 and ratios2:
            all_keys = set(ratios1.keys()) | set(ratios2.keys())
            diff = sum(abs(ratios1.get(k, 0) - ratios2.get(k, 0)) for k in all_keys)
            max_diff = sum(max(ratios1.get(k, 0), ratios2.get(k, 0)) for k in all_keys) or 1
            scores["naming"] = round((1 - diff / max_diff) * 100, 1)
        else:
            scores["naming"] = 50.0

        # Compare comment density
        cd1 = fp1.get("comment_density", {})
        cd2 = fp2.get("comment_density", {})
        d1 = cd1.get("overall_density", 0) if isinstance(cd1, dict) else 0
        d2 = cd2.get("overall_density", 0) if isinstance(cd2, dict) else 0
        max_d = max(d1, d2) or 0.01
        scores["comments"] = round((1 - abs(d1 - d2) / max_d) * 100, 1)

        # Compare file count ratio
        f1 = fp1.get("total_files", 0)
        f2 = fp2.get("total_files", 0)
        max_f = max(f1, f2) or 1
        scores["scale"] = round(min(f1, f2) / max_f * 100, 1)

        # Overall similarity (weighted average)
        weights = {"languages": 0.3, "complexity": 0.2, "naming": 0.2, "comments": 0.15, "scale": 0.15}
        overall = sum(scores.get(k, 50) * weights[k] for k in weights)

        return {
            "overall_similarity": round(overall, 1),
            "category_scores": scores,
            "project1": fp1.get("project", "unknown"),
            "project2": fp2.get("project", "unknown"),
            "verdict": (
                "Nearly identical codebase" if overall > 90 else
                "Very similar — likely forked or closely related" if overall > 75 else
                "Somewhat similar — may share common patterns" if overall > 50 else
                "Different codebases" if overall > 25 else
                "Completely different projects"
            ),
        }

    def detect_clones(self) -> List[Dict]:
        """Detect files that look like they were copied."""
        files = self._scan_files()
        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php',
                           '.c', '.cpp', '.cs', '.swift', '.kt'}
        code_files = [f for f in files if f["extension"] in code_extensions]

        # Hash each file's normalized content (strip whitespace, lowercase identifiers)
        file_hashes = {}
        for f in code_files:
            lines = self._read_file_lines(f["full_path"])
            # Normalize: strip whitespace, remove comments
            normalized = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith(('#', '//', '/*', '*')):
                    continue
                normalized.append(re.sub(r'\s+', ' ', stripped).lower())
            content = "\n".join(normalized)
            if content:
                h = hashlib.md5(content.encode()).hexdigest()
                if h not in file_hashes:
                    file_hashes[h] = []
                file_hashes[h].append(f["path"])

        clones = []
        for h, paths in file_hashes.items():
            if len(paths) > 1:
                clones.append({
                    "hash": h[:12],
                    "files": paths,
                    "count": len(paths),
                })

        clones.sort(key=lambda x: -x["count"])

        # Also detect near-clones by comparing 6-line block hashes
        block_hashes = defaultdict(list)
        for f in code_files:
            lines = self._read_file_lines(f["full_path"])
            for i in range(len(lines) - 5):
                block = "\n".join(lines[i:i + 6])
                block_h = hashlib.md5(block.encode()).hexdigest()
                block_hashes[block_h].append((f["path"], i + 1))

        near_clones = []
        for h, locations in block_hashes.items():
            if len(locations) > 1:
                # Check if these are from different files
                files_involved = set(loc[0] for loc in locations)
                if len(files_involved) > 1:
                    near_clones.append({
                        "block_hash": h[:12],
                        "locations": locations,
                        "files": list(files_involved),
                        "occurrences": len(locations),
                    })

        near_clones.sort(key=lambda x: -x["occurrences"])

        return {
            "exact_clones": clones[:10],
            "near_clones": near_clones[:10],
            "total_exact_clones": len(clones),
            "total_near_clone_blocks": len(near_clones),
        }

    def generate_barcode(self) -> str:
        """Generate ASCII art DNA barcode from the fingerprint."""
        if not self.fingerprint:
            self.generate_fingerprint()

        # Create deterministic data string from fingerprint
        data_parts = []

        # Language mix
        lang_dist = self.fingerprint.get("language_distribution", {})
        for lang, info in sorted(lang_dist.items()):
            if isinstance(info, dict):
                data_parts.append(f"{lang}:{info.get('percentage', 0)}")
            else:
                data_parts.append(f"{lang}:{info}")

        # Complexity signature
        comp = self.fingerprint.get("complexity_distribution", {})
        if isinstance(comp, dict):
            data_parts.append(f"cc:{comp.get('average', 0)}")

        # Naming style
        naming = self.fingerprint.get("naming_conventions", {})
        if isinstance(naming, dict):
            data_parts.append(f"dom:{naming.get('dominant', 'unknown')}")

        # Comment density
        cd = self.fingerprint.get("comment_density", {})
        if isinstance(cd, dict):
            data_parts.append(f"doc:{cd.get('overall_density', 0)}")

        data_str = "|".join(data_parts)
        barcode_hash = hashlib.sha256(data_str.encode()).hexdigest()

        # Generate barcode lines (each character maps to a bar pattern)
        lines = []
        lines.append("")
        lines.append("  ┌─────────────────────────────────────────────────────┐")
        lines.append("  │              🧬 CodeDNA Barcode                     │")
        lines.append("  ├─────────────────────────────────────────────────────┤")

        # Main barcode - 4 lines of bars
        for row in range(4):
            bar_line = "  │  "
            for i in range(0, len(barcode_hash), 2):
                pair = barcode_hash[i:i + 2]
                val = int(pair, 16)
                # Map to bar pattern (█, ▓, ▒, ░, space)
                if row == 0:
                    pattern = '█' if val > 191 else '▓' if val > 127 else '▒' if val > 63 else '░' if val > 15 else ' '
                elif row == 1:
                    pattern = '▓' if val > 223 else '█' if val > 159 else '░' if val > 95 else '▒' if val > 31 else ' '
                elif row == 2:
                    pattern = '▒' if val > 207 else '░' if val > 143 else '█' if val > 79 else '▓' if val > 15 else ' '
                else:
                    pattern = '░' if val > 239 else '▒' if val > 175 else '▓' if val > 111 else '█' if val > 47 else ' '
                bar_line += pattern + pattern
            bar_line = bar_line[:52] + " " * max(52 - len(bar_line), 0)
            lines.append(bar_line[:52] + "│")

        lines.append("  ├─────────────────────────────────────────────────────┤")

        # Summary line
        project = self.fingerprint.get("project", "unknown")
        total_files = self.fingerprint.get("total_files", 0)
        lines.append(f"  │  Project: {project:<37s} files: {total_files:<5d}│")

        # Language line
        top_langs = list(self.fingerprint.get("language_distribution", {}).items())[:3]
        lang_str = ", ".join(
            f"{l} {info['percentage']}%" if isinstance(info, dict) else f"{l}"
            for l, info in top_langs
        )
        lang_str = lang_str[:43]
        lines.append(f"  │  Languages: {lang_str:<39s}│")

        # Naming
        naming = self.fingerprint.get("naming_conventions", {})
        dom = naming.get("dominant", "unknown") if isinstance(naming, dict) else "unknown"
        lines.append(f"  │  Naming: {dom:<42s}│")

        # Hash
        lines.append(f"  │  Hash: {self.fingerprint.get('hash_patterns', 'N/A'):<42s}│")
        lines.append("  └─────────────────────────────────────────────────────┘")

        # Compact barcode for terminals
        lines.append("")
        lines.append("  Compact: ", )
        compact = ""
        for i in range(0, min(len(barcode_hash), 40), 2):
            val = int(barcode_hash[i:i+2], 16)
            compact += '█' if val > 127 else '░'
        lines.append(f"  [{compact}]")
        lines.append(f"  {barcode_hash[:32]}...")

        return "\n".join(lines)

    def save_fingerprint(self, path: str) -> None:
        """Save fingerprint to JSON file."""
        if not self.fingerprint:
            self.generate_fingerprint()
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.fingerprint, f, indent=2, default=str)

    def load_fingerprint(self, path: str) -> Dict:
        """Load fingerprint from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.fingerprint = data
        return data
