"""CodeVista Lint Rules — language-specific style and lint rules.

Supports: Python (PEP 8/Black), JavaScript/TypeScript (Airbnb),
Go (gofmt), Rust (clippy-lite), Java (Google style).

Each rule: rule_id, language, severity, description, detection function.
Returns list of LintViolation(file, line, rule_id, severity, message).
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LintViolation:
    """A single lint violation found in a file."""
    file: str
    line: int
    col: int = 0
    rule_id: str = ""
    language: str = ""
    severity: str = "warning"   # error / warning / info
    message: str = ""
    snippet: str = ""

    def __str__(self):
        loc = f"{self.file}:{self.line}" + (f":{self.col}" if self.col else "")
        sev = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(self.severity, "⚪")
        return f"  {sev} [{self.severity.upper()}] {self.rule_id}  {loc}  {self.message}"


@dataclass
class LintRule:
    """Definition of a lint rule."""
    rule_id: str
    language: str
    severity: str
    description: str
    check: Callable[[str, str], List[LintViolation]]  # (filepath, content) -> violations


# ──────────────────────────────────────────────────────────────────────
# Language registry
# ──────────────────────────────────────────────────────────────────────

LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}

# map typescript/javascript together for shared rules
LANGUAGE_ALIASES = {
    "typescript": "javascript",
}


# ──────────────────────────────────────────────────────────────────────
# Python rules (PEP 8 / Black)
# ──────────────────────────────────────────────────────────────────────

def _py_max_line_length(filepath: str, content: str, max_len: int = 88) -> List[LintViolation]:
    """PY001: Max line length (default 88 for Black, 79 for PEP 8)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        if len(line) > max_len:
            violations.append(LintViolation(
                file=filepath, line=i, col=max_len,
                rule_id="PY001", language="python", severity="warning",
                message=f"Line too long ({len(line)} > {max_len} chars)",
                snippet=line[:max_len] + "...",
            ))
    return violations


