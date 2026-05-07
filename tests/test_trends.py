"""Tests for trends module."""

import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.trends import (
    save_snapshot, load_snapshots, list_snapshots,
    compare_snapshots, format_trends_terminal,
    _compute_tech_debt_ratio, _trend_arrow, _get_nested,
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
        'functions': [
            {'complexity': 2, 'line_count': 10, 'nesting_depth': 1, 'param_count': 2},
        ],
        'duplicates': [],
        'todos': [],
        'circular_deps': [],
        'unused_imports': [],
        'quality_issues': [],
        'files': [],
        'git': None,
    }


class TestSnapshots:
    def test_save_and_load_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analysis = _make_analysis()
            path = save_snapshot(analysis, tmpdir)
            assert os.path.isfile(path)

            snaps = load_snapshots(tmpdir)
            assert len(snaps) >= 1
            assert snaps[0]['total_files'] == 5

    def test_snapshot_with_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analysis = _make_analysis()
            path = save_snapshot(analysis, tmpdir, label="v1.0")
            assert "v1.0" in path

            snaps = load_snapshots(tmpdir)
            assert snaps[0]['label'] == 'v1.0'

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_snapshot(_make_analysis(), tmpdir, label="first")
            save_snapshot(_make_analysis(), tmpdir, label="second")
            items = list_snapshots(tmpdir)
            assert len(items) >= 1

    def test_snapshot_scores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analysis = _make_analysis()
            path = save_snapshot(analysis, tmpdir)
            with open(path) as f:
                data = json.load(f)
            assert 'scores' in data
            assert 'overall' in data['scores']


class TestComparison:
    def test_compare_identical(self):
        snap_a = {'timestamp': '2026-01-01', 'scores': {'overall': 80},
                  'total_files': 5, 'avg_complexity': 3.0, 'max_complexity': 8,
                  'security_issues_count': 0, 'dependencies_count': 0,
                  'function_count': 10, 'duplicate_count': 0, 'todo_count': 0,
                  'circular_deps_count': 0, 'technical_debt_ratio': 0.1,
                  'total_lines': {'code': 100}, 'label': ''}
        snap_b = dict(snap_a)
        snap_b['timestamp'] = '2026-01-02'
        result = compare_snapshots(snap_a, snap_b)
        assert result['stable'] > 0

    def test_compare_improved(self):
        snap_a = {'timestamp': '2026-01-01', 'scores': {'overall': 50},
                  'total_files': 5, 'avg_complexity': 15.0, 'max_complexity': 30,
                  'security_issues_count': 5, 'dependencies_count': 10,
                  'function_count': 10, 'duplicate_count': 3, 'todo_count': 10,
                  'circular_deps_count': 1, 'technical_debt_ratio': 0.5,
                  'total_lines': {'code': 100}, 'label': ''}
        snap_b = {'timestamp': '2026-01-02', 'scores': {'overall': 80},
                  'total_files': 6, 'avg_complexity': 5.0, 'max_complexity': 10,
                  'security_issues_count': 0, 'dependencies_count': 5,
                  'function_count': 12, 'duplicate_count': 0, 'todo_count': 2,
                  'circular_deps_count': 0, 'technical_debt_ratio': 0.1,
                  'total_lines': {'code': 120}, 'label': ''}
        result = compare_snapshots(snap_a, snap_b)
        assert result['improved'] > 0


class TestFormatTrends:
    def test_no_snapshots(self):
        output = format_trends_terminal([])
        assert "No snapshots" in output

    def test_one_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_snapshot(_make_analysis(), tmpdir)
            snaps = load_snapshots(tmpdir)
            output = format_trends_terminal(snaps)
            assert "Health Score" in output


class TestHelpers:
    def test_trend_arrow_stable(self):
        arrow, label = _trend_arrow(0.1)
        assert label == 'stable'

    def test_trend_arrow_improving(self):
        arrow, label = _trend_arrow(5.0)
        assert label == 'improving'

    def test_trend_arrow_degrading(self):
        arrow, label = _trend_arrow(-5.0)
        assert label == 'degrading'

    def test_get_nested(self):
        data = {'a': {'b': {'c': 42}}}
        assert _get_nested(data, 'a.b.c') == 42
        assert _get_nested(data, 'a.b.x', 'default') == 'default'

    def test_tech_debt_ratio(self):
        analysis = _make_analysis()
        ratio = _compute_tech_debt_ratio(analysis, {'overall': 80})
        assert 0 <= ratio <= 1


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
