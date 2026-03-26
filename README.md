<p align="center">
  <pre>
 ██████╗ ██████╗ ███╗   ██╗ ██████╗ ███████╗██╗ ██████╗ ██╗  ██╗████████╗
██╔═══██╗██╔══██╗████╗  ██║██╔════╝ ██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝
██║   ██║██████╔╝██╔██╗ ██║██║  ███╗███████╗██║██║  ███╗███████║   ██║
██║   ██║██╔══██╗██║╚██╗██║██║   ██║╚════██║██║██║   ██║██╔══██║   ██║
╚██████╔╝██║  ██║██║ ╚████║╚██████╔╝███████║██║╚██████╔╝██║  ██║   ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
  </pre>
</p>

<h3 align="center"><strong>Google Analytics for your code</strong></h3>
<p align="center">
  Beautiful interactive codebase visualizations — single HTML, zero dependencies.
</p>

---

## ✨ What is CodeVista?

CodeVista analyzes your codebase and generates a **stunning single-page HTML report** — no server, no internet, no external dependencies. Just share one file and everyone can explore your code visually.

## 🚀 Quick Start

```bash
pip install codevista
codevista analyze ./my-project/
```

That's it. Open `report.html` in any browser. No server needed.

## 📦 Installation

```bash
pip install codevista
```

Zero external dependencies — pure Python stdlib.

## 🎯 Commands

| Command | Description |
|---------|-------------|
| `codevista analyze ./project/` | Full analysis with all features |
| `codevista analyze ./project/ -o report.html` | Custom output path |
| `codevista analyze ./project/ --no-git` | Skip git analysis |
| `codevista analyze ./project/ --depth 3` | Limit directory depth |
| `codevista quick ./project/` | Fast analysis (~3 seconds) |
| `codevista serve ./project/ --port 8080` | Serve report on HTTP server |
| `codevista compare ./v1/ ./v2/` | Compare two codebases |
| `codevista watch ./project/` | Re-analyze on file changes |
| `codevista smells ./project/` | Detect code smells and anti-patterns |
| `codevista architecture ./project/` | Detect architecture patterns |
| `codevista code-age ./project/` | Analyze file age, churn, and risk |
| `codevista export ./project/ -f sarif` | Export as SARIF for CI |
| `codevista export ./project/ --all` | Export to all formats |
| `codevista health ./project/` | Health score only |
| `codevista security ./project/` | Security scan only |
| `codevista deps ./project/` | Dependency analysis |
| `codevista git-stats ./project/` | Git repository statistics |
| `codevista languages ./project/` | Language distribution breakdown |
| `codevista complexity ./project/` | Complexity analysis and top functions |

## 📊 What It Analyzes

### 🏗️ Architecture Map
- File dependency graph — who imports whom
- Interactive directory tree with line counts
- Module cluster detection

### 📈 Code Metrics
- Lines of code per file (interactive bar chart)
- Cyclomatic complexity (hot spot detection)
- Code duplication detection (hash-based)
- Comment coverage tracking
- File size distribution

### 🧩 Technology Detection
- Language detection (50+ languages)
- Framework detection (React, Django, Flask, Express, etc.)
- Dependency inventory with versions

### 🏥 Health Score
- Overall health: 0-100 (composite score)
- Per-category: readability, complexity, duplication, coverage, security, dependencies
- Color-coded indicators (green/yellow/red)
- Specific improvement recommendations

### 🔒 Security Scan
- Hardcoded secrets (AWS, GitHub, Stripe, API keys, passwords, tokens)
- Dangerous functions (eval, exec, shell=True, pickle)
- Private key detection
- Severity scoring (critical/high/medium/low)

### 👥 Git Insights
- Contribution heatmap (52-week calendar)
- Top contributors with commit share
- Most active files
- Commit statistics

### 👃 Code Smell Detection
CodeVista detects **19 categories of code smells** that go beyond typical linters:

| Smell | Description |
|-------|-------------|
| **God Classes** | Classes with too many methods/fields/responsibilities |
| **Long Parameter Lists** | Functions with too many params, especially with `=None` |
| **Feature Envy** | Methods using another class's data more than their own |
| **Divergent Change** | Classes modified for multiple unrelated reasons |
| **Shotgun Surgery** | Single logical change requiring edits across many files |
| **Parallel Inheritance** | Adding a subclass of A always requires subclassing B |
| **Speculative Generality** | Unused abstractions, abstract methods never overridden |
| **Temporary Fields** | Instance variables set only in certain methods |
| **Message Chains** | Long dot chains: `a.b.c.d.e.f` |
| **Middle Man** | Classes that only delegate to another class |
| **Comment Smells** | Comments describing WHAT code does, not WHY |
| **Dead Code** | Variables assigned but never read, functions never called |
| **Magic Numbers** | Unnamed numeric literals scattered in code |
| **Copy-Paste Code** | Near-duplicate blocks within and across files |
| **Missing Error Handling** | I/O operations without try/catch or error checks |
| **Inconsistent Naming** | Mixing camelCase and snake_case conventions |
| **Boolean Parameters** | Flags indicating method should be split |
| **isinstance Chains** | Type checking chains suggesting missing polymorphism |

Each smell comes with severity, location, and **actionable remediation advice**.

```bash
codevista smells ./my-project/
```

### 🏗️ Architecture Pattern Detection
Automatically identifies architectural patterns from project structure and code:

- **MVC / MVVM / MVP** — UI patterns
- **Layered Architecture** — presentation, business, data layers
- **Clean Architecture** — entities, use cases, controllers, adapters
- **Hexagonal** — ports & adapters pattern
- **Repository Pattern** — data access mediation
- **Service Layer** — application boundary with coordinating operations
- **CQRS** — command/query separation
- **Event-Driven** — event publishers, subscribers, handlers
- **Microservices** — independent service architecture
- **Singleton / Factory / Strategy / Observer / Decorator** — design patterns
- **Dependency Injection** — DI framework and manual injection