def _py_no_wildcard_imports(filepath: str, content: str) -> List[LintViolation]:
    """PY002: No wildcard imports (from x import *)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r'^from\s+\S+\s+import\s+\*', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="PY002",
                language="python", severity="error",
                message="Wildcard import detected; import specific names",
                snippet=stripped,
            ))
    return violations


def _py_import_order(filepath: str, content: str) -> List[LintViolation]:
    """PY003: Imports should be ordered stdlib → third-party → local, alphabetized."""
    STDLIB_MODULES = {
        "abc", "aifc", "argparse", "array", "ast", "asyncio", "atexit", "base64",
        "binascii", "bisect", "builtins", "bz2", "calendar", "cgi", "cmath",
        "cmd", "code", "codecs", "collections", "colorsys", "concurrent",
        "configparser", "contextlib", "contextvars", "copy", "copyreg",
        "cProfile", "csv", "ctypes", "dataclasses", "datetime", "dbm",
        "decimal", "difflib", "dis", "doctest", "email", "enum", "errno",
        "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
        "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob",
        "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
        "imaplib", "importlib", "inspect", "io", "ipaddress", "itertools",
        "json", "keyword", "lib2to3", "linecache", "locale", "logging",
        "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
        "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
        "numbers", "operator", "optparse", "os", "pathlib", "pdb", "pickle",
        "pickletools", "pipes", "pkgutil", "platform", "plistlib", "poplib",
        "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
        "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re",
        "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
        "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
        "site", "smtpd", "smtplib", "socket", "socketserver", "sqlite3",
        "ssl", "stat", "statistics", "string", "struct", "subprocess", "sunau",
        "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
        "tempfile", "termios", "test", "textwrap", "threading", "time",
        "timeit", "tkinter", "token", "tokenize", "trace", "traceback",
        "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing",
        "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
        "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
        "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    }
    violations = []
    import_blocks = []
    current_block = []
    block_start = None

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            if not current_block:
                block_start = i + 1
            current_block.append((i + 1, stripped))
        elif stripped and current_block:
            import_blocks.append((block_start, current_block))
            current_block = []
            block_start = None
        i += 1
    if current_block:
        import_blocks.append((block_start, current_block))

    for _, block in import_blocks:
        groups = {"stdlib": [], "third_party": [], "local": []}
        for line_no, imp in block:
            match = re.match(r'^(?:from\s+)?([\w.]+)', imp)
            if not match:
                continue
            module = match.group(1).split(".")[0]
            if module in STDLIB_MODULES:
                groups["stdlib"].append((line_no, module, imp))
            elif module.startswith("."):
                groups["local"].append((line_no, module, imp))
            else:
                groups["third_party"].append((line_no, module, imp))

        # Check if groups are interleaved
        expected_order = []
        for group in ("stdlib", "third_party", "local"):
            expected_order.extend(groups[group])

        for idx in range(1, len(expected_order)):
            prev_module = expected_order[idx - 1][1]
            curr_module = expected_order[idx][1]
            prev_group = "stdlib" if prev_module in STDLIB_MODULES else ("local" if prev_module.startswith(".") else "third_party")
            curr_group = "stdlib" if curr_module in STDLIB_MODULES else ("local" if curr_module.startswith(".") else "third_party")
            group_order = {"stdlib": 0, "third_party": 1, "local": 2}
            if group_order[curr_group] < group_order[prev_group]:
                violations.append(LintViolation(
                    file=filepath, line=expected_order[idx][0],
                    rule_id="PY003", language="python", severity="info",
                    message=f"'{curr_module}' ({curr_group}) should come before '{prev_module}' ({prev_group}) — "
                            f"expected order: stdlib → third-party → local",
                    snippet=expected_order[idx][2],
                ))
                break

        # Check alphabetical within each group
        for group_name, items in groups.items():
            for idx in range(1, len(items)):
                if items[idx][1].lower() < items[idx - 1][1].lower():
                    violations.append(LintViolation(
                        file=filepath, line=items[idx][0],
                        rule_id="PY003", language="python", severity="info",
                        message=f"'{items[idx][1]}' is not alphabetically ordered within {group_name} imports",
                        snippet=items[idx][2],
                    ))
                    break

    return violations


def _py_blank_lines_functions(filepath: str, content: str) -> List[LintViolation]:
    """PY004: Two blank lines before top-level functions/classes."""
    violations = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^(def |class |@)', stripped):
            # Check preceding non-blank, non-decorator, non-comment lines
            blank_count = 0
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                blank_count += 1
                j -= 1
            # Skip decorators/comments right before
            while j >= 0 and (lines[j].strip().startswith("@") or
                              lines[j].strip().startswith("#") or
                              lines[j].strip().startswith("\"\"\"") or
                              lines[j].strip().startswith("'")):
                j -= 1
            # Re-count blanks before the actual code
            blank_count2 = 0
            k = i - 1
            while k > j:
                if lines[k].strip() == "":
                    blank_count2 += 1
                k -= 1
            if j >= 0 and not (stripped.startswith("@")):
                # Top-level: need 2 blank lines
                # Check if we're at top level (not indented)
                if not line.startswith(" ") and not line.startswith("\t"):
                    if blank_count2 < 2 and blank_count2 != -1:
                        violations.append(LintViolation(
                            file=filepath, line=i + 1, rule_id="PY004",
                            language="python", severity="info",
                            message=f"Expected 2 blank lines before top-level definition (found {blank_count2})",
                        ))
    return violations


def _py_blank_lines_methods(filepath: str, content: str) -> List[LintViolation]:
    """PY005: One blank line before methods inside a class."""
    violations = []
    lines = content.splitlines()
    prev_indent = 0
    prev_blank = False
    for i, line in enumerate(lines[1:], 2):
        stripped = line.strip()
        if stripped.startswith("def ") and (line.startswith("    ") or line.startswith("\t")):
            indent = len(line) - len(line.lstrip())
            if indent > 0 and prev_indent > 0 and not prev_blank:
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="PY005",
                    language="python", severity="info",
                    message="Expected 1 blank line before method definition",
                ))
        if stripped:
            prev_indent = len(line) - len(line.lstrip())
            prev_blank = False
        else:
            prev_blank = True
    return violations


def _py_spaces_around_operators(filepath: str, content: str) -> List[LintViolation]:
    """PY006: Spaces around binary operators (PEP 8)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("\"\"\"") or stripped.startswith("'"):
            continue
        # Check for missing spaces around = (assignment)
        if re.search(r'(?<!=)=(?!=)', line):
            # Find bare = assignments (not ==, !=, <=, >=)
            matches = re.finditer(r'(?<![=<>!])=(?![=])', line)
            for m in matches:
                before = m.start() - 1
                after = m.end()
                # Skip default args, keyword args (allow x=1)
                if before >= 0 and line[before] in "(,":
                    continue
                if before >= 0 and line[before] != " " and after < len(line) and line[after] != " ":
                    violations.append(LintViolation(
                        file=filepath, line=i, col=m.start() + 1,
                        rule_id="PY006", language="python", severity="info",
                        message="Missing spaces around assignment operator",
                    ))
    return violations


