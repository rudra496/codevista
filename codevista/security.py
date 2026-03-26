"""Comprehensive security scanner — 40+ secret patterns, dangerous code detection.

Scans for hardcoded secrets, credentials, API keys, tokens,
dangerous function usage, SQL injection risks, command injection,
and security misconfigurations.
"""

import os
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple


# ── Secret Detection Patterns (40+) ─────────────────────────────────────────

SECRET_PATTERNS: List[Tuple[str, str, str, str]] = [
    # AWS
    (r'(?i)akia[0-9a-z]{16}', 'AWS Access Key', 'critical', 'secrets'),
    (r'(?i)aws_secret_access_key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}', 'AWS Secret Key', 'critical', 'secrets'),
    (r'(?i)aws_access_key_id\s*[=:]\s*["\']?AKIA[0-9A-Z]{16}', 'AWS Access Key ID', 'critical', 'secrets'),
    (r'(?i)aws_session_token\s*[=:]\s*["\']?[A-Za-z0-9/+=]{200,}', 'AWS Session Token', 'critical', 'secrets'),
    (r'(?i)aws[-_]?(?:key|secret|token)\s*[=:]\s*["\'][^"\']{8,}', 'AWS Credential', 'critical', 'secrets'),
    (r'(?i)aws_account_id\s*[=:]\s*["\']\d{12}', 'AWS Account ID', 'high', 'secrets'),

    # Google
    (r'(?i)google[_-]?api[_-]?key\s*[=:]\s*["\']AIza[0-9A-Za-z\-_]{35}', 'Google API Key', 'critical', 'secrets'),
    (r'(?i)google[_-]?oauth[_-]?client[_-]?id\s*[=:]\s*["\'][^"\']{10,}', 'Google OAuth Client ID', 'high', 'secrets'),
    (r'(?i)google[_-]?service[_-]?account\s*[=:]\s*["\'][^"\']{10,}', 'Google Service Account', 'critical', 'secrets'),
    (r'(?i)"type":\s*"service_account"', 'Google Service Account Key File', 'critical', 'secrets'),
    (r'(?i)google[_-]?cloud[_-]?api[_-]?key\s*[=:]\s*["\'][^"\']{20,}', 'Google Cloud API Key', 'critical', 'secrets'),
    (r'(?i)google[_-]?maps[_-]?key\s*[=:]\s*["\'][^"\']{20,}', 'Google Maps API Key', 'critical', 'secrets'),
    (r'(?i)firebase[_-]?api[_-]?key\s*[=:]\s*["\']AIza[0-9A-Za-z\-_]{35}', 'Firebase API Key', 'critical', 'secrets'),
    (r'(?i)gcp_service_account_key', 'GCP Service Account Key Reference', 'critical', 'secrets'),

    # GitHub
    (r'(?i)github[_-]?token\s*[=:]\s*["\']?(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}', 'GitHub Token', 'critical', 'secrets'),
    (r'(?i)ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Access Token', 'critical', 'secrets'),
    (r'(?i)gho_[a-zA-Z0-9]{36}', 'GitHub OAuth Token', 'critical', 'secrets'),
    (r'(?i)ghs_[a-zA-Z0-9]{36}', 'GitHub App Token', 'critical', 'secrets'),
    (r'(?i)ghr_[a-zA-Z0-9]{36}', 'GitHub Refresh Token', 'critical', 'secrets'),
    (r'(?i)glpat-[a-zA-Z0-9\-]{20,}', 'GitLab PAT', 'critical', 'secrets'),
    (r'(?i)glptt-[a-zA-Z0-9\-]{20,}', 'GitLab Trigger Token', 'high', 'secrets'),
    (r'(?i)gitlab[-_]?token\s*[=:]\s*["\'][^"\']{10,}', 'GitLab Token', 'critical', 'secrets'),
    (r'(?i)bitbucket[-_]?token\s*[=:]\s*["\'][^"\']{10,}', 'Bitbucket Token', 'critical', 'secrets'),

    # Stripe
    (r'(?i)(?:pk|sk|rk)_(?:test|live)_[a-zA-Z0-9]{24,}', 'Stripe Key', 'critical', 'secrets'),
    (r'(?i)stripe[_-]?(?:publishable|secret)[_-]?key\s*[=:]\s*["\'][^"\']{10,}', 'Stripe Key', 'critical', 'secrets'),

    # Twilio
    (r'(?i)twilio[_-]?account[_-]?sid\s*[=:]\s*["\']AC[a-f0-9]{32}', 'Twilio Account SID', 'critical', 'secrets'),
    (r'(?i)twilio[_-]?auth[_-]?token\s*[=:]\s*["\'][a-f0-9]{32}', 'Twilio Auth Token', 'critical', 'secrets'),

    # SendGrid
    (r'(?i)sendgrid[_-]?api[_-]?key\s*[=:]\s*["\']SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}', 'SendGrid API Key', 'critical', 'secrets'),

    # Slack
    (r'(?i)https://hooks\.slack\.com/services/T[a-zA-Z0-9]{8}/B[a-zA-Z0-9]{8}/[a-zA-Z0-9]{24}', 'Slack Webhook URL', 'high', 'secrets'),
    (r'(?i)xox[bpas]-[a-zA-Z0-9\-]{10,}', 'Slack Bot/Token', 'high', 'secrets'),
    (r'(?i)slack[_-]?webhook\s*[=:]\s*["\'][^"\']{10,}', 'Slack Webhook', 'high', 'secrets'),

    # Azure
    (r'(?i)azure[-_]?connection[-_]?string\s*[=:]\s*["\'][^"\']{10,}', 'Azure Connection String', 'critical', 'secrets'),
    (r'(?i)azure[-_]?storage[-_]?key\s*[=:]\s*["\'][a-zA-Z0-9+]{40,}', 'Azure Storage Key', 'critical', 'secrets'),
    (r'(?i)azure[-_]?subscription[-_]?id\s*[=:]\s*["\'][a-f0-9\-]{36}', 'Azure Subscription ID', 'high', 'secrets'),
    (r'(?i)azure[-_]?client[-_]?secret\s*[=:]\s*["\'][^"\']{10,}', 'Azure Client Secret', 'critical', 'secrets'),

    # MongoDB
    (r'(?i)mongodb(?:\+srv)?://[^\s"\']+', 'MongoDB Connection URI', 'high', 'secrets'),

    # PostgreSQL
    (r'(?i)postgresql://[^\s"\']+', 'PostgreSQL Connection URI', 'high', 'secrets'),
    (r'(?i)postgres://[^\s"\']+', 'PostgreSQL Connection URI', 'high', 'secrets'),

    # MySQL
    (r'(?i)mysql://[^\s"\']+', 'MySQL Connection URI', 'high', 'secrets'),

    # Redis
    (r'(?i)redis://[^\s"\']+', 'Redis Connection URI', 'high', 'secrets'),

    # JWT
    (r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}', 'JWT Token', 'high', 'secrets'),
    (r'(?i)jwt[_-]?secret\s*[=:]\s*["\'][^"\']{8,}', 'JWT Secret', 'critical', 'secrets'),

    # Private Keys
    (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', 'Private Key', 'critical', 'secrets'),
    (r'-----BEGIN PGP PRIVATE KEY BLOCK-----', 'PGP Private Key', 'critical', 'secrets'),
    (r'-----BEGIN ENCRYPTED PRIVATE KEY-----', 'Encrypted Private Key', 'critical', 'secrets'),
    (r'-----BEGIN EC PRIVATE KEY-----', 'EC Private Key', 'critical', 'secrets'),
    (r'-----BEGIN SSH2 PRIVATE KEY-----', 'SSH2 Private Key', 'critical', 'secrets'),

    # Generic secrets
    (r'(?i)api[_-]?key\s*[=:]\s*["\'][a-zA-Z0-9_\-]{20,}', 'API Key (generic)', 'high', 'secrets'),
    (r'(?i)secret[_-]?key\s*[=:]\s*["\'][^"\']{8,}', 'Secret Key (generic)', 'high', 'secrets'),
    (r'(?i)password\s*[=:]\s*["\'][^"\']{4,}', 'Hardcoded Password', 'critical', 'secrets'),
    (r'(?i)passwd\s*[=:]\s*["\'][^"\']{4,}', 'Hardcoded Password (passwd)', 'critical', 'secrets'),
    (r'(?i)(?:token|auth|bearer)\s*[=:]\s*["\'][a-zA-Z0-9_\-\.]{20,}', 'Generic Token', 'high', 'secrets'),
    (r'(?i)authorization\s*[=:]\s*["\']Bearer [a-zA-Z0-9_\-\.]{20,}', 'Bearer Token', 'high', 'secrets'),
    (r'(?i)client[_-]?secret\s*[=:]\s*["\'][^"\']{8,}', 'Client Secret', 'critical', 'secrets'),
    (r'(?i)private[_-]?key\s*[=:]\s*["\'][a-zA-Z0-9/+=]{20,}', 'Private Key Value', 'critical', 'secrets'),
    (r'(?i)access[_-]?token\s*[=:]\s*["\'][a-zA-Z0-9_\-\.]{20,}', 'Access Token', 'high', 'secrets'),
    (r'(?i)refresh[_-]?token\s*[=:]\s*["\'][a-zA-Z0-9_\-\.]{20,}', 'Refresh Token', 'high', 'secrets'),
    (r'(?i)credentials\s*[=:]\s*["\'][^"\']{8,}', 'Hardcoded Credentials', 'critical', 'secrets'),
    (r'(?i)db[_-]?password\s*[=:]\s*["\'][^"\']{4,}', 'Database Password', 'critical', 'secrets'),
    (r'(?i)encryption[_-]?key\s*[=:]\s*["\'][^"\']{8,}', 'Encryption Key', 'critical', 'secrets'),
    (r'(?i)signing[_-]?key\s*[=:]\s*["\'][^"\']{8,}', 'Signing Key', 'critical', 'secrets'),

    # IPs and emails
    (r'\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b', 'Hardcoded IP Address', 'low', 'info'),
    (r'(?i)[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'Hardcoded Email', 'low', 'info'),
]


# ── Dangerous Code Patterns ─────────────────────────────────────────────────

DANGEROUS_PATTERNS: List[Tuple[str, str, str, str]] = [
    # Code execution
    (r'\beval\s*\(', 'eval() — arbitrary code execution risk', 'high', 'code'),
    (r'\bexec\s*\(', 'exec() — arbitrary code execution risk', 'high', 'code'),
    (r'\b__import__\s*\(', '__import__() — dynamic import risk', 'medium', 'code'),
    (r'\bcompile\s*\(', 'compile() — code injection risk', 'medium', 'code'),
    (r'\bgetattr\s*\([^,]+,\s*["\'][^"\']+["\']\s*,', 'getattr with string attribute — potential injection', 'low', 'code'),

    # Command injection
    (r'\bsubprocess\.\w+\([^)]*shell\s*=\s*True', 'subprocess with shell=True — command injection', 'high', 'code'),
    (r'\bos\.system\s*\(', 'os.system() — command injection', 'high', 'code'),
    (r'\bos\.popen\s*\(', 'os.popen() — command injection', 'high', 'code'),
    (r'\bcommands\s*\.\s*getoutput\s*\(', 'commands.getoutput() — command injection', 'high', 'code'),
    (r'\bpopen2\s*\(', 'popen2() — command injection', 'high', 'code'),
    (r'\bos\.exec[a-z]*\s*\(', 'os.exec*() — command execution', 'high', 'code'),
    (r'\bpty\.spawn\s*\(', 'pty.spawn() — command execution', 'high', 'code'),
    (r'\bfabric\.api\.local\s*\(', 'fabric local() — command execution', 'medium', 'code'),

    # Deserialization
    (r'\bpickle\.loads?\s*\(', 'pickle.loads() — arbitrary code execution', 'high', 'code'),
    (r'\bpickle\.load\s*\(', 'pickle.load() — arbitrary code execution', 'high', 'code'),
    (r'\bmarshal\.loads?\s*\(', 'marshal.loads() — arbitrary code execution', 'high', 'code'),
    (r'\byaml\.load\s*\(', 'yaml.load() without SafeLoader — code execution', 'medium', 'code'),
    (r'\bshelve\.open\s*\(', 'shelve.open() — deserialization risk', 'medium', 'code'),
    (r'\bjson\.loads?\s*\([^)]*object_hook', 'JSON with custom hook — potential code execution', 'medium', 'code'),

    # SSRF
    (r'urllib\.request\.urlopen\s*\(', 'urllib.urlopen() — potential SSRF', 'medium', 'code'),
    (r'\burllib2\.urlopen\s*\(', 'urllib2.urlopen() — potential SSRF', 'medium', 'code'),
    (r'\brequests\.get\s*\(\s*["\']http', 'requests.get with hardcoded URL', 'low', 'code'),
    (r'\brequests\.post\s*\(\s*["\']http', 'requests.post with hardcoded URL', 'low', 'code'),

    # Path traversal
    (r'os\.path\.join\s*\([^)]*\+?\s*(?:request|input|param|args|form)', 'Path traversal with user input', 'high', 'code'),
    (r'open\s*\([^)]*(?:\+|format|f["\'])', 'File open with string concatenation', 'medium', 'code'),
    (r'\.\.\s*[/\\](?:etc|proc|sys|home|tmp|var)', 'Path traversal attempt (../)', 'high', 'code'),

    # SQL injection
    (r'(?:execute|cursor\.execute)\s*\([^)]*(?:\+|format|f["\'])', 'SQL with string formatting — injection risk', 'high', 'code'),
    (r'(?:SELECT|INSERT|UPDATE|DELETE).*(?:\+|format|f["\'])', 'SQL string concatenation — injection risk', 'high', 'code'),
    (r'raw\s*=\s*True', 'Django ORM raw() — SQL injection risk', 'medium', 'code'),
    (r'\bModel\.objects\.raw\s*\(', 'Django raw SQL query', 'medium', 'code'),

    # Debug/security misconfiguration
    (r'\bDEBUG\s*=\s*True', 'DEBUG mode enabled', 'medium', 'config'),
    (r'\bFLASK_DEBUG\s*=\s*[Tt]rue', 'Flask DEBUG mode enabled', 'medium', 'config'),
    (r'\bAPP_DEBUG\s*=\s*True', 'APP_DEBUG enabled', 'medium', 'config'),
    (r'print\s*\(\s*(?:request|error|exception|traceback)', 'Verbose error/sensitive data in print', 'medium', 'code'),
    (r'\blogging\.basicConfig\s*\([^)]*level\s*=\s*logging\.DEBUG', 'Debug-level logging configured', 'low', 'config'),
    (r'console\.log\s*\(\s*(?:process\.env|req\.(?:body|headers|query))', 'Sensitive data in console.log', 'medium', 'code'),
    (r'\bstack_trace\s*=\s*True', 'Stack trace enabled in production', 'medium', 'config'),
    (r'SHOW_DEBUG_TOOLBAR\s*=\s*True', 'Django Debug Toolbar enabled', 'medium', 'config'),

    # SSL/TLS
    (r'verify\s*=\s*False', 'SSL verification disabled', 'high', 'code'),
    (r'ssl\.create_default_context\s*\(\s*\)', 'SSL context without verification', 'medium', 'code'),
    (r'SSLContext\(\)', 'SSL context without verification', 'medium', 'code'),
    (r'PROTOCOL_TLS\s*=\s*ssl\._SSLMethod\.PROTOCOL_TLSv1', 'Insecure TLS version', 'high', 'code'),
    (r'TLSv1[_\d]*\b', 'Insecure TLS version (v1.0/v1.1)', 'medium', 'code'),

    # Weak crypto
    (r'\bmd5\s*\(', 'MD5 — weak hash algorithm', 'medium', 'code'),
    (r'\bsha1\s*\(', 'SHA1 — weak hash algorithm', 'medium', 'code'),
    (r'\bDES\s*\(', 'DES — weak encryption', 'high', 'code'),
    (r'\bRC4\s*\(', 'RC4 — weak encryption', 'high', 'code'),
    (r'\bcrypt\.gensalt\s*\(\s*\)', 'bcrypt without cost factor', 'low', 'code'),
    (r'\bhashlib\.md5\b', 'MD5 hashlib usage — weak hash', 'medium', 'code'),
    (r'\bhashlib\.sha1\b', 'SHA1 hashlib usage — weak hash', 'medium', 'code'),

    # Hardcoded ports
    (r':(?:3306|5432|27017|6379|9200|5672|9092|1521|1433)\b', 'Well-known service port hardcoded', 'low', 'info'),

    # CORS
    (r'Access-Control-Allow-Origin.*\*', 'CORS allows all origins', 'medium', 'config'),
    (r'cors\s*=\s*True', 'CORS broadly enabled', 'medium', 'config'),
    (r'allow_origins\s*=\s*["\']\*["\']', 'CORS allows all origins', 'medium', 'config'),
    (r'@cross_origin\(origins\s*=\s*["\']\*', 'CORS wildcard origin', 'medium', 'config'),

    # Race conditions
    (r'if\s+os\.path\.exists\s*\([^)]+\)\s*:\s*\n.*open\s*\(', 'TOCTOU race condition', 'medium', 'code'),
    (r'file\.read\(\).*file\.write\(', 'Non-atomic read-modify-write — race condition', 'medium', 'code'),

    # Log injection
    (r'logging\.(?:info|debug|warning|error)\s*\([^)]*(?:request|input|param|args|form)', 'Unsanitized user input in log — log injection risk', 'medium', 'code'),
    (r'logger\.(?:info|debug|warning|error)\s*\([^)]*(?:request|input|param|args|form)', 'Unsanitized user input in logger — log injection risk', 'medium', 'code'),

    # Other
    (r'\binput\s*\(', 'input() — potential injection (Python 2)', 'low', 'code'),
    (r'\bassert\s*\(', 'assert — disabled with -O optimization flag', 'low', 'code'),
    (r'(?i)TODO.*(?:password|secret|key|token)', 'TODO mentions sensitive data', 'low', 'info'),
    (r'(?i)FIXME.*(?:password|secret|key|token)', 'FIXME mentions sensitive data', 'low', 'info'),
    (r'\btempfile\.mktemp\s*\(', 'tempfile.mktemp() — insecure, use mkstemp', 'medium', 'code'),
    (r'\brandom\.\s*random\s*\(', 'random.random() — not cryptographically secure', 'low', 'code'),
    (r'chmod\s*\(.*0o777', 'chmod 777 — overly permissive', 'high', 'code'),
    (r'\bXMLParser\b', 'XMLParser — vulnerable to XXE attacks', 'medium', 'code'),
    (r'defusedxml', 'defusedxml found — good practice (informational)', 'low', 'info'),
]

# ── Patterns to exclude (reduce false positives) ─────────────────────────────

EXCLUDE_PATTERNS: List[str] = [
    r'\bexample\.com\b', r'\bexample\.org\b', r'\blinux',
    r'\blocalhost\b', r'\b127\.0\.0\.1\b', r'\b0\.0\.0\.0\b',
    r'\b10\.\d+\.\d+\.\d+\b', r'\b172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+\b',
    r'\b192\.168\.\d+\.\d+\b',
    r'\btest[_-]?(?:key|secret|token|password)\b',
    r'\b(?:fake|mock|dummy|placeholder|example|sample|your[-_]?)[_-]?(?:key|secret|token|password|api)',
    r'\bxxx+["\']?\s*[,;)]',
    r'\bnone["\']?\s*[,;)]',
    r'\bnull["\']?\s*[,;)]',
    r'\bchangeme["\']?\s*[,;)]',
    r'\bpassword123["\']?\s*[,;)]',
    r'\b(?:TODO|FIXME|HACK|NOTE)\b.*\b(?:your|placeholder|example)\b',
]


def scan_file(filepath: str, content: str) -> List[Dict]:
    """Scan a file for security issues."""
    issues: List[Dict] = []
    rel = filepath

    basename = os.path.basename(filepath)
    if basename == '.env' or (basename.endswith('.env') and not basename.endswith('.env.example') and not basename.endswith('.env.local')):
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        if lines:
            issues.append({
                'file': rel, 'type': 'config', 'name': '.env file committed to repository',
                'severity': 'high', 'count': len(lines), 'line': 1,
                'category': 'secrets',
                'remediation': 'Use .env.example and add .env to .gitignore. Use secrets manager in production.',
            })

    env_like_files = {'.env.production', '.env.staging', '.env.local', '.env.development'}
    if basename.lower() in env_like_files:
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        if lines:
            issues.append({
                'file': rel, 'type': 'config', 'name': f'{basename} committed to repository',
                'severity': 'high', 'count': len(lines), 'line': 1,
                'category': 'secrets',
                'remediation': 'Add this file to .gitignore. Use environment-specific config management.',
            })

    for pattern, name, severity, category in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            filtered = 0
            for match in matches:
                match_str = str(match)
                is_fp = False
                for excl in EXCLUDE_PATTERNS:
                    if re.search(excl, match_str, re.IGNORECASE):
                        is_fp = True
                        break
                if not is_fp:
                    filtered += 1
            if filtered > 0:
                line_num = _find_line(content, pattern)
                issues.append({
                    'file': rel, 'type': category, 'name': name,
                    'severity': severity, 'count': filtered, 'line': line_num,
                    'category': category,
                    'remediation': _get_remediation(name, severity),
                })

    for pattern, name, severity, category in DANGEROUS_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            line_num = _find_line(content, pattern)
            issues.append({
                'file': rel, 'type': category, 'name': name,
                'severity': severity, 'count': len(matches), 'line': line_num,
                'category': category,
                'remediation': _get_remediation(name, severity),
            })

    return issues


def _find_line(content: str, pattern: str) -> int:
    """Find first line number matching pattern."""
    for i, line in enumerate(content.split('\n'), 1):
        if re.search(pattern, line):
            return i
    return 0


def _get_remediation(name: str, severity: str) -> str:
    """Get remediation suggestion for an issue."""
    n = name.lower()
    if 'password' in n or 'secret' in n:
        return 'Move to environment variables or a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault).'
    if 'key' in n and ('private' in n or 'api' in n or 'access' in n):
        return 'Rotate the key immediately. Store in a secrets manager and use environment variables.'
    if 'token' in n:
        return 'Use environment variables. Rotate the token immediately if this is committed to version control.'
    if 'eval' in n or 'exec' in n:
        return 'Avoid eval/exec. Use safer alternatives like ast.literal_eval() or explicit function calls.'
    if 'pickle' in n or 'marshal' in n or 'shelve' in n:
        return 'Avoid pickle for untrusted data. Use JSON, MessagePack, or other safe serialization formats.'
    if 'yaml' in n and 'load' in n:
        return 'Use yaml.safe_load() instead of yaml.load() to prevent arbitrary code execution.'
    if 'sql' in n or 'injection' in n:
        return 'Use parameterized queries / prepared statements instead of string concatenation.'
    if 'command' in n or 'shell' in n:
        return 'Avoid shell=True. Use subprocess with a list of arguments instead of a shell string.'
    if 'ssrf' in n or 'urlopen' in n:
        return 'Validate and whitelist URLs. Use a URL parsing library to block private/internal IPs.'
    if 'path traversal' in n:
        return 'Use os.path.abspath() to resolve paths and verify they stay within allowed directories.'
    if 'ssl' in n or 'verify' in n or 'tls' in n:
        return 'Enable SSL certificate verification. Use certifi or system CA bundle.'
    if 'md5' in n or 'sha1' in n:
        return 'Use SHA-256 or stronger hash algorithms for security purposes.'
    if 'des' in n or 'rc4' in n:
        return 'Use AES-256-GCM or ChaCha20-Poly1305 instead of deprecated weak ciphers.'
    if 'debug' in n:
        return 'Disable debug mode in production environments.'
    if 'cors' in n:
        return 'Restrict CORS to specific allowed origins, not wildcard "*".'
    if 'env' in n:
        return 'Use .env.example for templates. Add .env to .gitignore.'
    if 'chmod' in n:
        return 'Use minimum required permissions instead of 777.'
    if 'xxe' in n or 'xml' in n:
        return 'Use defusedxml or configure XML parser to disable external entities.'
    if 'race' in n or 'toctou' in n:
        return 'Use atomic operations, file locks, or transactional patterns.'
    if 'log' in n and 'inject' in n:
        return 'Sanitize user input before logging. Remove newlines and control characters.'
    if 'random' in n and 'crypto' in n:
        return 'Use secrets module or os.urandom() for cryptographic randomness.'
    if 'mktemp' in n:
        return 'Use tempfile.mkstemp() or tempfile.NamedTemporaryFile() instead.'
    return 'Review this finding and ensure it follows security best practices.'


def security_score(issues: List[Dict]) -> int:
    """Calculate security score 0-100."""
    if not issues:
        return 100
    weights = {'critical': 15, 'high': 8, 'medium': 3, 'low': 1}
    penalty = sum(weights.get(i['severity'], 2) * min(i['count'], 5) for i in issues)
    return max(0, 100 - penalty)


def security_summary(issues: List[Dict]) -> Dict:
    """Group issues by severity and type."""
    by_severity = Counter(i['severity'] for i in issues)
    by_type = Counter(i.get('category', 'unknown') for i in issues)
    by_file = Counter(i.get('file', 'unknown') for i in issues)
    critical_files = [f for f, c in by_file.most_common(10) if c > 0]
    return {
        'total': len(issues),
        'by_severity': dict(by_severity),
        'by_type': dict(by_type),
        'top_files': critical_files,
        'score': security_score(issues),
    }


def scan_directory(project_path: str) -> List[Dict]:
    """Scan all files in a directory for security issues."""
    from .config import load_config, should_ignore
    from .languages import detect_language
    all_issues = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), project_path)]
        for fname in files:
            fpath = os.path.join(root, fname)
            if should_ignore(fpath, project_path):
                continue
            lang = detect_language(fpath)
            if lang is None and not fname.startswith('.'):
                continue
            try:
                content = open(fpath, 'r', errors='ignore').read()
            except OSError:
                continue
            issues = scan_file(fpath, content)
            all_issues.extend(issues)
    return all_issues


