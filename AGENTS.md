# Codex Agent Instructions - Chain Listener SDK

This file is the Codex-oriented version of the prompts in `.claude/`.
It consolidates project context, rules, and workflows into direct instructions.

## Project Context
- Build a universal multi-chain blockchain listener SDK for async event monitoring.
- Focus on reliability, performance, and security.
- Stack: Python 3.8+, asyncio + aiohttp, Web3.py, Pydantic, pytest, Poetry.
- Architecture: multi-chain support, adapter pattern, event-driven callbacks, async-first.
- Keep backward compatibility.

## Priority 1: Critical Rules (Must Follow)
- Security first: never expose sensitive data; validate all external inputs; handle errors safely; never execute user-provided strings as commands.
- TDD is mandatory: write failing tests before production code; follow Red-Green-Refactor; keep >= 90% test coverage.
- Code quality: type hints on all functions; Google-style docstrings for public APIs; PEP 8 (88 char line width).
- No production code without tests; avoid over-engineering and unnecessary features (YAGNI).

## Priority 2: Important Guidelines (Should Follow)
- Single responsibility, DRY, interface-based design when multiple implementations exist.
- Async-first for all I/O; avoid blocking calls; clean up resources (connections, subscriptions).
- Implement retry/recovery for transient failures; avoid memory leaks in long-running listeners.
- Keep naming clear, follow existing patterns, update `PROGRESS.md` at milestones.

## Priority 3: Recommendations (Nice to Have)
- Small, frequent commits; self-review; keep docs and examples updated.
- Favor clarity before optimization; measure before tuning.

## Coding Standards
- Formatting: 4 spaces; 88-char lines; import order (standard, third-party, local).
- Naming: modules `lowercase_with_underscores`, classes `CamelCase`, functions/vars `snake_case`, constants `ALL_CAPS`.
- File structure: imports, constants, classes/functions, helpers, optional `__main__`.
- Class structure: class attrs, `__init__`, public methods, abstract methods, private methods.
- Error handling: use explicit exceptions; log errors without leaking sensitive data.

## TDD Workflow
- Red: write failing tests first.
- Green: minimal code to pass tests.
- Refactor: improve structure while keeping tests green.
- Tests should be fast, independent, repeatable, and self-validating.
- Use AAA (Arrange/Act/Assert); avoid testing private methods.

## Feature Development Workflow
- Clarify requirements, review existing code, identify reusable components.
- Write tests first covering happy path, edge cases, errors, and integration.
- Implement minimal solution, then refactor and document.
- Check security, async behavior, and integration with `ChainListener`.

## Bug Fixing Workflow
- Reproduce with a failing test; identify root cause and impact.
- Apply the smallest fix possible; verify with full test suite.
- Add regression tests; update docs if behavior changes.

## Technical Design Protocol (Required for Larger Changes)
Use for new adapters, core architecture changes, or complex features (> ~500 LOC).

Phase 0 (Principles)
- Priority: usability > simplicity (KISS) > extensibility (OCP).
- YAGNI, keep designs readable, safety first.

Phase 1 (Context Analysis)
- Analyze models/adapters/utils for reuse and constraints.
- Identify performance and reliability needs.
- Ask 3-5 clarifying questions (edge cases: reorgs, network drops, retries).
- Stop and wait for user confirmation before drafting a solution.

Phase 2 (Draft Tech Spec)
- Provide architecture, interfaces, data models, and error handling.
- Use diagrams (Mermaid) for complex flows.
- Keep this at design level; avoid implementation code.

Phase 3 (Adversarial Audit)
- Critique the design across architecture, security, reliability, performance, KISS, blockchain-specific concerns.
- Output "Architecture Approved" or "Refactoring Required" and propose fixes.
- Ask whether to update the spec if changes are needed.

Phase 4 (Implementation Plan)
- Break into atomic steps, each suitable for an independent commit.
- Include tests and documentation updates.

## Tests and Commands
- Tests: `poetry run pytest` (unit/integration/coverage as needed).
- Prefer `poetry run ...` for tools and examples.
- Use `tests/unit/` and `tests/integration/` structures.
- Reference template: `.claude/templates/test-template.py`.
