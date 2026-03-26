"""Architectural Decay Detector — tracks code degradation over time."""

import subprocess
import os
import re
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class DecayDetector:
    """Analyzes how code quality degrades over time using git history."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.is_git = self._check_git()

    def _check_git(self) -> bool:
        """Check if directory is a git repo."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def _run_git(self, args: List[str]) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_file_at_commit(self, filepath: str, commit_hash: str) -> Optional[str]:
        """Get file content at a specific commit."""
        content = self._run_git(["show", f"{commit_hash}:{filepath}"])
        if content and not content.startswith("fatal:"):
            return content
        return None

    def _count_complexity(self, code: str) -> Dict:
        """Calculate cyclomatic complexity from code text."""
        if not code:
            return {"cyclomatic": 0, "cognitive": 0, "lines": 0, "functions": 0}
        lines = code.split("\n")
        total_lines = len(lines)
        decision_keywords = [
            r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
            r'\band\b', r'\bor\b', r'\bexcept\b', r'\bcase\b', r'\bcatch\b',
            r'\?\?', r'\?[^.]', r'&&', r'\|\|', r'\bwhen\b',
        ]
        cyclomatic = 1
        for line in lines:
            stripped = line.strip()
            for pattern in decision_keywords:
                cyclomatic += len(re.findall(pattern, stripped))
        func_pattern = r'(?:def|function|func|fn|sub|method)\s+\w+'
        functions = re.findall(func_pattern, code)
        num_functions = len(functions)
        cognitive = 0
        nesting = 0
        for line in lines:
            stripped = line.strip()
            nesting_increase = sum(
                1 for kw in ['if', 'for', 'while', 'elif', 'except', 'try', 'catch', 'switch', 'case']
                if re.search(rf'\b{kw}\b', stripped)
            )
            nesting_decrease = stripped.count('}') + stripped.count('end') + stripped.count('fi')
            cognitive += nesting_increase * (nesting + 1)
            nesting += nesting_increase - nesting_decrease
            nesting = max(0, nesting)
        return {
            "cyclomatic": cyclomatic,
            "cognitive": cognitive,
            "lines": total_lines,
            "functions": num_functions,
        }

    def _count_imports(self, code: str) -> List[str]:
        """Extract import/module references from code."""
        imports = []
        if not code:
            return imports
        patterns = [
            r'import\s+([\w.]+)',
            r'from\s+([\w.]+)\s+import',
            r'require\s*[("\']([\w./]+)',
            r'#include\s*[<"]([\w./]+)',
            r'use\s+([\w:]+)',
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, code))
        normalized = []
        for imp in imports:
            mod = imp.split(".")[0]
            mod = mod.split("/")[0]
            if mod and mod not in normalized:
                normalized.append(mod)
        return normalized

    def get_commit_history(self, since_days: int = 90) -> List[Dict]:
        """Get commit history with stats for the last N days."""
        since_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
        log = self._run_git([
            "log", f"--since={since_date}", "--pretty=format:%H|%ai|%an", "--numstat"
        ])
        commits = []
        current_commit = None
        for line in log.split("\n"):
            if "|" in line and line.count("|") >= 2:
                parts = line.split("|")
                if len(parts) == 3 and re.match(r'[0-9a-f]{40}', parts[0]):
                    current_commit = {
                        "hash": parts[0][:8], "date": parts[1].strip(),
                        "author": parts[2].strip(), "files": []
                    }
                    commits.append(current_commit)
            elif current_commit and line.strip():
                parts = line.split("\t")
                if len(parts) == 3:
                    try:
                        current_commit["files"].append({
                            "file": parts[2],
                            "added": int(parts[0]) if parts[0] != "-" else 0,
                            "removed": int(parts[1]) if parts[1] != "-" else 0,
                            "net": (int(parts[0]) if parts[0] != "-" else 0) -
                                   (int(parts[1]) if parts[1] != "-" else 0)
                        })
                    except ValueError:
                        pass
        return commits

    def _sample_commits(self, commits: List[Dict], max_samples: int = 10) -> List[Dict]:
        """Sample commits evenly across the time range."""
        if len(commits) <= max_samples:
            return commits
        step = len(commits) / max_samples
        sampled = [commits[int(i * step)] for i in range(max_samples)]
        if commits[-1] not in sampled:
            sampled[-1] = commits[-1]
        return sampled

    def _get_commits_for_file(self, filepath: str, since_days: int = 90) -> List[Dict]:
        """Get commits that touched a specific file."""
        all_commits = self.get_commit_history(since_days)
        return [c for c in all_commits if any(f["file"] == filepath for f in c["files"])]

    def analyze_file_complexity_over_time(self, filepath: str) -> List[Dict]:
        """Track complexity of a file across commits."""
        commits = self._get_commits_for_file(filepath)
        if not commits:
            return []
        sampled = self._sample_commits(commits, max_samples=12)
        timeline = []
        for commit in sampled:
            content = self._get_file_at_commit(filepath, commit["hash"])
            if content is not None:
                metrics = self._count_complexity(content)
                timeline.append({
                    "commit": commit["hash"], "date": commit["date"],
                    "author": commit["author"],
                    "cyclomatic": metrics["cyclomatic"], "cognitive": metrics["cognitive"],
                    "lines": metrics["lines"], "functions": metrics["functions"],
                })
        return timeline

    def calculate_coupling_growth(self) -> Dict:
        """Track how coupling between modules grows over time."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return {"timeline": [], "summary": {}, "most_coupled": []}
        sampled = self._sample_commits(commits, max_samples=12)
        timeline = []
        for commit in sampled:
            changed_files = [f["file"] for f in commit["files"] if f["file"]]
            module_imports = defaultdict(set)
            for filepath in changed_files:
                content = self._get_file_at_commit(filepath, commit["hash"])
                if content:
                    imports = self._count_imports(content)
                    module = filepath.split("/")[0] if "/" in filepath else filepath
                    for imp in imports:
                        module_imports[module].add(imp)
            coupling_values = []
            for module, deps in module_imports.items():
                external_deps = [d for d in deps if d != module and not d.startswith(".")]
                coupling_values.append(len(external_deps))
            avg_coupling = sum(coupling_values) / len(coupling_values) if coupling_values else 0
            max_coupling = max(coupling_values) if coupling_values else 0
            timeline.append({
                "commit": commit["hash"], "date": commit["date"],
                "avg_coupling": avg_coupling, "max_coupling": max_coupling,
                "modules_analyzed": len(module_imports),
            })
        first = timeline[0]["avg_coupling"] if timeline else 0
        last = timeline[-1]["avg_coupling"] if timeline else 0
        change = last - first
        change_pct = (change / first * 100) if first > 0 else 0
        summary = {
            "initial_avg_coupling": first, "current_avg_coupling": last,
            "change": change, "change_pct": round(change_pct, 1),
            "trend": "increasing" if change > 0.5 else "decreasing" if change < -0.5 else "stable",
        }
        most_coupled = []
        if commits:
            latest = commits[0]
            module_deps = defaultdict(set)
            for f in latest["files"]:
                content = self._get_file_at_commit(f["file"], latest["hash"])
                if content:
                    imports = self._count_imports(content)
                    module = f["file"].split("/")[0] if "/" in f["file"] else f["file"]
                    for imp in imports:
                        if imp != module:
                            module_deps[module].add(imp)
            sorted_modules = sorted(module_deps.items(), key=lambda x: -len(x[1]))
            most_coupled = [{"module": m, "dependencies": len(d), "deps": list(d)}
                            for m, d in sorted_modules[:10]]
        return {"timeline": timeline, "summary": summary, "most_coupled": most_coupled}

    def calculate_complexity_growth(self) -> Dict:
        """Track how cyclomatic complexity grows over time."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return {"timeline": [], "summary": {}, "complex_files": []}
        file_freq = defaultdict(int)
        for c in commits:
            for f in c["files"]:
                if f["file"]:
                    file_freq[f["file"]] += 1
        top_files = sorted(file_freq.items(), key=lambda x: -x[1])[:20]
        sampled = self._sample_commits(commits, max_samples=10)
        timeline = []
        for commit in sampled:
            total_complexity = 0
            total_lines = 0
            file_count = 0
            for filepath, _ in top_files:
                content = self._get_file_at_commit(filepath, commit["hash"])
                if content:
                    metrics = self._count_complexity(content)
                    total_complexity += metrics["cyclomatic"]
                    total_lines += metrics["lines"]
                    file_count += 1
            avg = total_complexity / file_count if file_count else 0
            timeline.append({
                "commit": commit["hash"], "date": commit["date"],
                "total_complexity": total_complexity, "avg_complexity": round(avg, 1),
                "total_lines": total_lines, "files_analyzed": file_count,
            })
        first_avg = timeline[0]["avg_complexity"] if timeline else 0
        last_avg = timeline[-1]["avg_complexity"] if timeline else 0
        change = last_avg - first_avg
        summary = {
            "initial_avg": first_avg, "current_avg": last_avg, "change": round(change, 1),
            "trend": "growing" if change > 1 else "shrinking" if change < -1 else "stable",
        }
        complex_files = []
        for filepath, freq in top_files:
            content = self._get_file_at_commit(filepath, "HEAD")
            if content:
                metrics = self._count_complexity(content)
                complex_files.append({
                    "file": filepath, "complexity": metrics["cyclomatic"],
                    "lines": metrics["lines"], "changes": freq,
                })
        complex_files.sort(key=lambda x: -x["complexity"])
        return {"timeline": timeline, "summary": summary, "complex_files": complex_files[:10]}

    def calculate_duplication_growth(self) -> Dict:
        """Track code duplication growth over time."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return {"timeline": [], "summary": {}}
        sampled = self._sample_commits(commits, max_samples=8)
        timeline = []
        for commit in sampled:
            file_blocks = {}
            for f in commit["files"]:
                if f["file"]:
                    content = self._get_file_at_commit(f["file"], commit["hash"])
                    if content:
                        file_blocks[f["file"]] = content
            line_hashes = defaultdict(list)
            for filepath, content in file_blocks.items():
                lines = content.split("\n")
                for i in range(len(lines) - 5):
                    block = "\n".join(lines[i:i + 6])
                    block_hash = hashlib.md5(block.encode()).hexdigest()
                    line_hashes[block_hash].append((filepath, i + 1))
            duplicates = {h: locs for h, locs in line_hashes.items() if len(locs) > 1}
            duplicate_lines = sum(6 * len(locs) for locs in duplicates.values())
            total_lines = sum(len(c.split("\n")) for c in file_blocks.values())
            dup_ratio = duplicate_lines / total_lines if total_lines > 0 else 0
            timeline.append({
                "commit": commit["hash"], "date": commit["date"],
                "duplicate_blocks": len(duplicates), "duplicate_lines": duplicate_lines,
                "total_lines": total_lines, "duplication_ratio": round(dup_ratio, 3),
            })
        first_ratio = timeline[0]["duplication_ratio"] if timeline else 0
        last_ratio = timeline[-1]["duplication_ratio"] if timeline else 0
        change = last_ratio - first_ratio
        summary = {
            "initial_ratio": first_ratio, "current_ratio": last_ratio,
            "change": round(change, 3),
            "trend": "worsening" if change > 0.01 else "improving" if change < -0.01 else "stable",
        }
        return {"timeline": timeline, "summary": summary}

    def calculate_debt_velocity(self) -> Dict:
        """Rate of technical debt accumulation per week."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return {"weekly_debt": [], "summary": {}}
        weekly_data = defaultdict(lambda: {"added": 0, "removed": 0, "commits": 0})
        for commit in commits:
            try:
                dt = datetime.strptime(commit["date"][:10], "%Y-%m-%d")
            except ValueError:
                continue
            week_num = dt.isocalendar()[1]
            year = dt.year
            week_key = f"{year}-W{week_num:02d}"
            for f in commit["files"]:
                weekly_data[week_key]["added"] += f["added"]
                weekly_data[week_key]["removed"] += f["removed"]
            weekly_data[week_key]["commits"] += 1
        weeks = sorted(weekly_data.keys())
        weekly_debt = []
        cumulative_debt = 0
        for week in weeks:
            data = weekly_data[week]
            net = data["added"] - data["removed"]
            rush_factor = min(data["commits"] / 5.0, 2.0)
            debt_added = net * rush_factor * 0.3
            cumulative_debt += debt_added
            weekly_debt.append({
                "week": week, "lines_added": data["added"], "lines_removed": data["removed"],
                "net": net, "commits": data["commits"],
                "debt_added": round(debt_added, 0), "cumulative_debt": round(cumulative_debt, 0),
            })
        total_debt = cumulative_debt
        avg_weekly = total_debt / len(weeks) if weeks else 0
        peak_week_data = max(weekly_debt, key=lambda x: x["debt_added"]) if weekly_debt else None
        summary = {
            "total_debt_lines": round(total_debt, 0), "avg_weekly_debt": round(avg_weekly, 0),
            "weeks_analyzed": len(weeks),
            "peak_week": peak_week_data["week"] if peak_week_data else None,
            "peak_debt": peak_week_data["debt_added"] if peak_week_data else 0,
        }
        return {"weekly_debt": weekly_debt, "summary": summary}

    def identify_decay_hotspots(self) -> List[Dict]:
        """Files degrading fastest."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return []
        file_data = defaultdict(lambda: {
            "commits": 0, "added": 0, "removed": 0, "authors": set(),
            "first_seen": None, "last_seen": None,
        })
        for commit in commits:
            date_str = commit["date"][:10]
            for f in commit["files"]:
                if not f["file"]:
                    continue
                fd = file_data[f["file"]]
                fd["commits"] += 1
                fd["added"] += f["added"]
                fd["removed"] += f["removed"]
                fd["authors"].add(commit["author"])
                if fd["first_seen"] is None:
                    fd["first_seen"] = date_str
                fd["last_seen"] = date_str
        hotspots = []
        for filepath, data in file_data.items():
            if data["commits"] < 2:
                continue
            churn = data["added"] + data["removed"]
            author_count = len(data["authors"])
            net_growth = data["added"] - data["removed"]
            content = self._get_file_at_commit(filepath, "HEAD")
            complexity = 0
            if content:
                metrics = self._count_complexity(content)
                complexity = metrics["cyclomatic"]
            decay_score = (
                (churn / max(data["commits"], 1)) * 2.0 +
                complexity * 0.5 +
                (author_count - 1) * 3.0 +
                max(net_growth, 0) * 0.1
            )
            hotspots.append({
                "file": filepath, "decay_score": round(decay_score, 1),
                "churn": churn, "commits": data["commits"], "authors": author_count,
                "complexity": complexity, "net_growth": net_growth,
                "first_seen": data["first_seen"], "last_seen": data["last_seen"],
            })
        hotspots.sort(key=lambda x: -x["decay_score"])
        return hotspots[:20]

    def predict_future_state(self, weeks: int = 12) -> Dict:
        """Predict code metrics N weeks from now using linear regression."""
        complexity_data = self.calculate_complexity_growth()
        debt_data = self.calculate_debt_velocity()
        coupling_data = self.calculate_coupling_growth()
        timeline = complexity_data.get("timeline", [])
        weekly_debt = debt_data.get("weekly_debt", [])

        def _linear_predict(values, steps_forward):
            if len(values) < 2:
                return values[-1] if values else 0
            n = len(values)
            x = list(range(n))
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_x2 = sum(xi ** 2 for xi in x)
            denom = n * sum_x2 - sum_x ** 2
            if denom == 0:
                return values[-1]
            slope = (n * sum_xy - sum_x * sum_y) / denom
            intercept = (sum_y - slope * sum_x) / n
            return round(intercept + slope * (n + steps_forward - 1), 1)

        predictions = {"weeks_forward": weeks}
        if timeline:
            avg_values = [t["avg_complexity"] for t in timeline]
            predictions["predicted_avg_complexity"] = _linear_predict(avg_values, weeks)
            total_values = [t["total_complexity"] for t in timeline]
            predictions["predicted_total_complexity"] = _linear_predict(total_values, weeks)
        if weekly_debt:
            debt_values = [w["cumulative_debt"] for w in weekly_debt]
            predictions["predicted_debt_lines"] = _linear_predict(debt_values, weeks)
        coupling_timeline = coupling_data.get("timeline", [])
        if coupling_timeline:
            coupling_values = [t["avg_coupling"] for t in coupling_timeline]
            predictions["predicted_avg_coupling"] = _linear_predict(coupling_values, weeks)
        predictions["confidence"] = "moderate" if len(timeline) >= 5 else "low"
        return predictions

    def generate_decay_timeline(self) -> List[Dict]:
        """Key inflection points where code quality changed significantly."""
        commits = self.get_commit_history(since_days=90)
        if not commits:
            return []
        sampled = self._sample_commits(commits, max_samples=15)
        inflections = []
        prev_metrics = None
        for commit in sampled:
            total_complexity = 0
            total_lines = 0
            file_count = 0
            for f in commit["files"]:
                if not f["file"]:
                    continue
                content = self._get_file_at_commit(f["file"], commit["hash"])
                if content:
                    metrics = self._count_complexity(content)
                    total_complexity += metrics["cyclomatic"]
                    total_lines += metrics["lines"]
                    file_count += 1
            current_avg = total_complexity / file_count if file_count else 0
            if prev_metrics is not None:
                prev_avg = prev_metrics["avg_complexity"]
                prev_lines = prev_metrics["total_lines"]
                prev_files = prev_metrics["files"]
                complexity_change = ((current_avg - prev_avg) / prev_avg) if prev_avg > 0 else 0
                size_change = ((total_lines - prev_lines) / prev_lines) if prev_lines > 0 else 0
                is_inflection = (
                    abs(complexity_change) > 0.2 or
                    abs(size_change) > 0.25 or
                    abs(file_count - prev_files) > prev_files * 0.3
                )
                if is_inflection:
                    event_type = (
                        "degradation" if complexity_change > 0.2 else
                        "improvement" if complexity_change < -0.2 else
                        "structural_change"
                    )
                    desc = self._describe_inflection(event_type, complexity_change, size_change)
                    inflections.append({
                        "commit": commit["hash"], "date": commit["date"],
                        "author": commit["author"], "type": event_type,
                        "complexity_change_pct": round(complexity_change * 100, 1),
                        "size_change_pct": round(size_change * 100, 1),
                        "description": desc,
                    })
            prev_metrics = {"avg_complexity": current_avg, "total_lines": total_lines, "files": file_count}
        return inflections

    def _describe_inflection(self, event_type, complexity_change, size_change):
        """Generate human-readable description of an inflection point."""
        parts = []
        if event_type == "degradation":
            parts.append(f"complexity {'spiked' if complexity_change > 0.3 else 'rose'} +{complexity_change * 100:.0f}%")
            if size_change > 0.25:
                parts.append(f"code grew +{size_change * 100:.0f}%")
        elif event_type == "improvement":
            parts.append(f"complexity improved {complexity_change * 100:.0f}%")
        else:
            direction = "grew" if size_change > 0 else "shrunk"
            parts.append(f"codebase {direction} {abs(size_change) * 100:.0f}%")
        return "; ".join(parts) if parts else "quality shift detected"

    def suggest_interventions(self) -> List[Dict]:
        """When and what to refactor based on decay analysis."""
        hotspots = self.identify_decay_hotspots()
        predictions = self.predict_future_state(weeks=12)
        coupling_data = self.calculate_coupling_growth()
        debt_data = self.calculate_debt_velocity()
        interventions = []

        for hs in hotspots[:5]:
            if hs["decay_score"] > 30:
                priority, icon = "critical", "🔴"
            elif hs["decay_score"] > 15:
                priority, icon = "high", "🟠"
            elif hs["decay_score"] > 8:
                priority, icon = "medium", "🟡"
            else:
                continue
            suggestions = []
            if hs["complexity"] > 20:
                suggestions.append("break into smaller functions/modules")
            if hs["authors"] > 3:
                suggestions.append("assign clear ownership")
            if hs["net_growth"] > 100:
                suggestions.append("review recent additions for necessity")
            if hs["churn"] / max(hs["commits"], 1) > 50:
                suggestions.append("stabilize — changes are volatile")
            if not suggestions:
                suggestions.append("review and refactor")
            interventions.append({
                "icon": icon, "priority": priority, "file": hs["file"],
                "action": "refactor", "details": "; ".join(suggestions),
                "decay_score": hs["decay_score"], "complexity": hs["complexity"],
            })

        pred_complexity = predictions.get("predicted_avg_complexity", 0)
        if pred_complexity > 15:
            interventions.append({
                "icon": "🔴", "priority": "critical", "file": "project-wide",
                "action": "architectural_review",
                "details": f"predicted avg complexity {pred_complexity} in 12 weeks — schedule refactoring sprint",
                "decay_score": 0, "complexity": 0,
            })

        coupling_summary = coupling_data.get("summary", {})
        if coupling_summary.get("trend") == "increasing":
            interventions.append({
                "icon": "🟠", "priority": "high", "file": "project-wide",
                "action": "decouple_modules",
                "details": f"module coupling growing (+{coupling_summary.get('change_pct', 0)}%) — review dependency graph",
                "decay_score": 0, "complexity": 0,
            })

        debt_summary = debt_data.get("summary", {})
        avg_debt = debt_summary.get("avg_weekly_debt", 0)
        if avg_debt > 100:
            interventions.append({
                "icon": "🟡", "priority": "medium", "file": "project-wide",
                "action": "debt_sprint",
                "details": f"accumulating ~{avg_debt:.0f} debt lines/week — allocate 20% sprint capacity to cleanup",
                "decay_score": 0, "complexity": 0,
            })

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        interventions.sort(key=lambda x: priority_order.get(x["priority"], 99))
        return interventions

    def compare_decay_rates(self) -> Dict:
        """Compare decay rate across directories."""
        repo_abs = os.path.abspath(self.repo_path)
        subdirs = []
        for entry in os.listdir(repo_abs):
            full = os.path.join(repo_abs, entry)
            if os.path.isdir(full) and not entry.startswith('.') and entry not in (
                'node_modules', '__pycache__', '.git', 'vendor', 'build', 'dist',
                '.venv', 'venv', 'target', '.tox', '.next', '.nuxt', 'tests', 'test'
            ):
                subdirs.append(entry)

        results = []
        for subdir in sorted(subdirs):
            commits = self.get_commit_history(since_days=90)
            file_freq = defaultdict(int)
            for c in commits:
                for f in c["files"]:
                    if f["file"] and f["file"].startswith(subdir + "/"):
                        file_freq[f["file"]] += 1

            if not file_freq:
                continue

            # Analyze complexity of files in this directory
            total_complexity = 0
            file_count = 0
            for filepath in list(file_freq.keys())[:10]:
                content = self._get_file_at_commit(filepath, "HEAD")
                if content:
                    metrics = self._count_complexity(content)
                    total_complexity += metrics["cyclomatic"]
                    file_count += 1

            avg_complexity = total_complexity / file_count if file_count else 0
            total_churn = sum(file_freq.values())

            results.append({
                "directory": subdir,
                "file_count": len(file_freq),
                "total_churn": total_churn,
                "avg_complexity": round(avg_complexity, 1),
                "decay_rate": round(total_churn / max(len(file_freq), 1), 1),
            })

        results.sort(key=lambda x: -x["decay_rate"])
        return {"directories": results}

    def generate_report(self) -> str:
        """Generate ASCII report of decay analysis."""
        lines = []
        lines.append("")
        lines.append("  ╔═══════════════════════════════════════════════════════════╗")
        lines.append("  ║          🏚️  ARCHITECTURAL DECAY ANALYSIS                 ║")
        lines.append("  ╠═══════════════════════════════════════════════════════════╣")
        lines.append(f"  ║  Repository: {os.path.basename(os.path.abspath(self.repo_path)):<48s}║")
        lines.append(f"  ║  Is Git:     {'Yes' if self.is_git else 'No':<48s}║")
        lines.append("  ╚═══════════════════════════════════════════════════════════╝")

        if not self.is_git:
            lines.append("")
            lines.append("  ⚠️  Not a git repository. Decay analysis requires git history.")
            return "\n".join(lines)

        # Complexity growth
        lines.append("")
        lines.append("  📈 COMPLEXITY GROWTH")
        lines.append("  " + "─" * 55)
        cg = self.calculate_complexity_growth()
        timeline = cg.get("timeline", [])
        if timeline:
            for t in timeline[-5:]:
                bar_len = min(int(t["avg_complexity"] / 2), 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"    {t['date'][:10]}  avg CC: {t['avg_complexity']:>5.1f}  [{bar}]")
            summary = cg.get("summary", {})
            trend_icon = {"growing": "📈", "shrinking": "📉", "stable": "➡️"}.get(summary.get("trend", ""), "➡️")
            lines.append(f"    Trend: {trend_icon} {summary.get('trend', 'unknown').upper()}")
        else:
            lines.append("    No commit data available.")

        # Decay hotspots
        lines.append("")
        lines.append("  🔥 DECAY HOTSPOTS (top 10)")
        lines.append("  " + "─" * 55)
        hotspots = self.identify_decay_hotspots()
        if hotspots:
            for i, hs in enumerate(hotspots[:10], 1):
                bar_len = min(int(hs["decay_score"] / 2), 20)
                bar = "█" * bar_len
                icon = "🔴" if hs["decay_score"] > 30 else "🟠" if hs["decay_score"] > 15 else "🟡" if hs["decay_score"] > 8 else "🟢"
                fname = hs["file"][-40:] if len(hs["file"]) > 40 else hs["file"]
                lines.append(f"    {icon} {i:>2d}. {hs['decay_score']:>5.1f} [{bar:<20s}] {fname}")
        else:
            lines.append("    No hotspots detected.")

        # Coupling growth
        lines.append("")
        lines.append("  🔗 COUPLING GROWTH")
        lines.append("  " + "─" * 55)
        coup = self.calculate_coupling_growth()
        coup_timeline = coup.get("timeline", [])
        if coup_timeline:
            for t in coup_timeline[-5:]:
                lines.append(f"    {t['date'][:10]}  avg coupling: {t['avg_coupling']:.1f}  (max: {t['max_coupling']})")
            coup_summary = coup.get("summary", {})
            trend_icon = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}.get(coup_summary.get("trend", ""), "➡️")
            lines.append(f"    Trend: {trend_icon} {coup_summary.get('trend', 'unknown').upper()}")
            most_coupled = coup.get("most_coupled", [])[:5]
            if most_coupled:
                lines.append("    Most coupled modules:")
                for mc in most_coupled:
                    lines.append(f"      • {mc['module']}: {mc['dependencies']} dependencies")
        else:
            lines.append("    No data available.")

        # Duplication growth
        lines.append("")
        lines.append("  📋 DUPLICATION GROWTH")
        lines.append("  " + "─" * 55)
        dup = self.calculate_duplication_growth()
        dup_timeline = dup.get("timeline", [])
        if dup_timeline:
            for t in dup_timeline[-5:]:
                ratio_bar_len = min(int(t["duplication_ratio"] * 100), 20)
                bar = "█" * ratio_bar_len + "░" * (20 - ratio_bar_len)
                lines.append(f"    {t['date'][:10]}  ratio: {t['duplication_ratio']:.3f}  [{bar}]")
            dup_summary = dup.get("summary", {})
            trend_icon = {"worsening": "📈", "improving": "📉", "stable": "➡️"}.get(dup_summary.get("trend", ""), "➡️")
            lines.append(f"    Trend: {trend_icon} {dup_summary.get('trend', 'unknown').upper()}")
        else:
            lines.append("    No data available.")

        # Debt velocity
        lines.append("")
        lines.append("  💰 DEBT VELOCITY")
        lines.append("  " + "─" * 55)
        debt = self.calculate_debt_velocity()
        weekly = debt.get("weekly_debt", [])
        if weekly:
            for w in weekly[-6:]:
                debt_bar_len = min(int(abs(w["debt_added"]) / 10), 20)
                bar = "█" * debt_bar_len
                lines.append(f"    {w['week']}  debt: {w['debt_added']:>6.0f} lines  cum: {w['cumulative_debt']:>8.0f}  [{bar}]")
            debt_summary = debt.get("summary", {})
            lines.append(f"    Avg weekly debt: {debt_summary.get('avg_weekly_debt', 0):.0f} lines")
            lines.append(f"    Total debt: {debt_summary.get('total_debt_lines', 0):.0f} lines")
        else:
            lines.append("    No data available.")

        # Predictions
        lines.append("")
        lines.append("  🔮 PREDICTIONS (12 weeks forward)")
        lines.append("  " + "─" * 55)
        pred = self.predict_future_state(weeks=12)
        lines.append(f"    Avg complexity:   {pred.get('predicted_avg_complexity', 'N/A')}")
        lines.append(f"    Total complexity: {pred.get('predicted_total_complexity', 'N/A')}")
        lines.append(f"    Debt lines:       {pred.get('predicted_debt_lines', 'N/A')}")
        lines.append(f"    Avg coupling:     {pred.get('predicted_avg_coupling', 'N/A')}")
        lines.append(f"    Confidence:       {pred.get('confidence', 'unknown')}")

        # Inflection points
        lines.append("")
        lines.append("  ⚡ INFLECTION POINTS")
        lines.append("  " + "─" * 55)
        inflections = self.generate_decay_timeline()
        if inflections:
            for inf in inflections[:5]:
                icon = {"degradation": "🔴", "improvement": "🟢", "structural_change": "🟡"}.get(inf["type"], "⚪")
                lines.append(f"    {icon} {inf['date'][:10]} {inf['commit']} — {inf['description']}")
        else:
            lines.append("    No significant inflection points detected.")

        # Interventions
        lines.append("")
        lines.append("  💡 RECOMMENDED INTERVENTIONS")
        lines.append("  " + "─" * 55)
        interventions = self.suggest_interventions()
        if interventions:
            for iv in interventions[:5]:
                lines.append(f"    {iv['icon']} [{iv['priority'].upper()}] {iv['file']}")
                lines.append(f"       Action: {iv['action']}")
                lines.append(f"       {iv['details']}")
        else:
            lines.append("    No interventions needed — codebase is healthy!")

        lines.append("")
        lines.append("  ═══════════════════════════════════════════════════════════")
        return "\n".join(lines)


