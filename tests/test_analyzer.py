"""Tests for analyzer module."""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.analyzer import analyze_project, detect_frameworks, quick_analyze
from codevista.utils import count_lines, cyclomatic_complexity, extract_imports
from codevista.languages import detect_language


class TestLanguageDetection:
    def test_python_extension(self):
        assert detect_language('test.py') == 'Python'

    def test_javascript_extension(self):
        assert detect_language('app.js') == 'JavaScript'

    def test_typescript_extension(self):
        assert detect_language('app.ts') == 'TypeScript'

    def test_html_extension(self):
        assert detect_language('index.html') == 'HTML'

    def test_css_extension(self):
        assert detect_language('style.css') == 'CSS'

    def test_rust_extension(self):
        assert detect_language('main.rs') == 'Rust'

    def test_go_extension(self):
        assert detect_language('main.go') == 'Go'

    def test_unknown_extension(self):
        assert detect_language('data.xyz123') is None

    def test_shebang_detection(self):
        assert detect_language('script', '#!/usr/bin/env python3\nprint(1)') == 'Python'

    def test_bash_shebang(self):
        assert detect_language('script', '#!/bin/bash\necho hi') == 'Shell'

    def test_makefile(self):
        assert detect_language('/path/to/Makefile') == 'Makefile'

    def test_dockerfile(self):
        assert detect_language('/path/to/Dockerfile') == 'Dockerfile'

    def test_vue_extension(self):
        assert detect_language('App.vue') == 'Vue'

    def test_svelte_extension(self):
        assert detect_language('App.svelte') == 'Svelte'

    def test_tsx_extension(self):
        assert detect_language('App.tsx') == 'TypeScript'

    def test_ruby_extension(self):
        assert detect_language('app.rb') == 'Ruby'

    def test_swift_extension(self):
        assert detect_language('main.swift') == 'Swift'

    def test_java_extension(self):
        assert detect_language('Main.java') == 'Java'

    def test_kotlin_extension(self):
        assert detect_language('Main.kt') == 'Kotlin'

    def test_c_extension(self):
        assert detect_language('main.c') == 'C'

    def test_cpp_extension(self):
        assert detect_language('main.cpp') == 'C++'


class TestLineCounting:
    def test_python_total_lines(self):
        code = "line1\nline2\nline3\n"
        result = count_lines(code, 'Python')
        assert result['total'] == 3

    def test_python_blank_lines(self):
        code = "line1\n\nline3\n"
        result = count_lines(code, 'Python')
        assert result['blank'] == 1

    def test_python_comment_lines(self):
        code = "line1\n# comment\nline3\n"
        result = count_lines(code, 'Python')
        assert result['comment'] == 1
        assert result['code'] == 2

    def test_empty_content(self):
        result = count_lines('', 'Python')
        assert result['total'] == 0
        assert result['code'] == 0

    def test_only_comments(self):
        code = "# one\n# two\n"
        result = count_lines(code, 'Python')
        assert result['comment'] == 2
        assert result['code'] == 0


class TestCyclomaticComplexity:
    def test_empty_content(self):
        assert cyclomatic_complexity('', 'Python') == 0

    def test_simple_function(self):
        code = "def foo():\n    return 1\n"
        result = cyclomatic_complexity(code, 'Python')
        assert result >= 1

    def test_if_increases_complexity(self):
        simple = "def foo():\n    return 1\n"
        with_if = "def foo():\n    if x:\n        return 1\n    return 0\n"
        assert cyclomatic_complexity(with_if, 'Python') > cyclomatic_complexity(simple, 'Python')

    def test_non_code_is_zero(self):
        assert cyclomatic_complexity('<html></html>', 'HTML') == 0
        assert cyclomatic_complexity('{ "key": "value" }', 'JSON') == 0


class TestImportExtraction:
    def test_python_imports(self):
        code = "import os\nfrom sys import path\nimport json\n"
        result = extract_imports(code, 'Python')
        assert 'os' in result
        assert 'sys' in result
        assert 'json' in result

    def test_javascript_imports(self):
        code = "import React from 'react'\nconst fs = require('fs')\n"
        result = extract_imports(code, 'JavaScript')
        assert len(result) >= 1

    def test_no_imports(self):
        result = extract_imports("x = 1\ny = 2\n", 'Python')
        assert len(result) == 0


class TestAnalyzeProject:
    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = analyze_project(tmpdir, include_git=False)
            assert result['total_files'] == 0
            assert result['total_lines']['code'] == 0

    def test_single_python_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, 'test.py')
            with open(fpath, 'w') as f:
                f.write("import os\n\ndef hello():\n    print('hello')\n")
            result = analyze_project(tmpdir, include_git=False)
            assert result['total_files'] == 1
            assert 'Python' in result['languages']

    def test_multiple_languages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'a.py'), 'w') as f:
                f.write('x = 1\n')
            with open(os.path.join(tmpdir, 'b.js'), 'w') as f:
                f.write('const x = 1;\n')
            result = analyze_project(tmpdir, include_git=False)
            assert result['total_files'] == 2
            assert 'Python' in result['languages']
            assert 'JavaScript' in result['languages']

    def test_hidden_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, '.hidden.py'), 'w') as f:
                f.write('x = 1\n')
            with open(os.path.join(tmpdir, 'visible.py'), 'w') as f:
                f.write('x = 1\n')
            result = analyze_project(tmpdir, include_git=False)
            assert result['total_files'] == 1

    def test_vendored_dirs_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'node_modules', 'pkg'))
            with open(os.path.join(tmpdir, 'node_modules', 'pkg', 'index.js'), 'w') as f:
                f.write('x=1')
            with open(os.path.join(tmpdir, 'app.py'), 'w') as f:
                f.write('x=1')
            result = analyze_project(tmpdir, include_git=False)
            assert result['total_files'] == 1


class TestFrameworkDetection:
    def test_no_framework(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_frameworks(tmpdir)
            assert isinstance(result, list)

    def test_django_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'requirements.txt'), 'w') as f:
                f.write('django==4.0\n')
            with open(os.path.join(tmpdir, 'manage.py'), 'w') as f:
                f.write('# manage')
            result = detect_frameworks(tmpdir)
            assert 'Django' in result


class TestQuickAnalyze:
    def test_quick_returns_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('x = 1\n')
            result = quick_analyze(tmpdir)
            assert 'total_files' in result
            assert 'languages' in result


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
