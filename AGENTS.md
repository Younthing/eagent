# AGENTS.md

This file is a working checklist for maintaining documentation consistency as the
ROB2 system evolves.

## Document Map (What Each Doc Is For)

- `docs/requirements.md`: Product requirements and scope (Standard ROB2 only).
- `docs/architecture.md`: Target architecture, interfaces, layering, and repo layout.
- `docs/system-uml.md`: Current implementation diagram (code-level).
- `docs/Milestones.md`: Milestone plan and deliverables mapping.
- `docs/rob2_reference/rob2_questions.md`: ROB2 decision trees and question mapping.
- `docs/adr/`: Architecture Decision Records (why a choice was made).
- `docs/evaluation/`: Evaluation protocols, benchmarks, and scoring results.

## Update Triggers (What to Touch When Something Changes)

- **Scope change** (e.g., input format, supported ROB2 variant)
  - Update `docs/requirements.md`
  - If it affects flow, update `docs/architecture.md`
  - If it impacts milestones, update `docs/Milestones.md`

- **Architecture change** (new subsystem, new pipeline step, new data contract)
  - Update `docs/architecture.md`
  - Update `docs/requirements.md` if the requirement or guarantees change
  - Add an ADR in `docs/adr/` if there was a significant trade-off

- **Implementation change** (new nodes, graph routing, runtime behavior)
  - Update `docs/system-uml.md` if it changes the code structure
  - Ensure `docs/architecture.md` still represents the target system

- **Evaluation change** (new dataset, metric, or benchmark)
  - Update `docs/evaluation/` (new report or add a section)
  - Update `docs/Milestones.md` if milestone DoD changes

- **ROB2 rule change** (new decision rules or mapping updates)
  - Update `docs/rob2_reference/rob2_questions.md`
  - Update `docs/architecture.md` if interfaces or reasoning flow change

## Minimal Process (Plan → Implement → Verify)

1. **Plan**: Update `docs/requirements.md` and/or add ADRs if needed.
2. **Design**: Update `docs/architecture.md` (diagram + contracts + flow).
3. **Implement**: Update code and `docs/system-uml.md` if structure changes.
4. **Evaluate**: Record changes in `docs/evaluation/`.
5. **Milestones**: Keep `docs/Milestones.md` in sync with deliverables.

## Quality Checks

- After coding, run `uvx ty check` and `ruff` checks before finalizing changes.

## Notes

- The system is **Standard ROB2 only** unless explicitly changed in requirements.
- `docs/system-uml.md` is descriptive (current code), while `docs/architecture.md`
  is prescriptive (target design).