Includes architecture quality scoring (organization, coupling, modularity, balance) and text-based architecture diagrams.

```bash
codevista architecture ./my-project/
```

### 📅 Code Age & Risk Analysis
Track file age, change frequency, and identify files most likely to have bugs:

| Category | Description |
|----------|-------------|
| 🔥 **Hot** | Changed in the last 7 days |
| 🌤️ **Warm** | Changed in the last 30 days |
| ❄️ **Cold** | Changed 30-365 days ago |
| 🧊 **Cold Stable** | Old but few changes (stable) |
| 💀 **Dead** | Unchanged for >1 year |

**Risk Analysis** correlates age × complexity × churn to identify the files most likely to contain bugs:
- Files with high age, high complexity, and high change frequency get the highest risk scores
- Statistical correlation analysis between age, complexity, and churn
- Actionable recommendations for high-risk files

```bash
codevista code-age ./my-project/
```

## 📤 Export Formats

Export analysis results in multiple formats for different use cases:

| Format | Use Case | Command |
|--------|----------|---------|
| **HTML** | Interactive report in browser | `codevista export . -f html` |
| **JSON** | Programmatic access, APIs | `codevista export . -f json` |
| **Markdown** | Documentation, READMEs, wikis | `codevista export . -f markdown` |
| **SARIF** | GitHub Code Scanning, CI/CD | `codevista export . -f sarif` |
| **CSV** | Spreadsheets, data analysis | `codevista export . -f csv` |
| **YAML** | CODE_METRICS format | `codevista export . -f yaml` |
| **PDF** | Printable reports | `codevista export . -f pdf` |
| **All formats** | Everything at once | `codevista export . --all` |

```bash
# CI integration with GitHub Code Scanning
codevista export ./project/ -f sarif -o results.sarif.json

# Export everything
codevista export ./project/ -o ./reports/codevista --all
```

## 🐳 Docker

```bash
# Build
docker build -t codevista .

# Analyze a project
docker run --rm -v $(pwd):/workspace codevista analyze /workspace

# Use docker-compose
docker-compose up
```

The Docker image uses multi-stage builds for minimal size, runs as non-root, and includes `wkhtmltopdf` for PDF export.

## 🎨 Report Features

- **Single HTML file** — share anywhere, works offline forever
- **Dark/light mode** toggle
- **Interactive tables** — sort by any column, filter by language, search
- **Inline SVG charts** — no external JS libraries
- **Collapsible sections**
- **Print-friendly**
- **Responsive** — works on mobile

## 🏆 Comparison

| Feature | CodeVista | SonarQube | CodeClimate | lizard |
|---------|-----------|-----------|-------------|--------|
| Setup | `pip install` | Docker/Server | SaaS | `pip install` |
| Dependencies | **Zero** | Heavy | None | None |
| Output | **Single HTML** | Web UI | Web UI | CLI |
| Offline | ✅ | ❌ | ❌ | N/A |
| Security scan | ✅ | ✅ | ✅ | ❌ |
| Git analysis | ✅ | ✅ | ✅ | ❌ |
| Visual charts | ✅ | ✅ | ✅ | ❌ |
| Code smell detection | ✅ **19 types** | Limited | Limited | ❌ |
| Architecture patterns | ✅ **12+ patterns** | ❌ | ❌ | ❌ |
| Code age analysis | ✅ | ❌ | ❌ | ❌ |
| SARIF export | ✅ | ✅ | ✅ | ❌ |
| Cost | **Free** | Free/Paid | Paid | Free |
| Server needed | **No** | Yes | Yes | No |

## 💎 What Makes CodeVista Unique

1. **Zero dependencies** — pure Python stdlib, no pip install headaches
2. **Single HTML output** — share one file, works offline forever, no server
3. **Deep code smell detection** — 19 smell categories with AST-level analysis, not just regex
4. **Architecture pattern detection** — identifies 12+ patterns from structure + code
5. **Code age × risk correlation** — statistical analysis of age, complexity, and churn
6. **Multi-format export** — HTML, JSON, Markdown, SARIF, CSV, YAML, PDF
7. **Docker support** — multi-stage build, non-root user, PDF-ready
8. **Beautiful design** — dark mode, glassmorphism, inline SVG charts, animations
9. **Works on any codebase** — 50+ languages, no configuration needed
10. **CI/CD ready** — SARIF export for GitHub Code Scanning integration

## 🏗️ Architecture

```
codevista/
├── cli.py            # CLI interface (argparse)
├── analyzer.py       # Core analysis engine
├── report.py         # HTML report generator
├── metrics.py        # Health scores & recommendations
├── smells.py         # Code smell detection (19 categories)
├── architecture.py   # Architecture pattern detector
├── code_age.py       # Code age & risk analysis
├── export.py         # Multi-format export (HTML/JSON/MD/SARIF/CSV/YAML/PDF)
├── security.py       # Secret/vulnerability scanning
├── dependencies.py   # Dependency parsing & analysis
├── git_analysis.py   # Git stats extraction
├── languages.py      # Language definitions & colors
├── config.py         # Configuration & ignore patterns
├── utils.py          # Utilities & color schemes
└── templates/        # HTML templates
```

## 🛠️ Tech Stack

- **Python 3.7+** (stdlib only)
- **Inline SVG** for all charts
- **CSS custom properties** for theming
- **Vanilla JavaScript** for interactivity
- **AST parsing** for deep code analysis (Python)

## 🤝 Contributing

1. Fork it
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

MIT © 2026 — see [LICENSE](LICENSE)
