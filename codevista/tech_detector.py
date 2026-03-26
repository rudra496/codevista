"""Technology detection with confidence scoring.

Detects frameworks, databases, ORMs, containers, CI/CD, cloud services,
testing frameworks, linting tools, build tools, and package managers.
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple


def detect_tech_stack(project_path: str) -> Dict:
    """Detect the full technology stack of a project.

    Returns dict with categories: frameworks, databases, orm, containers,
    cicd, cloud, testing, linting, build_tools, package_managers.
    Each category has a list of {'name': str, 'confidence': str, 'evidence': list}.
    """
    result: Dict = {
        'frameworks': [], 'databases': [], 'orm': [], 'containers': [],
        'cicd': [], 'cloud': [], 'testing': [], 'linting': [],
        'build_tools': [], 'package_managers': [], 'languages_runtime': [],
    }

    # Read config/lock files
    file_contents: Dict[str, str] = {}
    files_to_check = [
        'package.json', 'requirements.txt', 'pyproject.toml', 'Pipfile',
        'Pipfile.lock', 'Cargo.toml', 'go.mod', 'Gemfile', 'Gemfile.lock',
        'pom.xml', 'build.gradle', 'build.gradle.kts', 'composer.json',
        'docker-compose.yml', 'docker-compose.yaml', 'Dockerfile',
        '.github/workflows/ci.yml', '.travis.yml', '.circleci/config.yml',
        '.gitlab-ci.yml', 'Jenkinsfile', 'Makefile', 'CMakeLists.txt',
        '.eslintrc', '.eslintrc.json', '.eslintrc.js', '.prettierrc',
        '.pylintrc', 'setup.cfg', 'tox.ini', 'pytest.ini',
        '.env', '.env.example', 'terraform.tf', 'serverless.yml',
        '.github/workflows/test.yml', '.github/workflows/build.yml',
        'angular.json', 'vue.config.js', 'svelte.config.js', 'next.config.js',
        'tsconfig.json', 'webpack.config.js', 'vite.config.js', 'vite.config.ts',
        'tailwind.config.js', 'tailwind.config.ts',
        'manage.py', 'gunicorn.conf.py', 'celeryconfig.py',
        'database.yml', 'knexfile.js', 'sequelize.js',
        'samconfig.toml', 'template.yaml', 'serverless.yml',
    ]

    for fname in files_to_check:
        fpath = os.path.join(project_path, fname)
        if os.path.isfile(fpath):
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    file_contents[fname] = f.read()
            except OSError:
                pass

    # Also check all GitHub Actions workflows
    gh_actions_dir = os.path.join(project_path, '.github', 'workflows')
    if os.path.isdir(gh_actions_dir):
        for wf in os.listdir(gh_actions_dir):
            fpath = os.path.join(gh_actions_dir, wf)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, 'r', errors='ignore') as f:
                        file_contents[f'.github/workflows/{wf}'] = f.read()
                except OSError:
                    pass

    # ── Framework Detection ──────────────────────────────────────────────────

    # Python frameworks
    if 'requirements.txt' in file_contents:
        reqs = file_contents['requirements.txt'].lower()
        _check_markers(reqs, result['frameworks'], [
            ('django', 'Django', 0.9), ('flask', 'Flask', 0.9),
            ('fastapi', 'FastAPI', 0.9), ('starlette', 'Starlette', 0.85),
            ('tornado', 'Tornado', 0.8), ('pyramid', 'Pyramid', 0.8),
            ('celery', 'Celery', 0.85), ('sanic', 'Sanic', 0.8),
            ('aiohttp', 'aiohttp', 0.8), ('falcon', 'Falcon', 0.8),
            ('bottle', 'Bottle', 0.75), ('cherrypy', 'CherryPy', 0.75),
            ('web2py', 'Web2Py', 0.7), ('dash', 'Dash', 0.8),
            ('streamlit', 'Streamlit', 0.85), ('gradio', 'Gradio', 0.85),
            ('plotly', 'Plotly', 0.7), ('selenium', 'Selenium', 0.7),
        ])

    if 'pyproject.toml' in file_contents:
        pyproject = file_contents['pyproject.toml'].lower()
        _check_markers(pyproject, result['frameworks'], [
            ('django', 'Django', 0.9), ('flask', 'Flask', 0.9),
            ('fastapi', 'FastAPI', 0.9), ('celery', 'Celery', 0.85),
        ])

    if 'manage.py' in file_contents:
        result['frameworks'].append({'name': 'Django', 'confidence': 'high',
                                      'evidence': ['manage.py found']})

    if 'celeryconfig.py' in file_contents or 'gunicorn.conf.py' in file_contents:
        result['frameworks'].append({'name': 'Celery/Gunicorn', 'confidence': 'high',
                                      'evidence': ['config file found']})

    # JavaScript/TypeScript frameworks
    if 'package.json' in file_contents:
        try:
            pkg = json.loads(file_contents['package.json'])
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            all_lower = {k.lower(): v for k, v in deps.items()}

            _check_markers_dict(all_lower, result['frameworks'], [
                ('react', 'React', 0.95), ('vue', 'Vue.js', 0.95),
                ('angular', 'Angular', 0.95), ('next', 'Next.js', 0.9),
                ('nuxt', 'Nuxt.js', 0.9), ('svelte', 'Svelte', 0.95),
                ('express', 'Express', 0.9), ('fastify', 'Fastify', 0.85),
                ('koa', 'Koa', 0.85), ('nestjs', 'NestJS', 0.9),
                ('meteor', 'Meteor', 0.85), ('hapi', 'hapi', 0.8),
                ('gatsby', 'Gatsby', 0.85), ('remix', 'Remix', 0.85),
                ('astro', 'Astro', 0.85), ('vite', 'Vite', 0.85),
                ('webpack', 'Webpack', 0.8), ('rollup', 'Rollup', 0.75),
                ('esbuild', 'esbuild', 0.8), ('turbo', 'Turborepo', 0.75),
            ])

            # Testing
            _check_markers_dict(all_lower, result['testing'], [
                ('jest', 'Jest', 0.95), ('mocha', 'Mocha', 0.9),
                ('vitest', 'Vitest', 0.9), ('cypress', 'Cypress', 0.9),
                ('playwright', 'Playwright', 0.9), ('puppeteer', 'Puppeteer', 0.85),
                ('chai', 'Chai', 0.85), ('sinon', 'Sinon', 0.85),
                ('testing-library', 'Testing Library', 0.85),
                ('@testing-library/react', 'Testing Library', 0.9),
                ('ava', 'AVA', 0.8), ('tape', 'Tape', 0.75),
                ('karma', 'Karma', 0.75),
            ])

            # Linting
            _check_markers_dict(all_lower, result['linting'], [
                ('eslint', 'ESLint', 0.95), ('prettier', 'Prettier', 0.95),
                ('stylelint', 'Stylelint', 0.85), ('tslint', 'TSLint', 0.85),
                ('biome', 'Biome', 0.85), ('oxlint', 'oxlint', 0.8),
            ])

        except (json.JSONDecodeError, KeyError):
            pass

    if 'angular.json' in file_contents:
        result['frameworks'].append({'name': 'Angular', 'confidence': 'high',
                                      'evidence': ['angular.json found']})
    if 'next.config.js' in file_contents or 'next.config.mjs' in file_contents:
        result['frameworks'].append({'name': 'Next.js', 'confidence': 'high',
                                      'evidence': ['next.config found']})
    if 'vue.config.js' in file_contents:
        result['frameworks'].append({'name': 'Vue.js', 'confidence': 'high',
                                      'evidence': ['vue.config.js found']})
    if 'svelte.config.js' in file_contents:
        result['frameworks'].append({'name': 'Svelte', 'confidence': 'high',
                                      'evidence': ['svelte.config.js found']})

    # Python testing
    if 'requirements.txt' in file_contents:
        reqs = file_contents['requirements.txt'].lower()
        _check_markers(reqs, result['testing'], [
            ('pytest', 'pytest', 0.95), ('unittest', 'unittest', 0.8),
            ('nose', 'nose', 0.8), ('hypothesis', 'Hypothesis', 0.85),
            ('tox', 'tox', 0.8), ('mypy', 'mypy', 0.85),
        ])
        _check_markers(reqs, result['linting'], [
            ('pylint', 'Pylint', 0.9), ('flake8', 'Flake8', 0.9),
            ('black', 'Black', 0.9), ('ruff', 'Ruff', 0.9),
            ('isort', 'isort', 0.85), ('mypy', 'mypy', 0.85),
            ('pyright', 'Pyright', 0.85), ('bandit', 'Bandit', 0.85),
            ('sphinx', 'Sphinx', 0.8),
        ])

    # Other frameworks
    if 'Gemfile' in file_contents:
        gemfile = file_contents['Gemfile'].lower()
        _check_markers(gemfile, result['frameworks'], [
            ('rails', 'Ruby on Rails', 0.95), ('sinatra', 'Sinatra', 0.85),
            ('hanami', 'Hanami', 0.8), ('roda', 'Roda', 0.75),
        ])
        _check_markers(gemfile, result['testing'], [
            ('rspec', 'RSpec', 0.9), ('minitest', 'Minitest', 0.9),
            ('capybara', 'Capybara', 0.85),
        ])

    if 'Cargo.toml' in file_contents:
        result['package_managers'].append({'name': 'Cargo', 'confidence': 'high',
                                            'evidence': ['Cargo.toml found']})
        result['frameworks'].append({'name': 'Rust', 'confidence': 'high',
                                      'evidence': ['Cargo.toml found']})

    if 'go.mod' in file_contents:
        result['package_managers'].append({'name': 'Go Modules', 'confidence': 'high',
                                            'evidence': ['go.mod found']})
        gomod = file_contents['go.mod'].lower()
        _check_markers(gomod, result['frameworks'], [
            ('gin', 'Gin', 0.85), ('echo', 'Echo', 0.85),
            ('fiber', 'Fiber', 0.85), ('chi', 'Chi', 0.8),
        ])

    if 'pom.xml' in file_contents:
        result['frameworks'].append({'name': 'Spring/Java', 'confidence': 'medium',
                                      'evidence': ['pom.xml found']})
        result['package_managers'].append({'name': 'Maven', 'confidence': 'high',
                                            'evidence': ['pom.xml found']})
        result['testing'].append({'name': 'JUnit', 'confidence': 'medium',
                                   'evidence': ['pom.xml found']})

    if 'build.gradle' in file_contents or 'build.gradle.kts' in file_contents:
        result['frameworks'].append({'name': 'Gradle/Java/Kotlin', 'confidence': 'medium',
                                      'evidence': ['build.gradle found']})
        result['package_managers'].append({'name': 'Gradle', 'confidence': 'high',
                                            'evidence': ['build.gradle found']})

    if 'composer.json' in file_contents:
        result['frameworks'].append({'name': 'Laravel/PHP', 'confidence': 'medium',
                                      'evidence': ['composer.json found']})
        result['package_managers'].append({'name': 'Composer', 'confidence': 'high',
                                            'evidence': ['composer.json found']})

    # ── Database Detection ───────────────────────────────────────────────────

    all_text = '\n'.join(file_contents.values()).lower()
    _check_markers(all_text, result['databases'], [
        ('postgresql', 'PostgreSQL', 0.85), ('postgres', 'PostgreSQL', 0.85),
        ('mysql', 'MySQL', 0.85), ('mariadb', 'MariaDB', 0.8),
        ('sqlite', 'SQLite', 0.85), ('mongodb', 'MongoDB', 0.85),
        ('mongo', 'MongoDB', 0.8), ('redis', 'Redis', 0.85),
        ('elasticsearch', 'Elasticsearch', 0.8),
        ('cassandra', 'Cassandra', 0.8), ('dynamodb', 'DynamoDB', 0.8),
        ('couchdb', 'CouchDB', 0.75), ('neo4j', 'Neo4j', 0.75),
        ('firestore', 'Firestore', 0.8),
    ])

    # Database files
    if os.path.isfile(os.path.join(project_path, 'database.yml')):
        result['databases'].append({'name': 'PostgreSQL/MySQL', 'confidence': 'medium',
                                     'evidence': ['database.yml found']})

    # ── ORM Detection ────────────────────────────────────────────────────────

    _check_markers(all_text, result['orm'], [
        ('sqlalchemy', 'SQLAlchemy', 0.9), ('django.db', 'Django ORM', 0.9),
        ('prisma', 'Prisma', 0.9), ('typeorm', 'TypeORM', 0.9),
        ('sequelize', 'Sequelize', 0.85), ('mongoose', 'Mongoose', 0.85),
        ('activerecord', 'ActiveRecord', 0.9), ('gorm', 'GORM', 0.85),
        ('sqlmodel', 'SQLModel', 0.85), ('peewee', 'Peewee', 0.8),
        ('tortoise', 'Tortoise ORM', 0.8), ('asyncpg', 'asyncpg', 0.75),
    ])

    # ── Container Detection ──────────────────────────────────────────────────

    if 'Dockerfile' in file_contents:
        result['containers'].append({'name': 'Docker', 'confidence': 'high',
                                      'evidence': ['Dockerfile found']})
    if 'docker-compose.yml' in file_contents or 'docker-compose.yaml' in file_contents:
        result['containers'].append({'name': 'Docker Compose', 'confidence': 'high',
                                      'evidence': ['docker-compose found']})

    # Check for Kubernetes manifests
    k8s_patterns = ['apiVersion', 'kind: Deployment', 'kind: Service', 'kind: ConfigMap']
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules')]
        for f in files:
            if f.endswith(('.yml', '.yaml')):
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, 'r', errors='ignore') as fh:
                        content = fh.read()
                    if any(p in content for p in k8s_patterns):
                        result['containers'].append({'name': 'Kubernetes', 'confidence': 'high',
                                                      'evidence': [f]})
                        break
                except OSError:
                    pass

    # ── CI/CD Detection ──────────────────────────────────────────────────────

    for fname, name in [('.github/workflows/ci.yml', 'GitHub Actions'),
                        ('.github/workflows/test.yml', 'GitHub Actions'),
                        ('.github/workflows/build.yml', 'GitHub Actions'),
                        ('.travis.yml', 'Travis CI'),
                        ('.circleci/config.yml', 'CircleCI'),
                        ('.gitlab-ci.yml', 'GitLab CI'),
                        ('Jenkinsfile', 'Jenkins')]:
        if fname in file_contents:
            _add_unique(result['cicd'], name, 'high', [fname])
            break

    # Check for any GitHub Actions workflow
    for key in file_contents:
        if key.startswith('.github/workflows/'):
            _add_unique(result['cicd'], 'GitHub Actions', 'high', [key])

    # ── Cloud Detection ─────────────────────────────────────────────────────

    _check_markers(all_text, result['cloud'], [
        ('aws', 'AWS', 0.7), ('amazon', 'AWS', 0.6),
        ('google.cloud', 'GCP', 0.7), ('gcp', 'GCP', 0.65),
        ('azure', 'Azure', 0.65),
        ('cloudflare', 'Cloudflare', 0.75),
        ('vercel', 'Vercel', 0.8), ('netlify', 'Netlify', 0.8),
        ('heroku', 'Heroku', 0.75), ('railway', 'Railway', 0.7),
        ('fly.io', 'Fly.io', 0.75), ('digitalocean', 'DigitalOcean', 0.7),
        ('linode', 'Linode', 0.65), ('terraform', 'Terraform', 0.8),
        ('pulumi', 'Pulumi', 0.8), ('serverless', 'Serverless Framework', 0.8),
        ('samconfig', 'AWS SAM', 0.85), ('cdk', 'AWS CDK', 0.8),
    ])

    # Cloud config files
    if 'serverless.yml' in file_contents or 'serverless.yaml' in file_contents:
        _add_unique(result['cloud'], 'Serverless Framework', 'high', ['serverless.yml'])
    if 'terraform.tf' in file_contents:
        _add_unique(result['cloud'], 'Terraform', 'high', ['terraform.tf'])

    # ── Build Tools ──────────────────────────────────────────────────────────

    if 'Makefile' in file_contents:
        result['build_tools'].append({'name': 'Make', 'confidence': 'high',
                                       'evidence': ['Makefile found']})
    if 'CMakeLists.txt' in file_contents:
        result['build_tools'].append({'name': 'CMake', 'confidence': 'high',
                                       'evidence': ['CMakeLists.txt found']})
    if 'webpack.config.js' in file_contents:
        result['build_tools'].append({'name': 'Webpack', 'confidence': 'high',
                                       'evidence': ['webpack.config.js found']})
    if 'vite.config.js' in file_contents or 'vite.config.ts' in file_contents:
        result['build_tools'].append({'name': 'Vite', 'confidence': 'high',
                                       'evidence': ['vite.config found']})
    if 'rollup.config.js' in file_contents:
        result['build_tools'].append({'name': 'Rollup', 'confidence': 'high',
                                       'evidence': ['rollup.config.js found']})
    if 'tsconfig.json' in file_contents:
        result['build_tools'].append({'name': 'TypeScript', 'confidence': 'high',
                                       'evidence': ['tsconfig.json found']})

    # ── Package Managers ────────────────────────────────────────────────────

    if 'requirements.txt' in file_contents:
        _add_unique(result['package_managers'], 'pip', 'high', ['requirements.txt'])
    if 'Pipfile' in file_contents:
        _add_unique(result['package_managers'], 'Pipenv', 'high', ['Pipfile'])
    if 'pyproject.toml' in file_contents:
        pyproject_lower = file_contents['pyproject.toml'].lower()
        if 'poetry' in pyproject_lower:
            _add_unique(result['package_managers'], 'Poetry', 'high', ['pyproject.toml'])
        else:
            _add_unique(result['package_managers'], 'pip (PEP 621)', 'high', ['pyproject.toml'])
    if 'conda' in all_text:
        result['package_managers'].append({'name': 'Conda', 'confidence': 'medium',
                                            'evidence': ['conda reference found']})
    if 'package.json' in file_contents:
        try:
            pkg = json.loads(file_contents['package.json'])
            pm = 'yarn' if os.path.isfile(os.path.join(project_path, 'yarn.lock')) else \
                 'pnpm' if os.path.isfile(os.path.join(project_path, 'pnpm-lock.yaml')) else 'npm'
            _add_unique(result['package_managers'], pm, 'high', ['package.json'])
        except (json.JSONDecodeError, KeyError):
            _add_unique(result['package_managers'], 'npm', 'high', ['package.json'])

    # Remove duplicates and deduplicate across categories
    for cat in result:
        result[cat] = _deduplicate(result[cat])

    return result


def _check_markers(text: str, target_list: list, markers: List[Tuple[str, str, float]]):
    """Check text for markers and add to target list."""
    for pattern, name, confidence in markers:
        if pattern in text:
            target_list.append({
                'name': name,
                'confidence': _confidence_label(confidence),
                'evidence': [f'Found "{pattern}"'],
            })


def _check_markers_dict(deps: dict, target_list: list,
                        markers: List[Tuple[str, str, float]]):
    """Check dependency dict keys for markers."""
    for pattern, name, confidence in markers:
        if pattern in deps:
            target_list.append({
                'name': name,
                'confidence': _confidence_label(confidence),
                'evidence': [f'Dependency: {pattern} ({deps[pattern]})'],
            })


def _confidence_label(confidence: float) -> str:
    """Convert numeric confidence to label."""
    if confidence >= 0.85:
        return 'high'
    elif confidence >= 0.65:
        return 'medium'
    return 'low'


def _add_unique(lst: list, name: str, confidence: str, evidence: list):
    """Add item to list if not already present by name."""
    if not any(item['name'] == name for item in lst):
        lst.append({'name': name, 'confidence': confidence, 'evidence': evidence})


def _deduplicate(lst: list) -> list:
    """Remove duplicate entries by name, keeping highest confidence."""
    seen: Dict[str, dict] = {}
    rank = {'high': 3, 'medium': 2, 'low': 1}
    for item in lst:
        name = item['name']
        if name not in seen or rank.get(item['confidence'], 0) > rank.get(seen[name]['confidence'], 0):
            seen[name] = item
    return sorted(seen.values(), key=lambda x: -rank.get(x['confidence'], 0))
