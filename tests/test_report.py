"""Tests for report generation."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.report import generate_report, build_pie_svg, build_bar_svg


class TestReportGeneration:
    def test_basic_report(self):
        analysis = {
            'project_name': 'test-project',
            'total_files': 1,
            'total_lines': {'total': 10, 'code': 8, 'comment': 1, 'blank': 1},
            'languages': {'Python': 10},
            'language_files': {'Python': 1},
            'frameworks': [],
            'tech_stack': None,
            'avg_complexity': 2.0,
            'max_complexity': 3,
            'functions': [],
            'top_complex_functions': [],
            'complexity_distribution': {},
            'size_distribution': {},
            'todos': [],
            'quality_issues': [],
            'quality_issue_summary': {},
            'duplicate_strings': [],
            'duplicates': [],
            'security_issues': [],
            'circular_deps': [],
            'dependencies': [],
            'package_manager': None,
            'import_graph': {},
            'import_details': {},
            'unused_imports': [],
            'git': None,
            'dir_tree': {'test.py': {'lines': 10, 'language': 'Python', 'color': '#3572A5', 'size': 100, 'complexity': 2}},
            'files': [{
                'path': 'test.py', 'language': 'Python', 'color': '#3572A5',
                'lines': {'total': 10, 'code': 8, 'comment': 1, 'blank': 1},
                'complexity': 2, 'maintainability_index': 75,
                'size': 100, 'imports': [], 'import_count': 0,
                'function_count': 0, 'functions': [], 'todos': [],
                'quality_issues': [], 'comment_ratio': 0.1,
            }],
        }
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output = f.name
        try:
            html = generate_report(analysis, output)
            assert os.path.isfile(output)
            assert '<!DOCTYPE html>' in html
            assert 'test-project' in html
            assert len(html) > 1000
        finally:
            os.unlink(output)

    def test_report_with_security_issues(self):
        analysis = {
            'project_name': 'insecure',
            'total_files': 1, 'total_lines': {'total': 5, 'code': 5, 'comment': 0, 'blank': 0},
            'languages': {'Python': 5}, 'language_files': {'Python': 1},
            'frameworks': [], 'tech_stack': None,
            'avg_complexity': 1, 'max_complexity': 1,
            'functions': [], 'top_complex_functions': [],
            'complexity_distribution': {}, 'size_distribution': {},
            'todos': [], 'quality_issues': [], 'quality_issue_summary': {},
            'duplicate_strings': [], 'duplicates': [],
            'security_issues': [{'severity': 'critical', 'name': 'AWS Key', 'file': 'app.py', 'line': 1, 'count': 1, 'category': 'secrets'}],
            'circular_deps': [], 'dependencies': [], 'package_manager': None,
            'import_graph': {}, 'import_details': {}, 'unused_imports': [],
            'git': None, 'dir_tree': {},
            'files': [],
        }
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output = f.name
        try:
            html = generate_report(analysis, output)
            assert 'Security' in html
        finally:
            os.unlink(output)


class TestSVGCharts:
    def test_pie_svg(self):
        svg = build_pie_svg({'Python': 100, 'JavaScript': 50})
        assert '<svg' in svg
        assert 'Python' in svg

    def test_pie_empty(self):
        svg = build_pie_svg({})
        assert 'No languages' in svg

    def test_bar_svg(self):
        files = [{'path': 'a.py', 'lines': {'total': 100}, 'color': '#3572A5'}]
        svg = build_bar_svg(files)
        assert '<svg' in svg

    def test_bar_empty(self):
        svg = build_bar_svg([])
        assert svg == ''


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
