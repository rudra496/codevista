"""CI/CD integrations — output formats for various CI/CD platforms.

SARIF (GitHub Code Scanning), GitLab Code Quality, Checkstyle XML,
JUnit XML, Markdown summary, terminal one-line summary, exit codes,
and threshold configuration.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

# ── Exit Codes ──────────────────────────────────────────────────────────────

EXIT_CLEAN = 0       # No findings
EXIT_WARNINGS = 1    # Warnings only
EXIT_ERRORS = 2      # Errors found
EXIT_CRITICAL = 3    # Critical issues found


# ── Threshold Configuration ─────────────────────────────────────────────────

DEFAULT_THRESHOLDS = {
    'max_security_critical': 0,
    'max_security_high': 0,
    'max_security_medium': 5,
    'max_security_total': 10,
    'max_avg_complexity': 10,
    'max_complexity_hotspots': 3,
    'max_technical_debt_ratio': 0.25,
    'min_health_score': 60,
    'max_duplicates': 10,
    'max_circular_deps': 0,
    'max_todo_count': 50,
}


def load_thresholds(config_path: str = None) -> Dict[str, Any]:
    """Load threshold configuration from file or use defaults."""
    thresholds = dict(DEFAULT_THRESHOLDS)

    # Try .codevista.json / .codevista.yaml
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, 'r', errors='ignore') as f:
                content = f.read()
            if config_path.endswith('.json'):
                import json
                custom = json.loads(content)
            else:
                custom = _parse_simple_yaml(content)
            thresholds.update(custom)
        except (OSError, ValueError):
            pass
    else:
        for fname in ('.codevista.json', '.codevista.yaml', '.codevista.yml'):
            if os.path.isfile(fname):
                try:
                    with open(fname, 'r', errors='ignore') as f:
                        content = f.read()
                    if fname.endswith('.json'):
                        import json
                        custom = json.loads(content)
                    else:
                        custom = _parse_simple_yaml(content)
                    thresholds.update(custom)
                except (OSError, ValueError):
                    pass

    return thresholds


def evaluate_thresholds(analysis: Dict[str, Any],
                        thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    """Evaluate analysis against thresholds and return exit code + violations."""
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    from .metrics import calculate_health
    scores = calculate_health(analysis)

    violations = []
    max_severity = 'none'

    # Check security issues
    sec_issues = analysis.get('security_issues', [])
    sec_by_sev = Counter(i['severity'] for i in sec_issues)

    critical_count = sec_by_sev.get('critical', 0)
    high_count = sec_by_sev.get('high', 0)
    medium_count = sec_by_sev.get('medium', 0)
    total_sec = len(sec_issues)

    if critical_count > thresholds.get('max_security_critical', 0):
        violations.append({
            'rule': 'security_critical',
            'message': f'{critical_count} critical security issues (max {thresholds["max_security_critical"]})',
            'severity': 'critical',
        })
        max_severity = 'critical'

    if high_count > thresholds.get('max_security_high', 0):
        violations.append({
            'rule': 'security_high',
            'message': f'{high_count} high security issues (max {thresholds["max_security_high"]})',
            'severity': 'high',
        })
        max_severity = _max_severity(max_severity, 'high')

    if medium_count > thresholds.get('max_security_medium', 5):
        violations.append({
            'rule': 'security_medium',
            'message': f'{medium_count} medium security issues (max {thresholds["max_security_medium"]})',
            'severity': 'medium',
        })
        max_severity = _max_severity(max_severity, 'medium')

    if total_sec > thresholds.get('max_security_total', 10):
        violations.append({
            'rule': 'security_total',
            'message': f'{total_sec} total security issues (max {thresholds["max_security_total"]})',
            'severity': 'medium',
        })
        max_severity = _max_severity(max_severity, 'medium')

    # Check complexity
    avg_cc = analysis.get('avg_complexity', 0)
    max_cc_threshold = thresholds.get('max_avg_complexity', 10)
    if avg_cc > max_cc_threshold:
        violations.append({
            'rule': 'avg_complexity',
            'message': f'Average complexity {avg_cc:.1f} exceeds {max_cc_threshold}',
            'severity': 'error',
        })
        max_severity = _max_severity(max_severity, 'error')

    # Check health score
    min_health = thresholds.get('min_health_score', 60)
    overall = scores.get('overall', 100)
    if overall < min_health:
        violations.append({
            'rule': 'health_score',
            'message': f'Health score {overall} below minimum {min_health}',
            'severity': 'error',
        })
        max_severity = _max_severity(max_severity, 'error')

    # Check duplicates
    dup_count = len(analysis.get('duplicates', []))
    max_dup = thresholds.get('max_duplicates', 10)
    if dup_count > max_dup:
        violations.append({
            'rule': 'duplicates',
            'message': f'{dup_count} code duplicates (max {max_dup})',
            'severity': 'warning',
        })
        max_severity = _max_severity(max_severity, 'warning')

    # Check circular deps
    circ_count = len(analysis.get('circular_deps', []))
    max_circ = thresholds.get('max_circular_deps', 0)
    if circ_count > max_circ:
        violations.append({
            'rule': 'circular_deps',
            'message': f'{circ_count} circular dependencies (max {max_circ})',
            'severity': 'warning',
        })
        max_severity = _max_severity(max_severity, 'warning')

    # Determine exit code
    if max_severity == 'critical':
        exit_code = EXIT_CRITICAL
    elif max_severity in ('error', 'high'):
        exit_code = EXIT_ERRORS
    elif max_severity in ('warning', 'medium'):
        exit_code = EXIT_WARNINGS
    else:
        exit_code = EXIT_CLEAN

    return {
        'exit_code': exit_code,
        'max_severity': max_severity,
        'violations': violations,
        'scores': scores,
        'passed': exit_code == EXIT_CLEAN,
    }


# ── SARIF Output ────────────────────────────────────────────────────────────

def generate_sarif(analysis: Dict[str, Any],
                   thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate SARIF output for GitHub Code Scanning."""
    sarif = {
        '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
        'version': '2.1.0',
        'runs': [_build_sarif_run(analysis)],
    }
    return sarif