def _py_fstring_over_format(filepath: str, content: str) -> List[LintViolation]:
    """PY007: Prefer f-strings over .format() or % formatting."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.search(r'\.format\(', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="PY007",
                language="python", severity="info",
                message="Prefer f-string over .format()",
                snippet=stripped[:80],
            ))
        elif re.search(r'%[sd]', stripped) and "(" not in stripped[:stripped.find("%")]:
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="PY007",
                language="python", severity="info",
                message="Prefer f-string over %-formatting",
                snippet=stripped[:80],
            ))
    return violations


def _py_type_hints_public(filepath: str, content: str) -> List[LintViolation]:
    """PY008: Public functions should have type hints on return (at minimum)."""
    violations = []
    in_class = False
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("class "):
            in_class = True
        elif stripped and not stripped.startswith(" ") and not stripped.startswith("\t") and not stripped.startswith("#"):
            if not stripped.startswith("class "):
                in_class = False
        if stripped.startswith("def "):
            # Check if it's a public function (not starting with _)
            func_name_match = re.match(r'def\s+([a-zA-Z_]\w*)\s*\(', stripped)
            if func_name_match:
                func_name = func_name_match.group(1)
                if not func_name.startswith("_") and in_class:
                    continue  # skip public methods in class (they could have self)
                if not func_name.startswith("_"):
                    # Check for return type hint
                    if "->" not in stripped:
                        violations.append(LintViolation(
                            file=filepath, line=i, rule_id="PY008",
                            language="python", severity="info",
                            message=f"Public function '{func_name}' missing return type hint",
                        ))
    return violations


def _py_naming_conventions(filepath: str, content: str) -> List[LintViolation]:
    """PY009: Naming conventions — snake_case functions/vars, PascalCase classes, UPPER constants."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Class names: PascalCase
        class_match = re.match(r'^class\s+([a-zA-Z_]\w*)', stripped)
        if class_match:
            name = class_match.group(1)
            if name[0].islower() and not name.isupper():
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="PY009",
                    language="python", severity="warning",
                    message=f"Class '{name}' should use PascalCase",
                    snippet=stripped[:60],
                ))

        # Function names: snake_case (top-level only)
        func_match = re.match(r'^def\s+([a-zA-Z_]\w*)\s*\(', stripped)
        if func_match:
            name = func_match.group(1)
            if re.search(r'[A-Z]', name) and not name.startswith("_") and not name.isupper():
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="PY009",
                    language="python", severity="info",
                    message=f"Function '{name}' should use snake_case",
                    snippet=stripped[:60],
                ))

        # UPPER_CASE constants (top-level assignments)
        if not stripped.startswith(" ") and not stripped.startswith("\t"):
            const_match = re.match(r'^([A-Z_][A-Z_0-9]*)\s*=\s*', stripped)
            if const_match:
                name = const_match.group(1)
                if len(name) > 1 and not name.isupper():
                    violations.append(LintViolation(
                        file=filepath, line=i, rule_id="PY009",
                        language="python", severity="info",
                        message=f"Constant '{name}' should use UPPER_CASE",
                        snippet=stripped[:60],
                    ))
    return violations


def _py_trailing_whitespace(filepath: str, content: str) -> List[LintViolation]:
    """PY010: No trailing whitespace."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        if line != line.rstrip() and line.strip():
            violations.append(LintViolation(
                file=filepath, line=i, col=len(line.rstrip()) + 1,
                rule_id="PY010", language="python", severity="info",
                message="Trailing whitespace",
            ))
    return violations


def _py_no_multiple_statements(filepath: str, content: str) -> List[LintViolation]:
    """PY011: No multiple statements on one line (separated by ;)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Simple check: semicolons not inside strings (rough heuristic)
        code_part = re.sub(r'([\"\']).*?\1', '', stripped)  # strip simple strings
        if ";" in code_part:
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="PY011",
                language="python", severity="warning",
                message="Multiple statements on one line (semicolon found)",
                snippet=stripped[:80],
            ))
    return violations


PYTHON_RULES: List[LintRule] = [
    LintRule("PY001", "python", "warning", "Max line length (88 for Black)",
             lambda fp, c: _py_max_line_length(fp, c, 88)),
    LintRule("PY002", "python", "error", "No wildcard imports (from x import *)",
             _py_no_wildcard_imports),
    LintRule("PY003", "python", "info", "Import order: stdlib → third-party → local, alphabetized",
             _py_import_order),
    LintRule("PY004", "python", "info", "Two blank lines before top-level definitions",
             _py_blank_lines_functions),
    LintRule("PY005", "python", "info", "One blank line before methods",
             _py_blank_lines_methods),
    LintRule("PY006", "python", "info", "Spaces around operators",
             _py_spaces_around_operators),
    LintRule("PY007", "python", "info", "Prefer f-strings over .format() / %-formatting",
             _py_fstring_over_format),
    LintRule("PY008", "python", "info", "Type hints on public functions",
             _py_type_hints_public),
    LintRule("PY009", "python", "warning", "Naming conventions (snake_case, PascalCase, UPPER_CASE)",
             _py_naming_conventions),
    LintRule("PY010", "python", "info", "No trailing whitespace",
             _py_trailing_whitespace),
    LintRule("PY011", "python", "warning", "No multiple statements on one line",
             _py_no_multiple_statements),
]


# ──────────────────────────────────────────────────────────────────────
# JavaScript / TypeScript rules (Airbnb style)
# ──────────────────────────────────────────────────────────────────────

