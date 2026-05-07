"""Tests for integrations module."""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.integrations import (
    evaluate_thresholds, load_thresholds,
    generate_sarif, generate_gitlab_codequality,
    generate_checkstyle, generate_junit,
    generate_markdown_summary, generate_one_line_summary,
    output_ci, _parse_simple_yaml,
    EXIT_CLEAN, EXIT_WARNINGS, EXIT_ERRORS, EXIT_CRITICAL,
)


def _make_analysis():
    return {
        'total_files': 5,
        'total_lines': {'total': 100, 'code': 80, 'comment': 10, 'blank': 10},
        'avg_complexity': 3.0,
        'max_complexity': 8,
        'languages': {'Python': 80},
        'security_issues': [],
        'dependencies': [],
        'functions': [],
        'top_complex_functions': [],
        'duplicates': [],
        'todos': [],
        'circular_deps': [],
        'unused_imports': [],
        'quality_issues': [],
        'files': [],
    }


def _make_analysis_with_issues():
    return {
        'total_files': 5,
        'total_lines': {'total': 100, 'code': 80, 'comment': 10, 'blank': 10},
        'avg_complexity': 15.0,
        'max_complexity': 30,
        'languages': {'Python': 80},
        'security_issues': [
            {'severity': 'critical', 'name': 'AWS Key', 'file': 'app.py',
             'line': 1, 'type': 'hardcoded_secret', 'count': 1, 'category': 'secrets'},
        ],
        'dependencies': ['flask'],
        'functions': [],
        'top_complex_functions': [],
        'duplicates': [{'file_a': 'a.py', 'file_b': 'b.py'}],
        'todos': [],
        'circular_deps': [],
        'unused_imports': [],
        'quality_issues': [],
        'files': [],
    }


class TestThresholds:
    def test_default_thresholds(self):
        t = load_thresholds()
        assert t['max_security_critical'] == 0
        assert t['min_health_score'] == 60

    def test_clean_analysis(self):
        result = evaluate_thresholds(_make_analysis())
        assert result['passed'] is True
        assert result['exit_code'] == EXIT_CLEAN

    def test_critical_issues(self):
        result = evaluate_thresholds(_make_analysis_with_issues())
        assert result['exit_code'] == EXIT_CRITICAL

    def test_custom_thresholds(self):
        result = evaluate_thresholds(
            _make_analysis(),
            {'min_health_score': 95, 'max_security_critical': 10}
        )
        assert result['exit_code'] in (EXIT_ERRORS, EXIT_WARNINGS)


class TestSARIF:
    def test_generate_sarif(self):
        sarif = generate_sarif(_make_analysis_with_issues())
        assert sarif['version'] == '2.1.0'
        assert len(sarif['runs']) == 1
        assert len(sarif['runs'][0]['results']) > 0

    def test_sarif_empty(self):
        sarif = generate_sarif(_make_analysis())
        assert sarif['version'] == '2.1.0'


class TestGitLab:
    def test_generate_gitlab(self):
        findings = generate_gitlab_codequality(_make_analysis_with_issues())
        assert len(findings) > 0
        assert findings[0]['check_name'].startswith('codevista')

    def test_gitlab_empty(self):
        findings = generate_gitlab_codequality(_make_analysis())
        assert len(findings) == 0


class TestCheckstyle:
    def test_generate_checkstyle(self):
        xml = generate_checkstyle(_make_analysis_with_issues())
        assert '<checkstyle' in xml

    def test_checkstyle_empty(self):
        xml = generate_checkstyle(_make_analysis())
        assert 'checkstyle' in xml


class TestJUnit:
    def test_generate_junit(self):
        xml = generate_junit(_make_analysis())
        assert '<testsuites' in xml
        assert 'Health Score' in xml

    def test_junit_failures(self):
        xml = generate_junit(_make_analysis_with_issues())
        assert '<testsuites' in xml


class TestMarkdown:
    def test_generate_markdown(self):
        md = generate_markdown_summary(_make_analysis())
        assert 'CodeVista' in md
        assert 'Health Score' in md

    def test_markdown_with_issues(self):
        md = generate_markdown_summary(_make_analysis_with_issues())
        assert 'Security' in md


class TestOneLineSummary:
    def test_summary(self):
        summary = generate_one_line_summary(_make_analysis())
        assert 'Health:' in summary
        assert 'Files:' in summary


class TestYamlParser:
    def test_parse_simple(self):
        yaml_content = "min_health_score: 70\nmax_avg_complexity: 15\n"
        result = _parse_simple_yaml(yaml_content)
        assert result['min_health_score'] == 70
        assert result['max_avg_complexity'] == 15

    def test_parse_bool(self):
        result = _parse_simple_yaml("strict: true\n")
        assert result['strict'] is True

    def test_parse_empty(self):
        result = _parse_simple_yaml("")
        assert result == {}

    def test_parse_comments(self):
        result = _parse_simple_yaml("# comment\nkey: 42\n")
        assert result == {'key': 42}


class TestOutputCI:
    def test_sarif_output(self):
        content, exit_code = output_ci(_make_analysis(), 'sarif')
        assert len(content) > 0
        parsed = json.loads(content)
        assert parsed['version'] == '2.1.0'

    def test_terminal_output(self):
        content, exit_code = output_ci(_make_analysis(), 'terminal')
        assert 'Health:' in content

    def test_file_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outpath = os.path.join(tmpdir, 'result')
            content, exit_code = output_ci(
                _make_analysis(), 'sarif', output_path=outpath)
            assert os.path.isfile(outpath + '.sarif.json')


class TestExitCodes:
    def test_exit_codes_defined(self):
        assert EXIT_CLEAN == 0
        assert EXIT_WARNINGS == 1
        assert EXIT_ERRORS == 2
        assert EXIT_CRITICAL == 3


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
