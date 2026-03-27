"""Tests for security scanner."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.security import scan_file, security_score, security_summary


class TestSecretDetection:
    def test_aws_key(self):
        content = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        issues = scan_file('test.py', content)
        assert any('AWS' in i['name'] for i in issues)

    def test_generic_password(self):
        content = 'password = "super_secret_123"\n'
        issues = scan_file('test.py', content)
        assert any('Password' in i['name'] for i in issues)

    def test_generic_api_key(self):
        content = 'api_key = "abcdefghijklmnopqrstuvwxyz"\n'
        issues = scan_file('test.py', content)
        assert any('API Key' in i['name'] for i in issues)

    def test_jwt_token(self):
        content = 'token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"\n'
        issues = scan_file('test.py', content)
        assert any('JWT' in i['name'] for i in issues)

    def test_private_key(self):
        content = '-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n'
        issues = scan_file('test.py', content)
        assert any('Private Key' in i['name'] for i in issues)

    def test_github_token(self):
        content = 'ghp_abcdefghijklmnopqrstuvwxyz1234567890\n'
        issues = scan_file('test.py', content)
        assert any('GitHub' in i['name'] for i in issues)

    def test_stripe_key(self):
        content = 'pk_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n'
        issues = scan_file('test.py', content)
        assert any('Stripe' in i['name'] for i in issues)

    def test_example_password_ignored(self):
        content = 'password = "example_password"\n'
        issues = scan_file('test.py', content)
        passwords = [i for i in issues if 'Password' in i['name']]
        assert len(passwords) == 0

    def test_placeholder_ignored(self):
        content = 'api_key = "your_api_key_here"\n'
        issues = scan_file('test.py', content)
        api_keys = [i for i in issues if 'API Key' in i['name']]
        assert len(api_keys) == 0

    def test_none_value_ignored(self):
        content = 'password = None\n'
        issues = scan_file('test.py', content)
        passwords = [i for i in issues if 'Password' in i['name']]
        assert len(passwords) == 0


class TestDangerousPatterns:
    def test_eval_detection(self):
        content = 'result = eval(user_input)\n'
        issues = scan_file('test.py', content)
        assert any('eval' in i['name'] for i in issues)

    def test_shell_true_detection(self):
        content = 'subprocess.run(cmd, shell=True)\n'
        issues = scan_file('test.py', content)
        assert any('shell=True' in i['name'] for i in issues)

    def test_pickle_detection(self):
        content = 'data = pickle.loads(serialized)\n'
        issues = scan_file('test.py', content)
        assert any('pickle' in i['name'] for i in issues)

    def test_yaml_load_detection(self):
        content = 'config = yaml.load(content)\n'
        issues = scan_file('test.py', content)
        assert any('yaml' in i['name'].lower() for i in issues)

    def test_debug_mode(self):
        content = 'DEBUG = True\n'
        issues = scan_file('settings.py', content)
        assert any('DEBUG' in i['name'] for i in issues)

    def test_ssl_verify_false(self):
        content = 'requests.get(url, verify=False)\n'
        issues = scan_file('test.py', content)
        assert any('SSL' in i['name'] for i in issues)

    def test_md5_detection(self):
        content = 'hashlib.md5(data).hexdigest()\n'
        issues = scan_file('test.py', content)
        assert any('MD5' in i['name'] for i in issues)


class TestScoring:
    def test_no_issues_perfect_score(self):
        assert security_score([]) == 100

    def test_critical_issues_lower_score(self):
        issues = [{'severity': 'critical', 'count': 2}]
        score = security_score(issues)
        assert score < 100

    def test_security_summary(self):
        issues = [
            {'severity': 'critical', 'category': 'secrets', 'file': 'a.py', 'count': 1},
            {'severity': 'high', 'category': 'code', 'file': 'b.py', 'count': 1},
            {'severity': 'low', 'category': 'info', 'file': 'c.py', 'count': 1},
        ]
        summary = security_summary(issues)
        assert summary['total'] == 3
        assert summary['by_severity']['critical'] == 1
        assert summary['by_severity']['high'] == 1


class TestEnvFile:
    def test_env_file_detection(self):
        content = 'DB_PASSWORD=secret123\nAPI_KEY=abcdef\n'
        issues = scan_file('.env', content)
        assert any('.env' in i['name'] for i in issues)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
