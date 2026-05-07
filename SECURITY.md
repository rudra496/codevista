# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of CodeVista seriously. If you believe you have found a
security vulnerability, please report it responsibly.

### How to Report

1. **Do not** open a public issue for the vulnerability.
2. Send an email to security@rudra496.dev or report via GitHub's [private vulnerability reporting](https://github.com/rudra496/codevista/security/advisories/new) with the subject line
   `[Security] CodeVista Vulnerability Report`.
3. Include as much information as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- We will acknowledge receipt of your report within **48 hours**.
- We will provide an initial assessment within **7 business days**.
- We will keep you updated on the progress of the fix.
- If the vulnerability is accepted, we will release a fix as soon as possible.

### Disclosure Policy

- We follow **Coordinated Disclosure** — we will work with you to determine a
  timeline for public disclosure.
- Credit will be given to the reporter (unless anonymity is requested).
- We will not disclose the vulnerability publicly until a fix is released.

## Security Best Practices

When using CodeVista, follow these best practices:

### Input Files
- Only analyze codebases you trust or have permission to analyze.
- CodeVista reads source files — be aware of what you're pointing it at.

### Output Files
- HTML reports contain code excerpts — do not share reports publicly if the
  codebase contains sensitive information.
- JSON exports may contain security findings — handle with care.

### Snapshots
- Snapshots are stored in `~/.codevista/snapshots/` — they contain analysis
  metadata but not source code content.
- Review snapshot content before sharing.

### CI/CD Integration
- SARIF output may contain file paths and line numbers from your codebase.
- Ensure CI/CD logs are properly secured if your codebase is private.

## Security Features

CodeVista itself includes security scanning capabilities:

- **Secret Detection**: Identifies hardcoded API keys, passwords, tokens
- **Dangerous Function Detection**: Flags `eval()`, `exec()`, `pickle`, etc.
- **Private Key Detection**: Finds private keys committed to source

These features help you secure **your** codebase, not CodeVista itself.