def _js_no_var(filepath: str, content: str) -> List[LintViolation]:
    """JS001: No var — use const or let."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if re.search(r'\bvar\s+', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS001",
                language="javascript", severity="error",
                message="Unexpected var, use const or let",
                snippet=stripped[:80],
            ))
    return violations


def _js_template_literals(filepath: str, content: str) -> List[LintViolation]:
    """JS002: Prefer template literals over string concatenation with +."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Detect string + variable concatenation: "foo" + bar or 'foo' + bar
        if re.search(r"""['"][^'"]*['"]\s*\+\s*\w""", stripped) and "${" not in stripped:
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS002",
                language="javascript", severity="info",
                message="Prefer template literals over string concatenation",
                snippet=stripped[:80],
            ))
    return violations


def _js_arrow_callbacks(filepath: str, content: str) -> List[LintViolation]:
    """JS003: Use arrow functions for callbacks."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # function(x) { or function(x) used as argument
        if re.search(r'function\s*\([^)]*\)\s*\{', stripped):
            # Check if it looks like a callback (preceded by , ( or =)
            before = line[:line.index(stripped)].rstrip()
            if before.endswith(",") or before.endswith("(") or before.endswith("="):
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="JS003",
                    language="javascript", severity="info",
                    message="Prefer arrow function for callbacks",
                    snippet=stripped[:80],
                ))
    return violations


def _js_strict_equality(filepath: str, content: str) -> List[LintViolation]:
    """JS004: Use === instead of ==."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        # Find == but not === or !==
        if re.search(r'(?<![!=])==(?!=)', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS004",
                language="javascript", severity="warning",
                message="Use === instead of ==",
                snippet=stripped[:80],
            ))
    return violations


def _js_indentation(filepath: str, content: str) -> List[LintViolation]:
    """JS005: 2-space indentation."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        if not line or line.strip() == "" or line.strip().startswith("//"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent > 0:
            if line.startswith("\t"):
                violations.append(LintViolation(
                    file=filepath, line=i, col=1, rule_id="JS005",
                    language="javascript", severity="warning",
                    message="Expected 2-space indentation, found tab",
                ))
            elif indent % 2 != 0:
                violations.append(LintViolation(
                    file=filepath, line=i, col=1, rule_id="JS005",
                    language="javascript", severity="info",
                    message=f"Indentation not a multiple of 2 (found {indent} spaces)",
                ))
    return violations


def _js_no_unused_vars(filepath: str, content: str) -> List[LintViolation]:
    """JS006: Detect unused variables (simple heuristic)."""
    violations = []
    lines = content.splitlines()
    var_names = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # const/let/var x = ...
        match = re.match(r'(?:const|let|var)\s+([a-zA-Z_$]\w*)\s*=', stripped)
        if match:
            var_names.append((match.group(1), i + 1))

    for name, line_no in var_names:
        # Check if the variable appears again (excluding the declaration line)
        pattern = re.compile(r'\b' + re.escape(name) + r'\b')
        usage_count = sum(
            1 for j, l in enumerate(lines)
            if j != line_no - 1 and pattern.search(l) and not l.strip().startswith("//")
        )
        if usage_count == 0:
            violations.append(LintViolation(
                file=filepath, line=line_no, rule_id="JS006",
                language="javascript", severity="warning",
                message=f"Variable '{name}' is declared but never used",
            ))
    return violations


def _js_destructuring(filepath: str, content: str) -> List[LintViolation]:
    """JS007: Prefer destructuring when accessing object properties repeatedly."""
    violations = []
    # Simple heuristic: obj.prop used 3+ times without destructuring
    lines = content.splitlines()
    prop_access: Dict[str, List[int]] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        matches = re.findall(r'(\w+)\.\w+', stripped)
        for obj in matches:
            prop_access.setdefault(obj, []).append(i + 1)

    for obj, occurrences in prop_access.items():
        if len(occurrences) >= 4 and obj not in ("console", "Math", "JSON", "Object", "Array",
                                                     "String", "Number", "Promise", "window",
                                                     "document", "process", "module", "exports",
                                                     "require", "this", "super"):
            violations.append(LintViolation(
                file=filepath, line=occurrences[0], rule_id="JS007",
                language="javascript", severity="info",
                message=f"'{obj}' accessed {len(occurrences)} times — consider destructuring",
                snippet=f"  {obj}.prop  ({len(occurrences)} accesses)",
            ))
    return violations


def _js_object_shorthand(filepath: str, content: str) -> List[LintViolation]:
    """JS008: Use object shorthand { x } instead of { x: x }."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        matches = re.findall(r'(\w+)\s*:\s*\1(?!\w)', stripped)
        for name in set(matches):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS008",
                language="javascript", severity="info",
                message=f"Use object shorthand '{{ {name} }}' instead of '{{ {name}: {name} }}'",
                snippet=stripped[:80],
            ))
    return violations