def _build_sarif_run(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Build a single SARIF run."""
    results = []

    # Security findings
    for issue in analysis.get('security_issues', []):
        rule_id = f"codevista.security.{issue.get('type', 'unknown')}"
        level = _sarif_level(issue.get('severity', 'medium'))

        result = {
            'ruleId': rule_id,
            'level': level,
            'message': {
                'text': issue.get('name', 'Security issue'),
            },
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'uri': issue.get('file', 'unknown'),
                    },
                    'region': {
                        'startLine': issue.get('line', 1),
                    },
                },
            }],
        }

        if issue.get('remediation'):
            result['message']['text'] += f"\n\nFix: {issue['remediation']}"

        results.append(result)

    # Complexity findings
    for func in analysis.get('top_complex_functions', []):
        if func.get('complexity', 0) > 15:
            results.append({
                'ruleId': 'codevista.complexity.high',
                'level': 'warning',
                'message': {
                    'text': f"Function '{func.get('name', '')}' has high cyclomatic complexity ({func.get('complexity', 0)})",
                },
                'locations': [{
                    'physicalLocation': {
                        'artifactLocation': {
                            'uri': func.get('file', 'unknown'),
                        },
                        'region': {
                            'startLine': func.get('start_line', 1),
                        },
                    },
                }],
            })

    # Quality issues (top ones)
    for qi in analysis.get('quality_issues', [])[:100]:
        if qi.get('type') in ('long_line', 'very_long_line'):
            results.append({
                'ruleId': f"codevista.quality.{qi.get('type', 'unknown')}",
                'level': 'note',
                'message': {
                    'text': qi.get('message', 'Quality issue'),
                },
                'locations': [{
                    'physicalLocation': {
                        'artifactLocation': {
                            'uri': qi.get('file', 'unknown'),
                        },
                        'region': {
                            'startLine': qi.get('line', 1),
                        },
                    },
                }],
            })

    # Build rules
    rules = _build_sarif_rules(results)

    return {
        'tool': {
            'driver': {
                'name': 'CodeVista',
                'version': '1.0.0',
                'informationUri': 'https://github.com/codevista/codevista',
                'rules': rules,
            },
        },
        'results': results,
    }


def _build_sarif_rules(results: list) -> list:
    """Build SARIF rules from results."""
    rule_map = {}
    rule_configs = {
        'codevista.security.hardcoded_secret': {
            'name': 'Hardcoded Secret',
            'shortDescription': {'text': 'Hardcoded secret detected'},
            'properties': {'category': 'security'},
        },
        'codevista.security.dangerous_function': {
            'name': 'Dangerous Function',
            'shortDescription': {'text': 'Use of dangerous function'},
            'properties': {'category': 'security'},
        },
        'codevista.security.private_key': {
            'name': 'Private Key',
            'shortDescription': {'text': 'Private key detected in source'},
            'properties': {'category': 'security'},
        },
        'codevista.complexity.high': {
            'name': 'High Complexity',
            'shortDescription': {'text': 'Function with high cyclomatic complexity'},
            'properties': {'category': 'complexity'},
        },
    }

    for r in results:
        rule_id = r.get('ruleId', '')
        if rule_id and rule_id not in rule_map:
            config = rule_configs.get(rule_id, {
                'name': rule_id.split('.')[-1].replace('_', ' ').title(),
                'shortDescription': {'text': r.get('message', {}).get('text', '')[:100]},
                'properties': {'category': 'general'},
            })
            config['id'] = rule_id
            rule_map[rule_id] = config

    return list(rule_map.values())


def _sarif_level(severity: str) -> str:
    """Convert CodeVista severity to SARIF level."""
    mapping = {
        'critical': 'error',
        'high': 'error',
        'medium': 'warning',
        'low': 'note',
    }
    return mapping.get(severity, 'warning')


# ── GitLab Code Quality Output ──────────────────────────────────────────────

def generate_gitlab_codequality(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate GitLab Code Quality JSON output."""
    findings = []

    # Security issues
    severity_map = {
        'critical': 'critical',
        'high': 'major',
        'medium': 'minor',
        'low': 'info',
    }

    for issue in analysis.get('security_issues', []):
        findings.append({
            'description': f"{issue.get('name', 'Security issue')} in {issue.get('file', '')}:{issue.get('line', 0)}",
            'check_name': f"codevista.security.{issue.get('type', 'unknown')}",
            'fingerprint': _gitlab_fingerprint(issue),
            'severity': severity_map.get(issue.get('severity', 'medium'), 'minor'),
            'location': {
                'path': issue.get('file', ''),
                'lines': {
                    'begin': issue.get('line', 1),
                },
            },
            'content': {
                'body': issue.get('remediation', ''),
            },
        })

    # Complexity findings
    for func in analysis.get('top_complex_functions', []):
        if func.get('complexity', 0) > 15:
            findings.append({
                'description': f"Function '{func.get('name', '')}' has complexity {func.get('complexity', 0)}",
                'check_name': 'codevista.complexity.high',
                'fingerprint': _gitlab_fingerprint(func),
                'severity': 'major',
                'location': {
                    'path': func.get('file', ''),
                    'lines': {
                        'begin': func.get('start_line', 1),
                    },
                },
            })

    return findings


def _gitlab_fingerprint(item: Dict) -> str:
    """Generate a deterministic fingerprint for GitLab Code Quality."""
    import hashlib
    key = f"{item.get('file', '')}:{item.get('line', 0)}:{item.get('type', item.get('name', ''))}"
    return hashlib.md5(key.encode()).hexdigest()


# ── Checkstyle XML Output ───────────────────────────────────────────────────

def generate_checkstyle(analysis: Dict[str, Any]) -> str:
    """Generate Checkstyle XML output."""
    root = ET.Element('checkstyle', version='8.0')

    # Group issues by file
    by_file = defaultdict(list)

    for issue in analysis.get('security_issues', []):
        by_file[issue.get('file', '')].append({
            'line': issue.get('line', 1),
            'severity': issue.get('severity', 'warning'),
            'message': issue.get('name', 'Security issue'),
            'source': f'codevista.security.{issue.get("type", "unknown")}',
        })

    for func in analysis.get('top_complex_functions', []):
        if func.get('complexity', 0) > 10:
            by_file[func.get('file', '')].append({
                'line': func.get('start_line', 1),
                'severity': 'warning' if func['complexity'] <= 15 else 'error',
                'message': f"Complexity {func['complexity']}",
                'source': 'codevista.complexity',
            })

    for qi in analysis.get('quality_issues', [])[:200]:
        sev = 'warning' if qi.get('type') in ('long_line',) else 'info'
        by_file[qi.get('file', '')].append({
            'line': qi.get('line', 1),
            'severity': sev,
            'message': qi.get('message', ''),
            'source': f'codevista.quality.{qi.get("type", "unknown")}',
        })

    for filepath, issues in sorted(by_file.items()):
        file_elem = ET.SubElement(root, 'file', name=filepath)
        for issue in issues:
            ET.SubElement(file_elem, 'error', {
                'line': str(issue['line']),
                'severity': issue['severity'],
                'message': issue['message'],
                'source': issue['source'],
            })

    # Pretty print
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent='  ', encoding=None)


