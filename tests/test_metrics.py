"""Tests for metrics module."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.metrics import (
    calculate_health, halstead_metrics, maintainability_index,
    coupling_metrics, cohesion_metric, get_trend, generate_recommendations,
)


class TestHealthScoring:
    def test_empty_project(self):
        analysis = {
            'total_lines': {'total': 0, 'code': 0, 'comment': 0, 'blank': 0},
            'avg_complexity': 0, 'max_complexity': 0,
            'duplicates': [], 'security_issues': [], 'circular_deps': [],
            'dependencies': [], 'unused_imports': [],
            'quality_issues': [], 'files': [], 'functions': [],
        }
        scores = calculate_health(analysis)
        assert 'overall' in scores
        assert 0 <= scores['overall'] <= 100
        assert 'readability' in scores
        assert 'complexity' in scores

    def test_high_complexity_lowers_scores(self):
        simple = {
            'total_lines': {'total': 100, 'code': 80, 'comment': 10, 'blank': 10},
            'avg_complexity': 2, 'max_complexity': 5,
            'duplicates': [], 'security_issues': [], 'circular_deps': [],
            'dependencies': [], 'unused_imports': [],
            'quality_issues': [], 'files': [], 'functions': [],
        }
        complex_proj = {
            'total_lines': {'total': 100, 'code': 80, 'comment': 10, 'blank': 10},
            'avg_complexity': 30, 'max_complexity': 50,
            'duplicates': [], 'security_issues': [], 'circular_deps': [],
            'dependencies': [], 'unused_imports': [],
            'quality_issues': [], 'files': [], 'functions': [],
        }
        scores_simple = calculate_health(simple)
        scores_complex = calculate_health(complex_proj)
        assert scores_simple['complexity'] > scores_complex['complexity']


class TestHalsteadMetrics:
    def test_empty_content(self):
        result = halstead_metrics('')
        assert result['volume'] == 0

    def test_simple_code(self):
        code = "def foo():\n    x = 1\n    return x\n"
        result = halstead_metrics(code, 'Python')
        assert result['N'] > 0
        assert result['volume'] > 0

    def test_operators_counted(self):
        code = "if x and y:\n    return z\n"
        result = halstead_metrics(code, 'Python')
        assert result['N1'] > 0  # operators counted


class TestMaintainabilityIndex:
    def test_perfect_score(self):
        mi = maintainability_index(100, 1, 100, 0.2)
        assert 0 <= mi <= 100

    def test_zero_loc(self):
        mi = maintainability_index(0, 0, 0, 0)
        assert mi == 100.0

    def test_low_volume_high_mi(self):
        mi_high = maintainability_index(10, 1, 50, 0.2)
        mi_low = maintainability_index(1000, 30, 500, 0.02)
        assert mi_high > mi_low


class TestCouplingMetrics:
    def test_empty_graph(self):
        result = coupling_metrics({}, {})
        assert result['instability'] == 0

    def test_simple_graph(self):
        graph = {'a': {'b'}, 'b': {'c'}, 'c': set()}
        result = coupling_metrics(graph, {})
        assert result['avg_fan_out'] > 0
        assert 0 <= result['instability'] <= 1


class TestCohesionMetric:
    def test_single_function(self):
        result = cohesion_metric("def foo():\n    return 1\n", 'Python')
        assert result == 0.0

    def test_unrelated_functions(self):
        code = "def foo():\n    x = 1\n    return x\ndef bar():\n    y = 'hello'\n    return y\n"
        result = cohesion_metric(code, 'Python')
        assert 0 <= result <= 1


class TestTrend:
    def test_good(self):
        assert get_trend(90) == 'good'

    def test_warning(self):
        assert get_trend(60) == 'warning'

    def test_critical(self):
        assert get_trend(20) == 'critical'


class TestRecommendations:
    def test_empty_issues(self):
        analysis = {
            'avg_complexity': 2, 'max_complexity': 3,
            'total_lines': {'total': 100, 'comment': 20, 'blank': 10},
            'duplicates': [], 'security_issues': [], 'circular_deps': [],
            'dependencies': [], 'todos': [], 'quality_issues': [],
            'files': [], 'functions': [],
        }
        scores = {'readability': 90, 'coverage': 80, 'maintainability': 85}
        recs = generate_recommendations(analysis, scores)
        assert len(recs) >= 0

    def test_security_recommendation(self):
        analysis = {
            'avg_complexity': 2, 'max_complexity': 3,
            'total_lines': {'total': 100, 'comment': 20, 'blank': 10},
            'duplicates': [], 'circular_deps': [],
            'security_issues': [{'severity': 'critical', 'count': 1}],
            'dependencies': [], 'todos': [], 'quality_issues': [],
            'files': [], 'functions': [],
        }
        scores = {'readability': 90, 'coverage': 80, 'maintainability': 85}
        recs = generate_recommendations(analysis, scores)
        assert any(r['category'] == 'Security' for r in recs)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
