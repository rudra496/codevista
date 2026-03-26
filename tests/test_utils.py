"""Tests for utils module."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.utils import (
    discover_files, read_file_safe, compute_file_hash,
    normalize_for_duplication, block_hash, detect_functions,
    extract_todos, detect_quality_issues, find_duplicate_strings,
    cognitive_complexity, normalize_import, is_stdlib_import,
)


class TestFileDiscovery:
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = discover_files(tmpdir)
            assert files == []

    def test_finds_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'a.py'), 'w') as f:
                f.write('x=1')
            files = discover_files(tmpdir)
            assert len(files) == 1

    def test_ignores_hidden(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, '.hidden.py'), 'w') as f:
                f.write('x=1')
            with open(os.path.join(tmpdir, 'visible.py'), 'w') as f:
                f.write('x=1')
            files = discover_files(tmpdir)
            assert len(files) == 1

    def test_ignores_vendor_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'node_modules', 'pkg'))
            with open(os.path.join(tmpdir, 'node_modules', 'pkg', 'index.js'), 'w') as f:
                f.write('x=1')
            with open(os.path.join(tmpdir, 'app.py'), 'w') as f:
                f.write('x=1')
            files = discover_files(tmpdir)
            assert len(files) == 1

    def test_max_depth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'a', 'b', 'c'))
            with open(os.path.join(tmpdir, 'a', 'b', 'c', 'd.py'), 'w') as f:
                f.write('x=1')
            with open(os.path.join(tmpdir, 'top.py'), 'w') as f:
                f.write('x=1')
            files = discover_files(tmpdir, max_depth=1)
            assert len(files) == 1

    def test_binary_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'image.png'), 'wb') as f:
                f.write(b'\x89PNG\x00\x00\x00')
            with open(os.path.join(tmpdir, 'code.py'), 'w') as f:
                f.write('x=1')
            files = discover_files(tmpdir)
            assert len(files) == 1


class TestReadFileSafe:
    def test_utf8(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('hello world')
            path = f.name
        assert read_file_safe(path) == 'hello world'
        os.unlink(path)

    def test_missing_file(self):
        assert read_file_safe('/nonexistent/path/file.txt') == ''


class TestHashing:
    def test_deterministic(self):
        assert compute_file_hash('hello') == compute_file_hash('hello')

    def test_different_content(self):
        assert compute_file_hash('hello') != compute_file_hash('world')

    def test_normalize_removes_comments(self):
        result = normalize_for_duplication('# comment\ncode\n')
        assert 'comment' not in result

    def test_block_hash(self):
        blocks = block_hash('line1\nline2\nline3\nline4\nline5\nline6\n', block_size=3)
        assert isinstance(blocks, list)


class TestFunctionDetection:
    def test_python_function(self):
        code = "def foo(x, y):\n    return x + y\n"
        funcs = detect_functions(code, 'Python')
        assert len(funcs) == 1
        assert funcs[0]['name'] == 'foo'
        assert funcs[0]['param_count'] == 2

    def test_async_function(self):
        code = "async def fetch():\n    pass\n"
        funcs = detect_functions(code, 'Python')
        assert len(funcs) == 1
        assert funcs[0]['name'] == 'fetch'

    def test_multiple_functions(self):
        code = "def a():\n    pass\ndef b(x):\n    return x\n"
        funcs = detect_functions(code, 'Python')
        assert len(funcs) == 2

    def test_javascript_function(self):
        code = "function hello(name) {\n  return name;\n}\n"
        funcs = detect_functions(code, 'JavaScript')
        assert len(funcs) >= 1


class TestTodoExtraction:
    def test_todo(self):
        code = "# TODO: fix this later\nx = 1\n"
        todos = extract_todos(code)
        assert len(todos) == 1
        assert todos[0]['tag'] == 'TODO'

    def test_fixme(self):
        code = "# FIXME: broken\n"
        todos = extract_todos(code)
        assert len(todos) == 1
        assert todos[0]['tag'] == 'FIXME'

    def test_hack(self):
        code = "# HACK: workaround\n"
        todos = extract_todos(code)
        assert len(todos) == 1

    def test_no_todos(self):
        code = "x = 1\ny = 2\n"
        todos = extract_todos(code)
        assert len(todos) == 0


class TestQualityIssues:
    def test_long_line(self):
        code = "x" * 150 + "\n"
        issues = detect_quality_issues(code, 'Python', 'test.py')
        assert any(i['type'] in ('long_line', 'very_long_line') for i in issues)

    def test_trailing_whitespace(self):
        code = "x = 1   \n"
        issues = detect_quality_issues(code, 'Python', 'test.py')
        assert any(i['type'] == 'trailing_whitespace' for i in issues)

    def test_star_import(self):
        code = "from os import *\n"
        issues = detect_quality_issues(code, 'Python', 'test.py')
        assert any(i['type'] == 'star_import' for i in issues)

    def test_bare_except(self):
        code = "try:\n    x()\nexcept:\n    pass\n"
        issues = detect_quality_issues(code, 'Python', 'test.py')
        assert any(i['type'] == 'bare_except' for i in issues)

    def test_mutable_default(self):
        code = "def foo(items=[]):\n    pass\n"
        issues = detect_quality_issues(code, 'Python', 'test.py')
        assert any(i['type'] == 'mutable_default' for i in issues)


class TestDuplicateStrings:
    def test_duplicate_found(self):
        code = 'x = "some long string that repeats"\ny = "some long string that repeats"\nz = "some long string that repeats"\n'
        dups = find_duplicate_strings(code, min_length=20, min_occurrences=3)
        assert len(dups) > 0

    def test_no_duplicates(self):
        code = 'x = "unique string one"\ny = "unique string two"\n'
        dups = find_duplicate_strings(code, min_length=10, min_occurrences=3)
        assert len(dups) == 0


class TestCognitiveComplexity:
    def test_empty(self):
        assert cognitive_complexity('', 'Python') == 0

    def test_simple(self):
        assert cognitive_complexity('def f():\n    return 1\n', 'Python') >= 0

    def test_nested_higher(self):
        flat = "def f():\n    if x:\n        pass\n"
        nested = "def f():\n    if x:\n        if y:\n            pass\n"
        assert cognitive_complexity(nested, 'Python') > cognitive_complexity(flat, 'Python')


class TestImportHelpers:
    def test_normalize(self):
        assert normalize_import('os.path') == 'os'
        assert normalize_import('django.db.models') == 'django'

    def test_stdlib_detection(self):
        assert is_stdlib_import('os', 'Python') == True
        assert is_stdlib_import('django', 'Python') == False
        assert is_stdlib_import('fs', 'JavaScript') == True


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