# ── JUnit XML Output ────────────────────────────────────────────────────────

def generate_junit(analysis: Dict[str, Any],
                   thresholds: Dict[str, Any] = None) -> str:
    """Generate JUnit XML output for CI test results."""
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    threshold_result = evaluate_thresholds(analysis, thresholds)

    from .metrics import calculate_health
    scores = calculate_health(analysis)

    testsuites = ET.Element('testsuites')
    testsuite = ET.SubElement(testsuites, 'testsuite', {
        'name': 'CodeVista Analysis',
        'tests': '8',
        'failures': str(len(threshold_result['violations'])),
        'errors': '0',
        'time': '0',
    })

    # Health score test
    _add_junit_test(testsuite, 'Health Score', scores['overall'],
                    thresholds.get('min_health_score', 60),
                    f"Health score: {scores['overall']}/100 (min: {thresholds.get('min_health_score', 60)})")

    # Security test
    sec_count = len(analysis.get('security_issues', []))
    _add_junit_test(testsuite, 'Security Issues', sec_count,
                    0,  # want 0
                    f"Found {sec_count} security issues",
                    invert=True, max_allowed=thresholds.get('max_security_total', 10))

    # Complexity test
    _add_junit_test(testsuite, 'Average Complexity', analysis.get('avg_complexity', 0),
                    0,  # want low
                    f"Avg complexity: {analysis.get('avg_complexity', 0):.1f}",
                    invert=True, max_allowed=thresholds.get('max_avg_complexity', 10))

    # Duplication test
    _add_junit_test(testsuite, 'Code Duplication', len(analysis.get('duplicates', [])),
                    0,
                    f"Found {len(analysis.get('duplicates', []))} duplicates",
                    invert=True, max_allowed=thresholds.get('max_duplicates', 10))

    # Circular deps test
    _add_junit_test(testsuite, 'Circular Dependencies',
                    len(analysis.get('circular_deps', [])),
                    0,
                    f"Found {len(analysis.get('circular_deps', []))} circular deps",
                    invert=True, max_allowed=thresholds.get('max_circular_deps', 0))

    # Readability test
    _add_junit_test(testsuite, 'Readability Score', scores.get('readability', 100),
                    60,
                    f"Readability: {scores.get('readability', 0)}/100")

    # Maintainability test
    _add_junit_test(testsuite, 'Maintainability Score', scores.get('maintainability', 100),
                    50,
                    f"Maintainability: {scores.get('maintainability', 0)}/100")

    # Security score test
    _add_junit_test(testsuite, 'Security Score', scores.get('security', 100),
                    70,
                    f"Security: {scores.get('security', 0)}/100")

    xml_str = ET.tostring(testsuites, encoding='unicode')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent='  ', encoding=None)


