# Code Review Process for AI-Generated Code

## Branch Strategy

AI work happens on feature branches, NOT main.

```bash
# Before AI starts
git checkout -b ai/pipeline-run-$(date +%Y%m%d)
git tag pre-ai-$(date +%Y%m%d)

# AI works on branch, commits after each task
# ...

# After AI completes
git checkout main
git diff main..ai/pipeline-run-YYYYMMDD  # Review changes
```

## Review Checklist

### Structure
- [ ] New files in correct directories
- [ ] No random files in project root
- [ ] __init__.py files present where needed

### Code Quality
- [ ] Follows existing patterns (check similar files)
- [ ] No hardcoded secrets/paths
- [ ] Error handling present
- [ ] Logging added for key operations

### Tests
- [ ] New code has corresponding tests
- [ ] All tests pass
- [ ] No tests skipped without reason

### Documentation
- [ ] Docstrings on public functions
- [ ] README updated if needed
- [ ] ADR created for major decisions

## Quick Review Commands

```bash
# See all changes
git diff main..HEAD

# See changed files
git diff main..HEAD --stat

# See commits
git log main..HEAD --oneline

# Review specific file
git diff main..HEAD -- dashboard/app.py
```

## Merge Process

1. All tests pass: `pytest tests/ -v`
2. Human reviews diff: `git diff main..HEAD`
3. Human approves
4. Squash merge: `git checkout main && git merge --squash ai/branch && git commit`
5. Delete feature branch: `git branch -D ai/branch`
