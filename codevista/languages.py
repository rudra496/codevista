"""Language definitions, GitHub-compatible colors, and comment syntax database.

Covers 90+ file extensions with comment styles, shebang mappings,
language categories, and GitHub linguist-style colors.
"""

from typing import Dict, List, Optional, Tuple

# ── Extension → Language mapping (90+) ──────────────────────────────────────

LANG_MAP: Dict[str, str] = {
    # Python
    '.py': 'Python', '.pyw': 'Python', '.pyx': 'Cython', '.pxd': 'Cython',
    '.pyi': 'Python', '.pip': 'Python',
    # JavaScript / TypeScript
    '.js': 'JavaScript', '.jsx': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript', '.mts': 'TypeScript', '.cts': 'TypeScript',
    # Web
    '.html': 'HTML', '.htm': 'HTML', '.xhtml': 'HTML', '.vue': 'Vue',
    '.svelte': 'Svelte', '.css': 'CSS', '.scss': 'SCSS', '.sass': 'SCSS',
    '.less': 'Less', '.pcss': 'PostCSS',
    # Compiled languages
    '.rb': 'Ruby', '.rake': 'Ruby', '.erb': 'ERB', '.gemspec': 'Ruby',
    '.go': 'Go',
    '.rs': 'Rust',
    '.java': 'Java',
    '.kt': 'Kotlin', '.kts': 'Kotlin',
    '.scala': 'Scala',
    '.swift': 'Swift',
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++', '.hpp': 'C++', '.hxx': 'C++',
    '.h++': 'C++',
    '.cs': 'C#', '.csx': 'C#',
    '.php': 'PHP', '.phtml': 'PHP',
    '.dart': 'Dart',
    '.ex': 'Elixir', '.exs': 'Elixir',
    '.erl': 'Erlang', '.hrl': 'Erlang',
    '.hs': 'Haskell', '.lhs': 'Haskell',
    '.ml': 'OCaml', '.mli': 'OCaml',
    '.clj': 'Clojure', '.cljs': 'Clojure', '.cljc': 'Clojure',
    '.pl': 'Perl', '.pm': 'Perl',
    '.lua': 'Lua',
    '.r': 'R', '.R': 'R',
    '.m': 'Objective-C', '.mm': 'Objective-C++',
    '.zig': 'Zig',
    '.nim': 'Nim',
    '.v': 'V',
    '.jl': 'Julia',
    '.pas': 'Pascal', '.pp': 'Pascal', '.dpr': 'Pascal',
    '.d': 'D',
    '.ada': 'Ada', '.adb': 'Ada', '.ads': 'Ada',
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran', '.f03': 'Fortran',
    '.sol': 'Solidity',
    '.tf': 'HCL', '.tfvars': 'HCL',
    # Data / Config
    '.json': 'JSON', '.jsonl': 'JSON', '.json5': 'JSON',
    '.xml': 'XML', '.xsl': 'XML', '.xslt': 'XML', '.xsd': 'XML',
    '.yaml': 'YAML', '.yml': 'YAML',
    '.toml': 'TOML',
    '.ini': 'INI', '.cfg': 'INI', '.conf': 'INI', '.env': 'INI',
    '.properties': 'INI',
    '.csv': 'CSV', '.tsv': 'CSV',
    '.lock': 'Lockfile',
    '.txt': 'Text',
    # Shell
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell', '.fish': 'Shell',
    '.ps1': 'PowerShell', '.psm1': 'PowerShell',
    '.bat': 'Batch', '.cmd': 'Batch',
    # Database
    '.sql': 'SQL', '.prql': 'PRQL',
    # Docs
    '.md': 'Markdown', '.mdx': 'Markdown', '.rst': 'reStructuredText',
    '.adoc': 'AsciiDoc', '.asciidoc': 'AsciiDoc',
    # Protocols
    '.proto': 'Protocol Buffers', '.graphql': 'GraphQL', '.gql': 'GraphQL',
    # Build
    '.cmake': 'CMake', '.gradle': 'Gradle', '.gradle.kts': 'Gradle',
    '.makefile': 'Makefile',
    # Misc
    '.vim': 'Vim script', '.emacs': 'Emacs Lisp', '.el': 'Emacs Lisp',
    '.dockerfile': 'Dockerfile',
}

# ── GitHub-inspired language colors ──────────────────────────────────────────