def _js_no_trailing_comma_newline(filepath: str, content: str) -> List[LintViolation]:
    """JS009: Allow trailing commas in multiline (ES2017+), warn on single-line trailing commas."""
    violations = []
    in_multiline = False
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.rstrip()
        if '{' in stripped or '[' in stripped or '(' in stripped:
            in_multiline = True
        if stripped.endswith(',}'):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS009",
                language="javascript", severity="warning",
                message="Trailing comma before closing brace — remove or add newline",
                snippet=stripped[:80],
            ))
        elif in_multiline and stripped.endswith(',') and ('}' in stripped or ']' in stripped or ')' in stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JS009",
                language="javascript", severity="info",
                message="Trailing comma before closing bracket on same line",
                snippet=stripped[:80],
            ))
        if '}' in stripped or ']' in stripped or ')' in stripped:
            in_multiline = False
    return violations


JS_RULES: List[LintRule] = [
    LintRule("JS001", "javascript", "error", "No var — use const or let", _js_no_var),
    LintRule("JS002", "javascript", "info", "Prefer template literals over string concatenation",
             _js_template_literals),
    LintRule("JS003", "javascript", "info", "Use arrow functions for callbacks", _js_arrow_callbacks),
    LintRule("JS004", "javascript", "warning", "Use === instead of ==", _js_strict_equality),
    LintRule("JS005", "javascript", "warning", "2-space indentation (no tabs)", _js_indentation),
    LintRule("JS006", "javascript", "warning", "No unused variables", _js_no_unused_vars),
    LintRule("JS007", "javascript", "info", "Prefer destructuring for repeated property access",
             _js_destructuring),
    LintRule("JS008", "javascript", "info", "Use object shorthand syntax", _js_object_shorthand),
    LintRule("JS009", "javascript", "info", "Trailing comma conventions", _js_no_trailing_comma_newline),
]


# ──────────────────────────────────────────────────────────────────────
# Go rules (gofmt style)
# ──────────────────────────────────────────────────────────────────────

def _go_tab_indentation(filepath: str, content: str) -> List[LintViolation]:
    """GO001: Tab indentation required."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        if not line or line.strip() == "" or line.strip().startswith("//"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent > 0:
            # Check if using spaces instead of tabs
            if line.startswith(" " * indent) and not line.startswith("\t"):
                violations.append(LintViolation(
                    file=filepath, line=i, col=1, rule_id="GO001",
                    language="go", severity="error",
                    message=f"Go requires tab indentation (found {indent} spaces)",
                ))
    return violations


def _go_no_unused_imports(filepath: str, content: str) -> List[LintViolation]:
    """GO002: No unused imports."""
    violations = []
    lines = content.splitlines()
    imports = []
    in_import = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ("):
            in_import = True
            continue
        if in_import:
            if stripped == ")":
                in_import = False
                continue
            pkg = stripped.strip('"').strip()
            imports.append((pkg, i + 1))
        elif stripped.startswith("import "):
            pkg = stripped.split('"')[1] if '"' in stripped else ""
            if pkg:
                imports.append((pkg, i + 1))

    for pkg, line_no in imports:
        # Extract the package alias (last component)
        alias = pkg.split("/")[-1] if "/" in pkg else pkg
        pattern = re.compile(r'\b' + re.escape(alias) + r'\.')
        usage = sum(1 for l in lines if pattern.search(l) and not l.strip().startswith("import"))
        if usage == 0:
            violations.append(LintViolation(
                file=filepath, line=line_no, rule_id="GO002",
                language="go", severity="error",
                message=f"Import '{pkg}' is unused",
            ))
    return violations


def _go_exported_doc_comment(filepath: str, content: str) -> List[LintViolation]:
    """GO003: Exported names must have a doc comment."""
    violations = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Exported function
        match = re.match(r'func\s+([A-Z]\w*)', stripped)
        if match:
            name = match.group(1)
            # Check for doc comment above
            has_doc = False
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            if j >= 0 and lines[j].strip().startswith("//"):
                has_doc = True
            if not has_doc:
                violations.append(LintViolation(
                    file=filepath, line=i + 1, rule_id="GO003",
                    language="go", severity="warning",
                    message=f"Exported function '{name}' should have a doc comment",
                ))
            continue
        # Exported type
        match = re.match(r'type\s+([A-Z]\w*)\s+struct', stripped)
        if match:
            name = match.group(1)
            has_doc = False
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            if j >= 0 and lines[j].strip().startswith("//"):
                has_doc = True
            if not has_doc:
                violations.append(LintViolation(
                    file=filepath, line=i + 1, rule_id="GO003",
                    language="go", severity="warning",
                    message=f"Exported type '{name}' should have a doc comment",
                ))
    return violations


def _go_error_handling(filepath: str, content: str) -> List[LintViolation]:
    """GO004: No discarded errors (_ = err)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if re.search(r'_\s*=\s*\w+Err|_\s*=\s*\w+\(\)', stripped):
            if "err" in stripped.lower():
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="GO004",
                    language="go", severity="error",
                    message="Error return value is not checked — do not discard with _",
                    snippet=stripped[:80],
                ))
    return violations