def get_severity_icon(severity: str) -> str:
    """Return emoji icon for severity level."""
    return {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': 'ℹ️'}.get(severity, '❓')


def get_severity_color(severity: str) -> str:
    """Return hex color for severity level."""
    return {'critical': '#e53170', 'high': '#ff8906', 'medium': '#7f5af0', 'low': '#a7a9be', 'info': '#72757e'}.get(severity, '#999')


# ── Advanced Security Scanners ─────────────────────────────────────────────

def scan_for_dependency_confusion(manifest_path: str, deps: list) -> list:
    """Detect potential dependency confusion attacks."""
    issues = []
    for dep in deps:
        name = dep.get('name', '')
        # Check if package name matches internal module
        if any(c.isupper() for c in name) and '-' in name:
            issues.append({
                'name': f'Possible dependency confusion: {name}',
                'severity': 'medium',
                'category': 'supply_chain',
                'remediation': 'Use scoped packages or internal registry to prevent typosquatting.',
            })
    return issues


def scan_for_typosquatting(deps: list, popular_packages: list = None) -> list:
    """Detect potential typosquatting in dependencies."""
    if popular_packages is None:
        popular_packages = [
            'react', 'vue', 'angular', 'express', 'lodash', 'axios', 'moment',
            'numpy', 'pandas', 'requests', 'flask', 'django', 'tensorflow',
            'eslint', 'webpack', 'babel', 'typescript', 'jest', 'mocha',
        ]
    
    issues = []
    for dep in deps:
        name = dep.get('name', '').lower()
        for popular in popular_packages:
            if name != popular and _levenshtein_distance(name, popular) <= 2:
                issues.append({
                    'name': f'Possible typosquatting: {name} (similar to {popular})',
                    'severity': 'high',
                    'category': 'supply_chain',
                    'remediation': f'Verify that {name} is the intended package, not a typo for {popular}.',
                })
    return issues


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def scan_for_post_message_risks(content: str) -> list:
    """Scan for unsafe postMessage usage."""
    issues = []
    if 'postMessage' in content and 'addEventListener' in content:
        if "'*'" in content or '"*"' in content:
            issues.append({
                'name': 'Unsafe postMessage with wildcard origin',
                'severity': 'high',
                'category': 'xss',
                'remediation': 'Specify explicit origin in postMessage event listener.',
            })
        if 'event.origin' not in content and 'messageEvent.origin' not in content:
            issues.append({
                'name': 'postMessage without origin check',
                'severity': 'medium',
                'category': 'xss',
                'remediation': 'Always validate event.origin in message event handlers.',
            })
    return issues


def scan_for_prototype_pollution(content: str) -> list:
    """Scan for JavaScript prototype pollution risks."""
    issues = []
    patterns = [
        (r'Object\.assign\s*\(\s*\{\}', 'Object.assign on empty object — possible pollution'),
        (r'\.\.\.([^)]+)\)\s*,\s*\{', 'Spread operator with mutable merge'),
        (r'deepMerge|deepExtend|deepCopy', 'Deep merge function — potential prototype pollution'),
        (r'__proto__|constructor\[', 'Direct prototype access'),
        (r'JSON\.parse\s*\(', 'Unvalidated JSON parse — possible injection'),
    ]
    for pattern, name in patterns:
        if re.search(pattern, content):
            issues.append({
                'name': name,
                'severity': 'medium',
                'category': 'injection',
                'remediation': 'Sanitize inputs before deep merging. Use Object.create(null) for safe objects.',
            })
    return issues


def scan_for_idor_risks(content: str, language: str) -> list:
    """Scan for potential Insecure Direct Object Reference risks."""
    issues = []
    if language in ('Python', 'JavaScript', 'TypeScript', 'Ruby', 'PHP', 'Java'):
        patterns = [
            (r'(?:get|fetch|find)_by_id\s*\(\s*(?:request|req|params|args)\b', 'IDOR: Using user-controlled ID in database query'),
            (r'Object\.get\(\s*(?:request|req|params|args)\b', 'IDOR: Direct object access with user input'),
            (r'(?:SELECT|UPDATE|DELETE).*WHERE.*id\s*=\s*(?:request|req|params)\b', 'IDOR: SQL with user-controlled ID'),
        ]
        for pattern, name in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append({
                    'name': name,
                    'severity': 'high',
                    'category': 'idor',
                    'remediation': 'Validate user authorization before accessing objects by ID.',
                })
    return issues


def scan_for_mass_assignment(content: str, language: str) -> list:
    """Scan for mass assignment vulnerabilities."""
    issues = []
    if language in ('Python', 'JavaScript', 'TypeScript', 'Ruby', 'PHP'):
        patterns = [
            (r'Model\.objects\.create\s*\(\s*(?:request|req|params)\b', 'Mass assignment: Creating model from request directly'),
            (r'\.update\s*\(\s*(?:request|req|params|body)\b', 'Mass assignment: Updating with unsanitized request'),
            (r'Model\.save\s*\(\s*(?:request|req|params)\b', 'Mass assignment: Saving model from request'),
        ]
        for pattern, name in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append({
                    'name': name,
                    'severity': 'high',
                    'category': 'mass_assignment',
                    'remediation': 'Use explicit field whitelisting when creating/updating models from request data.',
                })
    return issues


def scan_for_header_security(content: str) -> list:
    """Scan for missing or insecure HTTP headers."""
    issues = []
    insecure_headers = [
        (r'Access-Control-Allow-Origin.*\*', 'CORS wildcard origin'),
        (r'X-Frame-Options.*ALLOWALL|X-Frame-Options.*sameorigin.*always', 'Clickjacking risk'),
        (r'Content-Security-Policy.*unsafe-inline|unsafe-eval', 'Weak CSP policy'),
        (r'X-Powered-By', 'Server technology disclosure'),
        (r'Server:.*Apache|Server:.*nginx|Server:.*Express', 'Server version disclosure'),
    ]
    for pattern, name in insecure_headers:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append({
                'name': name,
                'severity': 'medium',
                'category': 'headers',
                'remediation': 'Review security headers. Use security-focused middleware.',
            })
    
    # Check for missing headers
    recommended_headers = [
        'X-Content-Type-Options', 'X-Frame-Options', 'Content-Security-Policy',
        'Strict-Transport-Security', 'Referrer-Policy', 'Permissions-Policy',
    ]
    for header in recommended_headers:
        if header not in content:
            issues.append({
                'name': f'Missing security header: {header}',
                'severity': 'low',
                'category': 'headers',
                'remediation': f'Add {header} header to improve security posture.',
            })
    
    return issues


def scan_for_open_redirects(content: str) -> list:
    """Scan for potential open redirect vulnerabilities."""
    issues = []
    patterns = [
        (r'(?:redirect|redirectToRoute|HttpResponseRedirect)\s*\(\s*(?:request|req)\b', 
         'Open redirect: Redirecting based on user input'),
        (r'window\.location\s*=\s*(?:request|params|url|location)\b',
         'Open redirect: Client-side redirect with user input'),
        (r'response\.redirect\s*\(\s*(?:req\.query|req\.params|request)',
         'Open redirect: Express redirect with query params'),
    ]
    for pattern, name in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append({
                'name': name,
                'severity': 'medium',
                'category': 'redirect',
                'remediation': 'Whitelist allowed redirect URLs instead of using user input directly.',
            })
    return issues