LANG_COLORS: Dict[str, str] = {
    'Python': '#3572A5', 'JavaScript': '#f1e05a', 'TypeScript': '#3178c6',
    'Ruby': '#701516', 'Go': '#00ADD8', 'Rust': '#dea584', 'Java': '#b07219',
    'Kotlin': '#A97BFF', 'Swift': '#F05138', 'C': '#555555', 'C++': '#f34b7d',
    'C#': '#178600', 'PHP': '#4F5D95', 'HTML': '#e34c26', 'CSS': '#563d7c',
    'SCSS': '#c6538c', 'Less': '#1d365d', 'PostCSS': '#563d7c',
    'JSON': '#292929', 'YAML': '#cb171e', 'TOML': '#9c4221',
    'Markdown': '#083fa1', 'Shell': '#89e051', 'PowerShell': '#012456',
    'Batch': '#C1F12E', 'SQL': '#e38c00', 'R': '#198CE7', 'Lua': '#000080',
    'Dart': '#00B4AB', 'Elixir': '#6e4a7e', 'Erlang': '#B83998',
    'Haskell': '#5e5086', 'Vue': '#41b883', 'Svelte': '#ff3e00',
    'Dockerfile': '#384d54', 'GraphQL': '#e535ab',
    'Makefile': '#427819', 'CMake': '#064f8c', 'Gradle': '#00592C',
    'Text': '#999999', 'CSV': '#89e051', 'INI': '#6d8086',
    'XML': '#0060ac', 'Protocol Buffers': '#7B4F9C',
    'Clojure': '#db5855', 'Perl': '#0298c3', 'OCaml': '#3be133',
    'Scala': '#c22d40', 'Objective-C': '#438eff', 'Objective-C++': '#6866FB',
    'Zig': '#ec915c', 'Nim': '#FFE953', 'V': '#4d79ff', 'Julia': '#a270ba',
    'Pascal': '#003838', 'D': '#ba595e', 'Ada': '#02f88c', 'Fortran': '#4d41b1',
    'Solidity': '#AA6746', 'HCL': '#844FBA', 'PRQL': '#0e40b5',
    'reStructuredText': '#14140D', 'AsciiDoc': '#73b00e',
    'Vim script': '#199f4b', 'Emacs Lisp': '#c065db',
    'ERB': '#701516', 'Lockfile': '#666666', 'Cython': '#fedf5b',
    'PostCSS': '#563d7c',
}

# ── Language categories ──────────────────────────────────────────────────────

PROGRAMMING = {
    'Python', 'JavaScript', 'TypeScript', 'Ruby', 'Go', 'Rust', 'Java',
    'Kotlin', 'Swift', 'C', 'C++', 'C#', 'PHP', 'Dart', 'Elixir', 'Erlang',
    'Haskell', 'Lua', 'R', 'Objective-C', 'Objective-C++', 'Zig', 'Nim', 'V',
    'Julia', 'Pascal', 'D', 'Ada', 'Fortran', 'Solidity', 'Perl', 'OCaml',
    'Scala', 'Clojure', 'Shell', 'PowerShell', 'Batch', 'Cython',
}

MARKUP = {'HTML', 'Markdown', 'reStructuredText', 'AsciiDoc', 'XML', 'Vue', 'Svelte', 'ERB'}

DATA = {'JSON', 'YAML', 'TOML', 'CSV', 'INI', 'SQL', 'PRQL', 'Lockfile'}

CONFIG = {'HCL', 'Protocol Buffers', 'GraphQL', 'Makefile', 'CMake', 'Gradle',
          'Dockerfile', 'Vim script', 'Emacs Lisp'}

def get_category(lang: str) -> str:
    """Return language category: programming, markup, data, config."""
    if lang in PROGRAMMING:
        return 'programming'
    if lang in MARKUP:
        return 'markup'
    if lang in DATA:
        return 'data'
    if lang in CONFIG:
        return 'config'
    return 'other'

# ── Comment syntax per language (for comment extraction) ────────────────────
# Each entry: (line_comment_prefixes, block_comment_open, block_comment_close)