def _go_no_shadow(filepath: str, content: str) -> List[LintViolation]:
    """GO005: No := in inner scopes shadowing outer variables."""
    violations = []
    lines = content.splitlines()
    outer_vars = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Outer scope assignments
        match = re.match(r'(\w+)\s*:?=', stripped)
        if match and not stripped.startswith("\t") and not stripped.startswith(" "):
            outer_vars.add(match.group(1))
        # Inner scope with :=
        if stripped.startswith("\t") or stripped.startswith(" "):
            match = re.match(r'\s*(\w+)\s*:=', stripped)
            if match:
                name = match.group(1)
                if name in outer_vars and name != "err":
                    violations.append(LintViolation(
                        file=filepath, line=i + 1, rule_id="GO005",
                        language="go", severity="warning",
                        message=f"Variable '{name}' shadows outer declaration",
                        snippet=stripped[:60],
                    ))
    return violations


GO_RULES: List[LintRule] = [
    LintRule("GO001", "go", "error", "Tab indentation required", _go_tab_indentation),
    LintRule("GO002", "go", "error", "No unused imports", _go_no_unused_imports),
    LintRule("GO003", "go", "warning", "Exported names must have doc comment", _go_exported_doc_comment),
    LintRule("GO004", "go", "error", "Error handling — do not discard errors", _go_error_handling),
    LintRule("GO005", "go", "warning", "No variable shadowing in inner scopes", _go_no_shadow),
]


# ──────────────────────────────────────────────────────────────────────
# Rust rules (clippy-lite)
# ──────────────────────────────────────────────────────────────────────

def _rs_no_unwrap(filepath: str, content: str) -> List[LintViolation]:
    """RS001: No .unwrap() in production code."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if re.search(r'\.unwrap\(\)', stripped):
            # Allow in test modules and #[test] functions
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS001",
                language="rust", severity="error",
                message="Avoid .unwrap() — use ? or pattern matching instead",
                snippet=stripped[:80],
            ))
        if re.search(r'\.expect\(', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS001",
                language="rust", severity="warning",
                message=".expect() found — consider proper error handling with Result",
                snippet=stripped[:80],
            ))
    return violations


def _rs_option_result(filepath: str, content: str) -> List[LintViolation]:
    """RS002: Use Option/Result properly — no is_some().unwrap() pattern."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if re.search(r'\.is_some\(\)', stripped) and re.search(r'\.unwrap\(\)', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS002",
                language="rust", severity="warning",
                message="Use if let Some(x) = ... or match instead of is_some().unwrap()",
                snippet=stripped[:80],
            ))
        if re.search(r'\.is_ok\(\)', stripped) and re.search(r'\.unwrap\(\)', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS002",
                language="rust", severity="warning",
                message="Use if let Ok(x) = ... or match instead of is_ok().unwrap()",
                snippet=stripped[:80],
            ))
    return violations


def _rs_no_mutable_statics(filepath: str, content: str) -> List[LintViolation]:
    """RS003: No mutable statics."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r'static\s+mut\s+', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS003",
                language="rust", severity="error",
                message="Mutable statics are unsafe — use Mutex, RwLock, or atomics",
                snippet=stripped[:80],
            ))
    return violations


def _rs_no_clippy_deny(filepath: str, content: str) -> List[LintViolation]:
    """RS004: Warn on #[allow(...)] suppressing common clippy lints."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r'#\[allow\(', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS004",
                language="rust", severity="info",
                message="Lint suppression found — consider fixing the issue instead",
                snippet=stripped[:80],
            ))
    return violations


