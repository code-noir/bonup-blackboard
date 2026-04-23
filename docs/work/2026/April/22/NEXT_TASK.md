# NEXT_TASK.md

Status: Queued

## Sprint
Sprint 02 — Core Stabilization

## Task ID
C2

## Task Name
Resolve broken contacts path

## Why this is next
After lifecycle automation is fixed or explicitly disabled, the next cleanup target is the broken contacts path because it is broken legacy state that pollutes repo truth and could create future confusion or accidental reactivation.

## Goal
Stop the contacts area from remaining in a broken, misleading legacy state.

## Known problem
The contacts domain is broken, unrouted, and imports a deleted model class.

## Required outcome
- decide whether contacts should be removed, repaired, or isolated
- eliminate import of deleted model class
- ensure repo no longer presents contacts as a live usable domain when it is not
- document the decision clearly if the feature is intentionally deferred

## Scope
- inspect only the minimum files needed for contacts views, urls, model references, and related imports
- edit only the minimum files necessary
- do not broaden into contact system redesign

## Success condition
- contacts path is no longer broken and ambiguous
- either the domain is repaired or it is clearly removed or isolated
- future work cannot mistake it for a stable live feature