COMMENT_SYNTAX: Dict[str, Tuple[List[str], Optional[str], Optional[str]]] = {
    'Python':    (['#'],            None,                      None),
    'Cython':    (['#'],            None,                      None),
    'Ruby':      (['#'],            None,                      None),
    'Perl':      (['#'],            None,                      None),
    'R':         (['#'],            None,                      None),
    'Lua':       (['--'],           None,                      None),
    'Elixir':    (['#'],            None,                      None),
    'Erlang':    (['%'],            None,                      None),
    'Haskell':   (['--'],           '{-',                      '-}'),
    'Vim script':(['"'],            None,                      None),
    'Fortran':   (['!', 'c', 'C'],  None,                      None),
    'Pascal':    (None,             '{',                       '}'),
    'Ada':       (['--'],           None,                      None),
    'SQL':       (['--'],           '/*',                      '*/'),
    'PRQL':      (['#'],            None,                      None),
    'Shell':     (['#'],            None,                      None),
    'PowerShell':(['#'],            '<#',                      '#>'),
    'Batch':     (['REM ', 'rem ', '::'], None,               None),
    'C':         (['//'],           '/*',                      '*/'),
    'C++':       (['//'],           '/*',                      '*/'),
    'Java':      (['//'],           '/*',                      '*/'),
    'Kotlin':    (['//'],           '/*',                      '*/'),
    'Swift':     (['//'],           '/*',                      '*/'),
    'Go':        (['//'],           '/*',                      '*/'),
    'Rust':      (['//'],           '/*',                      '*/'),
    'JavaScript': (['//'],          '/*',                      '*/'),
    'TypeScript': (['//'],          '/*',                      '*/'),
    'C#':        (['//'],           '/*',                      '*/'),
    'Dart':      (['//'],           '/*',                      '*/'),
    'PHP':       (['//', '#'],      '/*',                      '*/'),
    'Scala':     (['//'],           '/*',                      '*/'),
    'Clojure':   ([';', ';;'],      None,                      None),
    'Objective-C': (['//'],         '/*',                      '*/'),
    'Zig':       (['//'],           None,                      None),
    'Nim':       (['#'],            None,                      None),
    'V':         (['//'],           None,                      None),
    'Julia':     (['#'],            '#=',                      '=#'),
    'Solidity':  (['//'],           '/*',                      '*/'),
    'D':         (['//'],           '/*',                      '*/'),
    'HTML':      (None,             '<!--',                    '-->'),
    'XML':       (None,             '<!--',                    '-->'),
    'Markdown':  (['<!--'],         '<!--',                    '-->'),
    'CSS':       (None,             '/*',                      '*/'),
    'SCSS':      (['//'],           '/*',                      '*/'),
    'Less':      (['//'],           '/*',                      '*/'),
    'JSON':      (None,             None,                      None),
    'YAML':      (['#'],            None,                      None),
    'TOML':      (['#'],            None,                      None),
    'INI':       (['#', ';'],       None,                      None),
    'Vue':       (None,             '<!--',                    '-->'),
    'Svelte':    (None,             '<!--',                    '-->'),
    'ERB':       (['<%#'],          None,                      None),
}

# ── Shebang → language mapping ───────────────────────────────────────────────

SHEBANG_MAP: Dict[str, str] = {
    'python': 'Python', 'python3': 'Python', 'python2': 'Python',
    'bash': 'Shell', 'sh': 'Shell', 'zsh': 'Shell', 'fish': 'Shell',
    'node': 'JavaScript', 'deno': 'TypeScript',
    'ruby': 'Ruby', 'perl': 'Perl', 'php': 'PHP',
    'lua': 'Lua', 'Rscript': 'R',
    'swift': 'Swift', 'dart': 'Dart', 'go': 'Go',
    'pwsh': 'PowerShell', 'powershell': 'PowerShell',
}

# ── Special filenames ────────────────────────────────────────────────────────

SPECIAL_FILES: Dict[str, str] = {
    'dockerfile': 'Dockerfile',
    'makefile': 'Makefile', 'gnumakefile': 'Makefile',
    'cmakelists.txt': 'CMake',
    'jenkinsfile': 'Groovy',
    '.gitignore': 'Config', '.dockerignore': 'Config', '.editorconfig': 'Config',
    '.prettierrc': 'JSON', '.eslintrc': 'JSON', '.babelrc': 'JSON',
    'tsconfig.json': 'TypeScript', 'vue.config.js': 'JavaScript',
    'next.config.js': 'JavaScript', 'next.config.mjs': 'JavaScript',
    'angular.json': 'TypeScript', 'svelte.config.js': 'JavaScript',
    'vite.config.ts': 'TypeScript', 'vite.config.js': 'JavaScript',
    'tailwind.config.js': 'JavaScript', 'tailwind.config.ts': 'TypeScript',
    'webpack.config.js': 'JavaScript', 'webpack.config.ts': 'TypeScript',
}