def _rs_naming(filepath: str, content: str) -> List[LintViolation]:
    """RS005: Rust naming conventions (snake_case, UpperCamelCase for types)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Functions: snake_case
        fn_match = re.match(r'(?:pub\s+)?fn\s+([A-Z]\w*)', stripped)
        if fn_match:
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS005",
                language="rust", severity="error",
                message=f"Function '{fn_match.group(1)}' should use snake_case",
                snippet=stripped[:60],
            ))
        # Variables: snake_case
        var_match = re.match(r'let\s+mut\s+([A-Z]\w*)', stripped)
        if var_match:
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="RS005",
                language="rust", severity="error",
                message=f"Variable '{var_match.group(1)}' should use snake_case",
                snippet=stripped[:60],
            ))
    return violations


RUST_RULES: List[LintRule] = [
    LintRule("RS001", "rust", "error", "No .unwrap() in production code", _rs_no_unwrap),
    LintRule("RS002", "rust", "warning", "Use Option/Result properly (no is_some().unwrap())",
             _rs_option_result),
    LintRule("RS003", "rust", "error", "No mutable statics", _rs_no_mutable_statics),
    LintRule("RS004", "rust", "info", "Lint suppressions should be avoided", _rs_no_clippy_deny),
    LintRule("RS005", "rust", "error", "Naming conventions (snake_case functions/vars)",
             _rs_naming),
]


# ──────────────────────────────────────────────────────────────────────
# Java rules (Google style)
# ──────────────────────────────────────────────────────────────────────

def _java_indentation(filepath: str, content: str) -> List[LintViolation]:
    """JA001: 4-space indentation."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        if not line or line.strip() == "" or line.strip().startswith("//"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent > 0:
            if line.startswith("\t"):
                violations.append(LintViolation(
                    file=filepath, line=i, col=1, rule_id="JA001",
                    language="java", severity="error",
                    message="Google style requires 4-space indentation (found tab)",
                ))
            elif indent % 4 != 0:
                violations.append(LintViolation(
                    file=filepath, line=i, col=1, rule_id="JA001",
                    language="java", severity="warning",
                    message=f"Indentation not a multiple of 4 (found {indent} spaces)",
                ))
    return violations


def _java_javadoc_public(filepath: str, content: str) -> List[LintViolation]:
    """JA002: Public methods should have Javadoc."""
    violations = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'public\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(', stripped):
            has_doc = False
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            if j >= 0 and lines[j].strip().startswith("/**"):
                has_doc = True
            if not has_doc:
                if "main(" in stripped or "@Override" in lines[max(0, i - 1)].strip():
                    continue
                violations.append(LintViolation(
                    file=filepath, line=i + 1, rule_id="JA002",
                    language="java", severity="warning",
                    message=f"Public method should have Javadoc",
                    snippet=stripped[:80],
                ))
    return violations


def _java_no_wildcard_imports(filepath: str, content: str) -> List[LintViolation]:
    """JA003: No wildcard imports."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r'import\s+[\w.]+\.\*', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JA003",
                language="java", severity="error",
                message="Wildcard import detected — import specific classes",
                snippet=stripped,
            ))
    return violations


def _java_braces(filepath: str, content: str) -> List[LintViolation]:
    """JA004: Braces required for all control statements (Google style)."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if re.search(r'\b(?:if|for|while)\s*\([^)]*\)\s*[^{]', stripped):
            if not re.search(r'\b(?:if|for|while)\s*\([^)]*\)\s*(?:return|break|continue|throw)\b', stripped):
                violations.append(LintViolation(
                    file=filepath, line=i, rule_id="JA004",
                    language="java", severity="error",
                    message="Braces required for control statements",
                    snippet=stripped[:80],
                ))
    return violations


def _java_catch_specific(filepath: str, content: str) -> List[LintViolation]:
    """JA005: Catch specific exceptions, not Exception or Throwable."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.search(r'catch\s*\(\s*(?:Exception|Throwable)\s+\w+\s*\)', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JA005",
                language="java", severity="warning",
                message="Catch specific exceptions, not Exception/Throwable",
                snippet=stripped[:80],
            ))
    return violations


def _java_no_system_out(filepath: str, content: str) -> List[LintViolation]:
    """JA006: Avoid System.out.print — use a logger."""
    violations = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if re.search(r'System\.out\.(print|println)\s*\(', stripped):
            violations.append(LintViolation(
                file=filepath, line=i, rule_id="JA006",
                language="java", severity="info",
                message="Avoid System.out.print — use a logging framework",
                snippet=stripped[:80],
            ))
    return violations


JAVA_RULES: List[LintRule] = [
    LintRule("JA001", "java", "error", "4-space indentation (no tabs)", _java_indentation),
    LintRule("JA002", "java", "warning", "Javadoc on public methods", _java_javadoc_public),
    LintRule("JA003", "java", "error", "No wildcard imports", _java_no_wildcard_imports),
    LintRule("JA004", "java", "error", "Braces required for control statements", _java_braces),
    LintRule("JA005", "java", "warning", "Catch specific exceptions", _java_catch_specific),
    LintRule("JA006", "java", "info", "Use logger instead of System.out.print", _java_no_system_out),
]


# ──────────────────────────────────────────────────────────────────────
# Master rule registry
# ──────────────────────────────────────────────────────────────────────

ALL_RULES: Dict[str, List[LintRule]] = {
    "python": PYTHON_RULES,
    "javascript": JS_RULES,
    "typescript": JS_RULES,
    "go": GO_RULES,
    "rust": RUST_RULES,
    "java": JAVA_RULES,
}

RULE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {}
for lang, rules in ALL_RULES.items():
    for rule in rules:
        RULE_DESCRIPTIONS[rule.rule_id] = {
            "language": rule.language,
            "severity": rule.severity,
            "description": rule.description,
        }


# ──────────────────────────────────────────────────────────────────────
# Lint engine
# ──────────────────────────────────────────────────────────────────────

def detect_language(filepath: str) -> Optional[str]:
    """Detect language from file extension."""
    _, ext = os.path.splitext(filepath)
    return LANGUAGE_EXTENSIONS.get(ext.lower())


def lint_file(filepath: str, languages: Optional[List[str]] = None) -> List[LintViolation]:
    """Lint a single file using all applicable rules."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (IOError, OSError):
        return []

    if not content.strip():
        return []

    lang = None
    if languages:
        lang = detect_language(filepath)
        if lang not in languages and lang not in LANGUAGE_ALIASES:
            return []
    else:
        lang = detect_language(filepath)

    if not lang:
        return []

    effective_lang = LANGUAGE_ALIASES.get(lang, lang)
    rules = ALL_RULES.get(effective_lang, [])

    violations = []
    for rule in rules:
        try:
            found = rule.check(filepath, content)
            violations.extend(found)
        except Exception:
            continue

    return violations


