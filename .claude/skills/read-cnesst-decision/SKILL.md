---
name: read-cnesst-decision
description: >
  Use when reading a CNESST administrative decision, review decision or
  entitlement determination.
applies_to:
  - administrative_decision
  - decision
  - cnesst_decision
  - tribunal_decision
  - review_decision
  - décision cnesst
  - décision dra
  - décision tat
---

# Objective

Extract the legally meaningful decision event.

# Required extraction

- Decision date token
- Decision maker or body
- Issue being decided
- Accepted diagnoses
- Rejected diagnoses
- Entitlement or benefit consequence
- Work-capacity consequence
- Review or appeal information when material
- Supporting source page and quote

# Rules

- Never use the accident date as the decision date.
- Preserve the exact accepted and rejected diagnoses.
- Do not place a CNESST decision in the secondary queue.
- Separate multiple decisions contained in one document.
- Flag ambiguity rather than inferring legal effect.

# Common errors

- Summarizing only the medical evidence and omitting the determination.
- Treating the mailing date as the decision date.
- Dropping a rejected diagnosis.
