# AGENTS.md

## Project Identity

This repository belongs to the **bonUP** platform.

The platform brand name is:

**bonUP**

Spelling is strict in user-facing contexts:
- lowercase **b**
- lowercase **o**
- lowercase **n**
- uppercase **U**
- uppercase **P**

Correct brand spelling:
- bonUP

Incorrect user-facing spellings:
- BonUp
- BonUP
- Bonup
- bonup
- bon up
- bone up
- Bon Appetit

## Product Structure

**bonUP** is the overall platform.

**Blackboard** is the contract system/product inside bonUP.

When the owner says **bonUP**, they usually mean the whole platform.

When the owner says **Blackboard**, they usually mean the contract system, contract workflow, contract domain, or contract-related product experience inside bonUP.

## Brand Naming vs Code Naming

### User-Facing Naming

In all user-facing text, the platform name must be written as:

**bonUP**

This applies to:
- frontend UI
- landing pages
- navigation
- buttons
- forms
- emails
- page titles
- product copy
- marketing copy
- support copy
- public-facing documentation
- user-visible error messages

### Code Naming

In code, technical identifiers may follow language, framework, database, or environment-variable conventions.

Acceptable code examples:
- `bonupConfig`
- `bonUPDisplayName`
- `BonupUser`
- `BonupContractService`
- `BONUP_API_KEY`
- `bonup_contracts`

However, any string rendered to users must use:

```ts
"bonUP"
```

## Source of Truth

The repository is the source of truth.

Do not rely on chat memory for:
- project facts
- product rules
- current task status
- architecture decisions
- implementation constraints
- business rules

Before planning or editing, read the relevant repo truth first.

Default reading order:
1. AGENTS.md
2. CLAUDE.md if present
3. docs/current-task.md
4. docs/next-task.md
5. docs/current-state/architecture/README.md
6. relevant domain architecture docs
7. relevant source code

If memory conflicts with repo files, repo files win.

If documentation conflicts with actual code behavior, report the conflict before editing.

Code behavior is the final source of truth for how the system currently works.

## Owner Authority

The owner is the final authority for:
- product direction
- priorities
- approval of implementation plans
- final code acceptance
- commits
- deployment decisions

AI agents must not commit changes.

Do not run:
- git commit
- git push
- git reset
- git rebase
- destructive git commands

unless the owner explicitly instructs it.

The owner runs git commands and writes commit messages.

## Interaction Modes

### Discussion Mode

When the owner says "discussion mode":
- do not edit files
- do not create files
- do not run commands unless explicitly approved
- treat the conversation as planning/context only
- help clarify product, architecture, or engineering direction
- summarize possible repo updates, but wait for approval before making changes

### Audit Mode

When the owner says "audit mode":
- inspect relevant files
- read code before making technical recommendations
- do not edit files
- do not create files
- do not run tests unless explicitly approved

Report:
1. files inspected
2. existing patterns found
3. risks or conflicts
4. proposed minimal change
5. tests needed
6. files that should not be touched

### Plan Mode

When the owner says "plan mode":
- produce a specific implementation plan
- recommend one approach
- include one realistic alternative and why it was not chosen
- identify tradeoffs
- identify blast radius
- identify tests required
- do not edit files

### Implementation Mode

When the owner says "implementation mode":
- edit only approved files
- keep the change small and controlled
- do not touch unrelated files
- follow existing code patterns unless there is a clear reason to deviate
- handle edge cases and error paths
- do not silently catch errors
- do not leave commented-out code behind
- do not commit

### Review Mode

When the owner says "review mode":
- summarize exact files changed
- summarize the purpose of each change
- report tests run and results
- report tests not run and why
- report remaining risks
- report documentation that may need updating
- do not commit

## Engineering Principles

- Code is truth; docs may be stale.
- Audit before action.
- Inventory before write.
- Small, accurate, controlled work beats large, clever, risky work.
- Correctness before speed.
- Prefer boring, maintainable solutions over clever abstractions.
- Match existing project patterns unless there is a strong reason to deviate.
- Name architectural drift before proceeding.
- Do not over-engineer.
- Do not mix unrelated cleanup with feature work.
- Do not invent project facts from memory.

## Blackboard Product Rules

Blackboard is the contract system inside bonUP.

Blackboard contracts have a maximum of 3 versions.

After version 3, parties must start a new contract.

Any task touching contracts, revisions, versions, agreement lifecycle, signing, negotiation, or contract UI must respect this rule.

## Code Quality Rules

Flag these issues before proceeding:
- premature abstraction
- new pattern when an existing pattern already fits
- scope creep
- inconsistency with existing architecture
- copy-paste instead of proper extraction
- magic numbers
- missing error handling
- untested critical paths
- mutable shared state without reason
- silent catches
- unrelated cleanup mixed into feature work
- commented-out code left behind
- user-facing naming that violates bonUP brand rules

## Required Technical Response Format

For technical tasks, respond with:

1. Assumptions
2. Files inspected
3. Existing pattern found
4. Recommendation
5. Alternative considered
6. Risks / edge cases
7. Test plan
8. Files to change
9. Files not to touch

Do not skip code inspection when the task involves existing behavior.

## Testing and Verification

Before saying work is complete:
- run relevant tests if available
- run typecheck/build/lint when touched files affect runtime behavior
- report the exact commands run
- report the exact results
- if tests cannot be run, explain why

Never claim something was tested if it was not actually tested.

## Documentation

Update documentation only when:
- the task requires it
- code behavior changes
- architecture decisions change
- product rules change
- current task/next task state changes

Do not invent documentation from memory.

When updating docs, base changes on:
- code behavior
- owner-approved decisions
- current repo state

## Git Rules

Do not commit.

Do not push.

Do not create branches unless explicitly instructed.

Do not rewrite git history.

Do not stage files unless explicitly instructed.

The owner controls git.

## Secrets and Security

Do not print secrets.

Do not modify production credentials.

Do not edit .env files unless explicitly instructed.

Use .env.example for documenting required environment variables.

Report security-sensitive changes before implementing them.

Treat the following as high-risk:
- authentication
- authorization
- payments
- database migrations
- production data
- deployment configuration
- VPS/server configuration
- API keys
- secrets
- user private data

## VPS and Deployment Safety

This project may run on a VPS.

Deployment and server changes require extra caution.

For deployment-related tasks:
1. audit first
2. identify files/configs involved
3. identify rollback path
4. wait for explicit approval
5. do not run destructive commands without approval

## Final Rule

Do not act like memory is truth.

Do not act like confidence is evidence.

Read the repo, inspect the code, name the risk, make the smallest safe change, test it, and report honestly.