def _add_junit_test(parent, name, value, threshold, message,
                    invert=False, max_allowed=None):
    """Add a JUnit testcase element."""
    passed = False
    if invert:
        passed = value <= (max_allowed if max_allowed is not None else threshold)
    else:
        passed = value >= threshold

    testcase = ET.SubElement(parent, 'testcase', {
        'name': name,
        'classname': 'CodeVista',
        'time': '0',
    })

    if not passed:
        failure = ET.SubElement(testcase, 'failure', {
            'message': f"FAILED: {message}",
            'type': 'ThresholdViolation',
        })
        failure.text = message


# ── Markdown Summary ────────────────────────────────────────────────────────

def generate_markdown_summary(analysis: Dict[str, Any]) -> str:
    """Generate a Markdown summary suitable for PR comments."""
    from .metrics import calculate_health
    scores = calculate_health(analysis)

    lines = []
    lines.append('## 🔍 CodeVista Analysis Report')
    lines.append('')

    # Summary table
    lines.append('| Metric | Value |')
    lines.append('|--------|-------|')
    lines.append(f'| 📁 Files | {analysis["total_files"]:,} |')
    lines.append(f'| 📝 Lines of Code | {analysis["total_lines"]["code"]:,} |')
    lines.append(f'| ⚡ Avg Complexity | {analysis["avg_complexity"]:.1f} |')
    lines.append(f'| 🔒 Security Issues | {len(analysis["security_issues"])} |')
    lines.append(f'| 📦 Dependencies | {len(analysis["dependencies"])} |')
    lines.append(f'| ♻️ Duplicates | {len(analysis["duplicates"])} |')
    lines.append(f'| 🏥 Health Score | **{scores["overall"]}/100** |')
    lines.append('')

    # Health scores
    lines.append('### Health Scores')
    lines.append('')
    for cat in ('readability', 'complexity', 'duplication', 'coverage',
                'security', 'dependencies', 'maintainability'):
        val = scores[cat]
        icon = '✅' if val >= 80 else '⚠️' if val >= 50 else '❌'
        bar = '█' * (val // 5) + '░' * (20 - val // 5)
        lines.append(f'- {icon} **{cat.title()}**: `{val}/100` `{bar}`')
    lines.append('')

    # Top issues
    if analysis.get('security_issues'):
        lines.append('### 🔒 Security Issues')
        lines.append('')
        for issue in analysis['security_issues'][:10]:
            sev_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}.get(
                issue['severity'], '⚪')
            lines.append(
                f'- {sev_icon} **{issue["severity"].upper()}** `{issue["file"]}:{issue.get("line", 0)}` '
                f'- {issue["name"]}'
            )
        lines.append('')

    # Top complex functions
    top_funcs = sorted(analysis.get('functions', []),
                       key=lambda x: x.get('complexity', 0), reverse=True)[:5]
    if top_funcs:
        lines.append('### ⚡ Most Complex Functions')
        lines.append('')
        lines.append('| Function | Complexity | File |')
        lines.append('|----------|-----------|------|')
        for f in top_funcs:
            lines.append(f'| `{f["name"]}` | {f["complexity"]} | `{f.get("file", "").split("/")[-1]}` |')
        lines.append('')

    lines.append(f'*Generated by [CodeVista](https://github.com/codevista/codevista) on {datetime.now().strftime("%Y-%m-%d")}*')

    return '\n'.join(lines)


