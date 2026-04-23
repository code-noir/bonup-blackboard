# NEXT_TASK.md

Status: Queued

## Date
2026-04-23

## Sprint
Sprint 02 — Core Stabilization

## Task ID
C1

## Task Name
Fix lifecycle automation path

## Why this is next
Once Sprint 01 is properly closed in the docs and the repo structure is cleaned, Sprint 02 begins with the broken lifecycle automation path because it is one of the main false-working core paths in the backend.

## Goal
Make lifecycle automation either actually work or be explicitly disabled until repaired.

## Known problem
The `run_lifecycle` path appears to fail because of a runner/service invocation mismatch.

## Required outcome
- `run_lifecycle` must no longer fail because of the known mismatch
- the real invocation path must be identified clearly
- use the smallest safe fix that restores the intended automation path
- do not broaden this into a lifecycle refactor
- do not redesign unrelated contract lifecycle logic

## Scope
- inspect only the minimum files needed for the lifecycle automation command, runner, factory, and service call chain
- edit only the minimum files necessary
- add or update tests if practical and necessary

## Success condition
- `run_lifecycle` no longer fails from the known invocation mismatch
- the fixed path is clear and intentional
- any remaining lifecycle architecture debt is reported, not expanded into this task