def lint_project(
    project_path: str,
    languages: Optional[List[str]] = None,
    severity_filter: Optional[List[str]] = None,
    max_violations: int = 500,
    include_rule_ids: Optional[List[str]] = None,
    exclude_rule_ids: Optional[List[str]] = None,
) -> List[LintViolation]:
    """Lint an entire project directory."""
    SKIP_DIRS = {
        "node_modules", "__pycache__", ".git", "vendor", "build", "dist",
        ".venv", "venv", "target", ".tox", ".next", ".nuxt", "coverage",
        ".idea", ".vscode", ".gradle", ".mvn", "bin", "obj",
    }

    violations = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            lang = detect_language(filepath)
            if not lang:
                continue
            if languages and lang not in languages:
                continue

            file_violations = lint_file(filepath, languages)
            for v in file_violations:
                if severity_filter and v.severity not in severity_filter:
                    continue
                if include_rule_ids and v.rule_id not in include_rule_ids:
                    continue
                if exclude_rule_ids and v.rule_id in exclude_rule_ids:
                    continue
                violations.append(v)
                if len(violations) >= max_violations:
                    return violations

    return violations


def format_summary(violations: List[LintViolation]) -> str:
    """Format a summary of lint violations."""
    if not violations:
        return "  ✅ No lint violations found!"

    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    infos = sum(1 for v in violations if v.severity == "info")

    by_lang: Dict[str, int] = {}
    by_rule: Dict[str, int] = {}
    for v in violations:
        by_lang[v.language] = by_lang.get(v.language, 0) + 1
        by_rule[v.rule_id] = by_rule.get(v.rule_id, 0) + 1

    lines = [
        "",
        f"  📋 Lint Summary: {len(violations)} violations",
        f"     🔴 Errors:   {errors}",
        f"     🟡 Warnings: {warnings}",
        f"     🔵 Info:     {infos}",
        "",
        "  By language:",
    ]
    for lang, count in sorted(by_lang.items(), key=lambda x: -x[1]):
        lines.append(f"    {lang:<15} {count:>5}")
    lines.append("")
    lines.append("  Top rules:")
    for rule_id, count in sorted(by_rule.items(), key=lambda x: -x[1])[:10]:
        desc = RULE_DESCRIPTIONS.get(rule_id, {}).get("description", "")
        lines.append(f"    {rule_id:<8} {count:>4}×  {desc}")

    return "\n".join(lines)


def format_violations_terminal(violations: List[LintViolation]) -> str:
    """Format violations for terminal output."""
    if not violations:
        return "✅ No lint violations found!"
    parts = ["", "🔍 Lint Results", "─" * 60]
    for v in violations:
        parts.append(str(v))
    parts.append(format_summary(violations))
    return "\n".join(parts)


def format_violations_json(violations: List[LintViolation]) -> str:
    """Format violations as JSON."""
    import json
    data = [
        {
            "file": v.file, "line": v.line, "col": v.col,
            "rule_id": v.rule_id, "language": v.language,
            "severity": v.severity, "message": v.message,
            "snippet": v.snippet,
        }
        for v in violations
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)


def get_rules_for_language(language: str) -> List[LintRule]:
    """Get all rules for a given language."""
    effective = LANGUAGE_ALIASES.get(language, language)
    return ALL_RULES.get(effective, [])


def list_all_rules() -> str:
    """List all available rules in a formatted string."""
    lines = ["", "📋 Available Lint Rules", "=" * 70]
    for lang, rules in ALL_RULES.items():
        lines.append(f"\n  📌 {lang.upper()}")
        lines.append(f"  {'─' * (len(lang) + 2)}")
        for rule in rules:
            sev = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(rule.severity, "⚪")
            lines.append(f"    {sev} {rule.rule_id:<8} {rule.description}")
    return "\n".join(lines)