# ── Ignored extensions (binary / assets) ────────────────────────────────────

IGNORED_EXTENSIONS: set = {
    '.pyc', '.pyo', '.class', '.o', '.so', '.dll', '.dylib', '.a', '.lib',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.zst',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.wav', '.ogg',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    '.exe', '.msi', '.dmg', '.app', '.deb', '.rpm',
    '.sqlite', '.db', '.bak', '.woff', '.eot',
    '.wasm', '.nib', '.storyboard', '.xib', '.pbxproj',
    '.parquet', '.arrow', '.feather',
    '.pyd', '.so', '.node',
}


def detect_language(filepath: str, content: Optional[str] = None) -> Optional[str]:
    """Detect language from file extension, special filename, shebang, or modeline.

    Args:
        filepath: Path to the file.
        content: Optional file content for shebang/modeline detection.

    Returns:
        Language name or None if not detected.
    """
    import os
    name = os.path.basename(filepath).lower()

    # Special filenames first
    if name in SPECIAL_FILES:
        return SPECIAL_FILES[name]

    # Extension-based
    _, ext = os.path.splitext(filepath)
    lang = LANG_MAP.get(ext.lower())
    if lang:
        return lang

    # Shebang-based detection if content provided and no extension match
    if content and not ext:
        first_line = content.split('\n')[0].strip()
        if first_line.startswith('#!'):
            shebang = first_line[2:].strip()
            parts = shebang.split()
            if parts:
                interpreter = os.path.basename(parts[0])
                lang = SHEBANG_MAP.get(interpreter)
                if not lang and len(parts) > 1 and interpreter in ('env',):
                    lang = SHEBANG_MAP.get(os.path.basename(parts[1]))
                if lang:
                    return lang

    # Modeline detection (vim: set filetype=python)
    if content and not lang:
        for line in content.split('\n')[:5]:
            for pattern in [r'vim:\s*.*filetype=(\w+)', r'vi:\s*.*filetype=(\w+)',
                           r'vim:\s*.*ft=(\w+)', r'vi:\s*.*ft=(\w+)']:
                import re
                m = re.search(pattern, line)
                if m:
                    ft = m.group(1).lower()
                    ft_map = {
                        'python': 'Python', 'javascript': 'JavaScript', 'ruby': 'Ruby',
                        'bash': 'Shell', 'sh': 'Shell', 'html': 'HTML', 'css': 'CSS',
                        'java': 'Java', 'c': 'C', 'cpp': 'C++', 'go': 'Go',
                        'rust': 'Rust', 'php': 'PHP', 'lua': 'Lua', 'sql': 'SQL',
                        'yaml': 'YAML', 'json': 'JSON', 'xml': 'XML', 'toml': 'TOML',
                        'kotlin': 'Kotlin', 'swift': 'Swift', 'dart': 'Dart',
                        'typescript': 'TypeScript', 'scala': 'Scala', 'haskell': 'Haskell',
                        'perl': 'Perl', 'r': 'R', 'lua': 'Lua', 'zig': 'Zig',
                    }
                    if ft in ft_map:
                        return ft_map[ft]

    return None


def get_lang_color(lang: str) -> str:
    """Get GitHub-compatible color for a language."""
    return LANG_COLORS.get(lang, '#999999')


def get_comment_syntax(lang: str) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Get comment syntax for a language.

    Returns:
        (line_prefixes, block_open, block_close) tuple.
    """
    return COMMENT_SYNTAX.get(lang, (['#'], None, None))


def is_ignored_ext(filepath: str) -> bool:
    """Check if file has a binary/asset extension."""
    import os
    _, ext = os.path.splitext(filepath)
    return ext.lower() in IGNORED_EXTENSIONS


def group_languages_for_chart(languages: dict, top_n: int = 8) -> dict:
    """Group small languages into 'Other' for pie chart.

    Args:
        languages: {language: line_count} mapping.
        top_n: Number of top languages to keep separate.

    Returns:
        New dict with small languages merged into 'Other'.
    """
    if len(languages) <= top_n:
        return dict(languages)
    sorted_langs = sorted(languages.items(), key=lambda x: -x[1])
    result = dict(sorted_langs[:top_n])
    other_total = sum(v for _, v in sorted_langs[top_n:])
    if other_total > 0:
        result['Other'] = other_total
    return result