# ── Terminal One-Line Summary ───────────────────────────────────────────────

def generate_one_line_summary(analysis: Dict[str, Any]) -> str:
    """Generate a compact one-line summary for terminal output."""
    from .metrics import calculate_health
    scores = calculate_health(analysis)

    overall = scores['overall']
    icon = '✅' if overall >= 80 else '⚠️' if overall >= 50 else '❌'

    sec = len(analysis['security_issues'])
    cc = analysis['avg_complexity']
    deps = len(analysis['dependencies'])

    parts = [f'{icon} Health:{overall}']
    if sec > 0:
        parts.append(f'Sec:{sec}')
    if cc > 8:
        parts.append(f'CC:{cc:.1f}')
    parts.append(f'Files:{analysis["total_files"]:,}')
    parts.append(f'LoC:{analysis["total_lines"]["code"]:,}')

    return 'CodeVista │ ' + ' │ '.join(parts)


# ── Output Dispatcher ───────────────────────────────────────────────────────

OUTPUT_FORMATS = {
    'sarif': {
        'description': 'SARIF (GitHub Code Scanning)',
        'extension': '.sarif.json',
        'generator': lambda a, t: json.dumps(generate_sarif(a), indent=2),
        'content_type': 'application/json',
    },
    'gitlab': {
        'description': 'GitLab Code Quality JSON',
        'extension': '.gitlab-codequality.json',
        'generator': lambda a, t: json.dumps(generate_gitlab_codequality(a), indent=2),
        'content_type': 'application/json',
    },
    'checkstyle': {
        'description': 'Checkstyle XML',
        'extension': '.checkstyle.xml',
        'generator': lambda a, t: generate_checkstyle(a),
        'content_type': 'application/xml',
    },
    'junit': {
        'description': 'JUnit XML',
        'extension': '.junit.xml',
        'generator': lambda a, t: generate_junit(a, t),
        'content_type': 'application/xml',
    },
    'markdown': {
        'description': 'Markdown Summary (PR comments)',
        'extension': '.md',
        'generator': lambda a, t: generate_markdown_summary(a),
        'content_type': 'text/markdown',
    },
    'terminal': {
        'description': 'Terminal one-line summary',
        'extension': '.txt',
        'generator': lambda a, t: generate_one_line_summary(a),
        'content_type': 'text/plain',
    },
}


