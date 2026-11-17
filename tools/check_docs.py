from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    ".specify/memory/constitution.md",
    "docs/adr/README.md",
    "docs/architecture.md",
    "specs/001-platform-foundation/spec.md",
    "specs/001-platform-foundation/plan.md",
    "specs/001-platform-foundation/tasks.md",
)
README_REFERENCES = (
    ".specify/memory/constitution.md",
    "docs/adr/README.md",
    "docs/architecture.md",
    "specs/001-platform-foundation/",
)


def find_documentation_issues(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (root / relative).exists():
            issues.append(f"Missing required documentation: {relative}")

    readme = root / "README.md"
    if not readme.exists():
        issues.append("Missing README.md")
        return issues

    content = readme.read_text(encoding="utf-8")
    for reference in README_REFERENCES:
        if reference not in content:
            issues.append(f"README.md does not reference {reference}")
    return issues


def main() -> int:
    issues = find_documentation_issues()
    if issues:
        for issue in issues:
            print(f"DOCUMENTATION ISSUE: {issue}")
        return 1
    print("Documentation navigation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