def output_ci(analysis: Dict[str, Any], fmt: str = 'sarif',
              output_path: str = None,
              config_path: str = None) -> Tuple[str, int]:
    """Generate CI output and evaluate thresholds.

    Returns (output_content, exit_code).
    """
    thresholds = load_thresholds(config_path)
    threshold_result = evaluate_thresholds(analysis, thresholds)

    fmt_lower = fmt.lower()
    fmt_config = OUTPUT_FORMATS.get(fmt_lower)
    if not fmt_config:
        available = ', '.join(OUTPUT_FORMATS.keys())
        print(f"❌ Unknown format: {fmt}. Available: {available}")
        return '', EXIT_ERRORS

    content = fmt_config['generator'](analysis, thresholds)

    # If threshold has critical violations, override exit code
    exit_code = threshold_result['exit_code']

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        ext = fmt_config['extension']
        if not output_path.endswith(ext):
            output_path += ext
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Output written to: {output_path}")
    else:
        print(content)

    # Print threshold results
    if threshold_result['violations']:
        print(f"\n🚨 {len(threshold_result['violations'])} threshold violation(s):")
        for v in threshold_result['violations']:
            icon = {'critical': '💀', 'high': '🔴', 'error': '❌',
                    'medium': '🟡', 'warning': '⚠️'}.get(v['severity'], '•')
            print(f"  {icon} [{v['severity']}] {v['message']}")
    else:
        print(f"\n✅ All thresholds passed!")

    print(f"\n📋 Exit code: {exit_code} "
          f"({'clean' if exit_code == 0 else 'warnings' if exit_code == 1 else 'errors' if exit_code == 2 else 'critical'})")

    return content, exit_code


# ── Helpers ─────────────────────────────────────────────────────────────────

def _max_severity(current: str, new: str) -> str:
    """Return the higher severity."""
    order = {'critical': 4, 'high': 3, 'error': 3, 'medium': 2, 'warning': 1, 'none': 0}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _parse_simple_yaml(content: str) -> Dict[str, Any]:
    """Minimal YAML parser for flat key-value configs."""
    result = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([\w_]+):\s*(.+)$', line)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        # Try to parse as number
        try:
            if '.' in val:
                val = float(val)
            else:
                val = int(val)
        except ValueError:
            if val.lower() in ('true', 'yes'):
                val = True
            elif val.lower() in ('false', 'no'):
                val = False
        result[key] = val
    return result


def print_threshold_help():
    """Print available threshold configurations."""
    print("\n📋 Available Thresholds:")
    print(f"{'─'*50}")
    for key, default in DEFAULT_THRESHOLDS.items():
        type_label = type(default).__name__
        print(f"  {key:<30s} = {default!s:>6s} ({type_label})")
    print(f"\n  Configure in .codevista.json:")
    print('  {')
    for key, default in DEFAULT_THRESHOLDS.items():
        print(f'    "{key}": {default!r},')
    print('  }')
