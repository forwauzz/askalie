# Ask ALIE — Local Agentic Chronology Platform
## Proof-of-Concept Product and Technical Specification

**Status:** Implementation-ready POC specification  
**Primary objective:** Determine whether an adaptive agentic architecture can outperform Ask ALIE’s previous deterministic and hybrid chronology solutions.  
**Initial domain:** Québec CNESST medical-legal files  
**Initial language:** French-first  
**Deployment:** Local application and local case workspace, with Claude inference through the Claude Agent SDK  
**Production readiness:** Out of scope

---

# 1. Executive summary

Ask ALIE is a local proof-of-concept platform for producing a sourced medical-legal chronology from large Québec case files.

The system receives PDFs containing medical, administrative and legal records. It extracts usable page text, replaces identifying information and dates with stable tokens, and exposes local case tools to a Claude Agent SDK orchestrator.

The orchestrator is adaptive. It inspects the case, delegates report discovery and reading, reviews intermediate results, identifies probable gaps, requests targeted re-reading or re-segmentation, and decides when the case is ready for curation.

The POC tests this hypothesis:

> An adaptive orchestrator supervising report discovery, report-level readers, gap investigation and curation will produce a more complete and more reviewable chronology than Ask ALIE’s prior fixed deterministic and hybrid approaches.

This is not a production system. It does not require multi-tenant authentication, distributed infrastructure, a production database, enterprise observability or deployment automation. It should remain simple enough for one developer to understand and modify.

---

# 2. The problem

A Québec CNESST, SAAQ or IVAC file may contain hundreds or thousands of pages of:

- consultation notes;
- emergency records;
- imaging reports;
- operative reports;
- physiotherapy and occupational therapy notes;
- expert reports;
- CNESST forms and decisions;
- employer records;
- prescriptions and referrals;
- laboratory reports;
- correspondence;
- duplicated faxes and scans;
- poorly OCR’d pages;
- handwritten material.

A paralegal reads the file and builds a chronology of material dated events, each tied to a source.

Ask ALIE has already tested multiple deterministic and hybrid approaches. The recurring weakness has been the machinery surrounding model reasoning:

- incorrect report boundaries;
- over-collapsing report units;
- brittle date reconciliation;
- missed events caused by filters;
- failures introduced by joins and post-processing;
- inability to adapt when the first interpretation of a document is wrong.

The POC must not recreate that architecture with different labels.

---

# 3. POC hypotheses

## 3.1 Primary hypothesis

An agentic control loop can recover material events that a fixed one-pass architecture misses by allowing the orchestrator to:

- inspect intermediate outputs;
- identify suspicious gaps;
- change report boundaries;
- request another reader;
- follow cross-references;
- re-read zero-event or low-confidence reports;
- run targeted searches;
- invoke a critic;
- stop only after reviewing the case state.

## 3.2 Secondary hypotheses

1. Giving a reader the complete report produces better events than retrieving disconnected spans.
2. A Scout Agent can identify report boundaries more accurately than the previous deterministic segmentation machinery.
3. A Gap Agent can recover a meaningful number of gold events after the initial reader pass.
4. A Curator Agent can reduce the default review burden without hiding supported candidate events.
5. Personalization can be added after baseline performance by converting user corrections into reusable skills and preferences.

## 3.3 What the POC is not proving

The POC is not trying to prove that:

- every model call must be an autonomous agent;
- the Claude Agent SDK should replace normal Python;
- multi-agent architecture is inherently better;
- the system is ready for live client deployment;
- personalization must exist before the base chronology works;
- the final UI is production quality.

---

# 4. Success criteria

The prior Case 1 reference result is:

- 74 gold events;
- 50 captured;
- 187 total emitted rows.

Every run must report:

1. **Gold captured** — gold events represented with the correct date and materially correct meaning.
2. **Total candidate events** — all events before curation.
3. **Default queue count**.
4. **Secondary queue count**.
5. **Defensible extras** — real useful events absent from the gold chronology.
6. **Unsupported extras**.
7. **Wrong-date events**.
8. **Events recovered by the agentic loop** — valuable events found only after the first reader pass.
9. **Review time** — time to reach an approved chronology.
10. **Run cost and duration**.
11. **Run-to-run stability**.

The most important agentic metric is:

> How many valuable events were recovered because the orchestrator adapted after seeing the initial result?

If that number is negligible, the added agentic complexity is not earning its place.

---

# 5. Design principles

## 5.1 Models make semantic judgments

Models decide:

- where a report begins and ends;
- what type of report it is;
- which date token represents the event date;
- what happened;
- what details matter;
- whether one report contains multiple events;
- whether an event belongs in the default or secondary queue;
- where probable omissions remain.

## 5.2 Local code provides tools and state

Local code:

- extracts text;
- runs OCR;
- tokenizes identifiers and dates;
- stores pages and reports;
- dispatches reader jobs;
- exposes state to agents;
- restores real dates;
- preserves source references;
- calculates metrics;
- renders results.

Local code should not infer medical or legal meaning through elaborate rules.

## 5.3 Nothing supported is silently deleted

A candidate may be:

- default;
- secondary;
- duplicate-linked;
- uncertain;
- unsupported;
- rejected by the reviewer.

It remains inspectable.

## 5.4 The orchestrator must be adaptive

The system is not agentic merely because it calls several models. The orchestrator must inspect current state and choose among different next actions.

## 5.5 Personalization follows baseline value

```text
Baseline works
    → user reviews
    → corrections are captured
    → repeated corrections become approved preferences or skills
    → skills and preferences are bundled into profiles
```

## 5.6 Test instead of debating

Where two reasonable approaches exist, implement the smallest comparison and score both.

Examples:

- opaque date tokens versus tokens plus relative metadata;
- current report units versus Scout-generated report units;
- one reader versus reader plus critic;
- direct curation versus hierarchical curation.

---

# 6. Scope

## 6.1 In scope

- Select a local case directory or upload PDFs.
- Hybrid native-text and OCR extraction.
- French and English page text.
- Stable identifier and date tokenization.
- Local case workspace.
- Scout Agent for report discovery.
- Reader workers operating on complete reports.
- Adaptive master orchestrator.
- Gap Agent.
- Curator Agent.
- Default and secondary queues.
- Source page and supporting quote.
- Basic local review UI.
- CSV, JSON and simple HTML export.
- Evaluation against the three gold cases.
- Optional case instructions.
- Filesystem-based Agent Skills after baseline success.
- Case chat after chronology validation.

## 6.2 Out of scope

- Multi-tenant authentication.
- Production database.
- Cloud storage.
- Production deployment.
- Distributed queues.
- Enterprise permission model.
- Billing.
- Production audit infrastructure.
- Perfect handwriting recognition.
- Image redaction pipeline.
- Complex MCP ecosystem.
- Automatic profile learning without user approval.
- Fine-tuning.
- Replacing current ALIE production code.
- SAAQ and IVAC optimization before CNESST baseline success.

---

# 7. User experience

## 7.1 First-run flow

The user is not asked to create a profile.

```text
1. Select case folder or upload PDFs.
2. Select “Build chronology.”
3. Configuration: ALIE Legal Baseline.
4. Add optional case instructions.
5. Start.
6. Watch progress.
7. Review default and secondary events.
8. Export.
```

Example case instruction:

> Focus on work capacity, the evolution of the lumbar condition, imaging findings and the alleged relapse.

## 7.2 Progress view

```text
Documents indexed: 13 / 13
Pages processed: 312 / 363
Reports proposed: 94
Reports read: 71 / 94
Gap review: investigating 8 items
Curation: pending
```

The user may open:

- report map;
- reports with no events;
- uncertain pages;
- reader failures;
- extracted candidates.

## 7.3 Review view

Each chronology row contains:

- date;
- event description;
- document type;
- author;
- source document;
- page;
- supporting quote;
- default or secondary status;
- flags;
- reviewer actions.

Reviewer actions:

- accept;
- edit;
- move to default;
- move to secondary;
- reject;
- merge;
- mark duplicate;
- add reason.

---

# 8. High-level architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL CASE WORKSPACE                     │
│ PDFs · OCR · token maps · pages · reports · outputs · evals │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID INGEST ROUTER                     │
│ native extraction → quality check → OCR only where needed   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   LOCAL TOKENIZATION                        │
│ identifiers → stable tokens · dates → stable date tokens    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 CLAUDE AGENT ORCHESTRATOR                   │
│ inspect → delegate → review → adapt → repeat → finish       │
└────────────┬────────────────┬────────────────┬──────────────┘
             │                │                │
             ▼                ▼                ▼
       Scout Agent      Reader Dispatcher    Gap Agent
             │                │                │
             └────────────────┴────────────────┘
                              │
                              ▼
                         Curator Agent
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL RECONSTRUCTION                     │
│ restore dates · source linkage · queues · exports · metrics │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                         REVIEW UI
```

---

# 9. Execution pattern: orchestrator plus reader dispatcher

A case may contain dozens or hundreds of reports. The master orchestrator should not carry the full transcript of every reader.

Use two execution patterns.

## 9.1 Programmatic subagents for low-volume reasoning

Use Agent SDK subagents for:

- Scout;
- Gap Reviewer;
- Curator;
- optional Critic.

These are a small number of focused tasks that benefit from isolated contexts.

## 9.2 Local reader dispatcher for high-volume work

Expose a custom local tool:

```text
dispatch_readers(report_ids, instructions, concurrency)
```

The tool launches bounded parallel reader sessions outside the orchestrator’s conversation.

Each reader:

- receives one report;
- loads only relevant instructions and skills;
- returns structured candidate events;
- writes its output to the local workspace.

The orchestrator receives a concise dispatch summary, not every transcript.

This preserves the agentic experiment because the orchestrator still decides:

- which reports to read;
- which reports to re-read;
- when boundaries must change;
- when the gap review is complete;
- when curation should begin.

---

# 10. Local case workspace

```text
workspace/
  cases/
    case_001/
      manifest.json
      instructions.md

      source/
        original/
          doc_001.pdf
          doc_002.pdf

      pages/
        doc_001/
          page_0001.json
          page_0001.raw.txt
          page_0001.safe.txt
          page_0001.png

      privacy/
        entity_map.enc.json
        date_map.enc.json
        unresolved.json

      reports/
        report_map.json
        units/
          report_0001.json
          report_0001.safe.txt

      tasks/
        tasks.jsonl

      readers/
        report_0001.result.json
        report_0001.transcript.jsonl

      candidates/
        events.jsonl

      curation/
        assignments.jsonl

      review/
        decisions.jsonl

      output/
        chronology.json
        chronology.csv
        chronology.html

      eval/
        metrics.json
        matches.jsonl
        run_summary.md

      logs/
        run.jsonl
```

For the POC, JSON and JSONL are sufficient. Add SQLite only if file coordination becomes inconvenient.

---

# 11. Core data models

Use Pydantic models and serialize to JSON.

## 11.1 Case manifest

```json
{
  "case_id": "case_001",
  "created_at": "2026-07-20T12:00:00-04:00",
  "configuration": "alie-legal-baseline-v1",
  "case_instructions_path": "instructions.md",
  "documents": [
    {
      "document_id": "doc_001",
      "filename": "bundle_01.pdf",
      "sha256": "...",
      "page_count": 94
    }
  ],
  "run_status": "active"
}
```

## 11.2 Page record

```json
{
  "page_id": "doc_001:p_0012",
  "document_id": "doc_001",
  "page_number": 12,
  "native_character_count": 0,
  "extraction_method": "tesseract",
  "text_quality": 0.76,
  "raw_text_path": "pages/doc_001/page_0012.raw.txt",
  "safe_text_path": "pages/doc_001/page_0012.safe.txt",
  "date_tokens": ["[[DATE_K7M2]]", "[[DATE_A91Q]]"],
  "entity_tokens": ["[[PERSON_01]]", "[[PROVIDER_03]]"],
  "flags": []
}
```

## 11.3 Report unit

```json
{
  "report_id": "report_0042",
  "document_id": "doc_001",
  "page_start": 12,
  "page_end": 15,
  "page_ids": [
    "doc_001:p_0012",
    "doc_001:p_0013",
    "doc_001:p_0014",
    "doc_001:p_0015"
  ],
  "document_type": "medical_consultation",
  "title": "Consultation médicale",
  "boundary_confidence": "medium",
  "boundary_reason": "New physician header and distinct signature block",
  "status": "proposed",
  "flags": []
}
```

## 11.4 Candidate event

```json
{
  "event_id": "event_0104",
  "report_id": "report_0042",
  "event_date_token": "[[DATE_K7M2]]",
  "event_type": "medical_consultation",
  "summary_fr": "Le travailleur consulte pour une recrudescence de lombalgie...",
  "author_token": "[[PROVIDER_03]]",
  "facility_token": "[[FACILITY_02]]",
  "source_pages": [13],
  "quote": "Le patient rapporte une augmentation...",
  "quote_page": 13,
  "reader_confidence": "high",
  "uncertainty": null,
  "cross_references": [
    {
      "description": "Référence à une IRM antérieure",
      "date_token": "[[DATE_A91Q]]"
    }
  ],
  "origin": {
    "reader_run_id": "reader_run_0051",
    "pass": 1,
    "reason_for_pass": "initial"
  },
  "flags": []
}
```

## 11.5 Agent task

```json
{
  "task_id": "task_0087",
  "action": "reread_report",
  "target_ids": ["report_0042"],
  "requested_by": "gap_agent",
  "reason": "Six date tokens are present but only one event was extracted",
  "priority": "high",
  "status": "pending",
  "attempts": 0,
  "result_summary": null
}
```

## 11.6 Curation assignment

```json
{
  "event_id": "event_0104",
  "queue": "default",
  "reason": "Material change in symptoms and work capacity",
  "curator_run_id": "curator_0003"
}
```

## 11.7 Reviewer decision

```json
{
  "event_id": "event_0104",
  "action": "edited",
  "before": {"summary_fr": "..."},
  "after": {"summary_fr": "..."},
  "reason": "Clarify that symptoms were reported, not objectively observed",
  "created_at": "..."
}
```

---

# 12. Hybrid ingest router

## 12.1 Goal

Avoid OCR when a page already contains usable native text.

## 12.2 Per-page routing

1. Attempt native extraction with PyMuPDF, pypdf or pdfplumber.
2. Score the result.
3. Use native text if the quality score passes.
4. Otherwise render the page and run Tesseract `fra+eng`.
5. Preserve the page image and extracted text.

## 12.3 Quality score

Do not use only a `<100 characters` threshold. Combine:

- total characters;
- alphabetic-character ratio;
- printable-character ratio;
- average word length;
- recognizable French or English words;
- repeated garbage patterns;
- extraction of only headers or page numbers.

Starter heuristic:

```python
def usable_native_text(text: str) -> bool:
    if len(text.strip()) < 80:
        return False

    printable_ratio = sum(ch.isprintable() for ch in text) / max(len(text), 1)
    alphabetic_ratio = sum(ch.isalpha() for ch in text) / max(len(text), 1)
    word_count = len(text.split())

    return (
        printable_ratio > 0.95
        and alphabetic_ratio > 0.35
        and word_count >= 12
    )
```

Test this against Case 1.

## 12.4 OCR output

Keep:

- raw OCR;
- normalized whitespace version;
- page image;
- OCR method;
- runtime;
- basic quality signals.

Do not aggressively clean text. Over-cleaning can remove dates, measurements or layout clues.

---

# 13. Local tokenization

## 13.1 Identifier tokens

Replace locally:

- patient names;
- family names;
- provider names;
- addresses;
- telephone numbers;
- email addresses;
- RAMQ numbers;
- claim and file numbers;
- facility names where required;
- employer names where required.

Stable tokens remain consistent across the case:

```text
[[PERSON_01]]
[[PROVIDER_03]]
[[FACILITY_02]]
[[CLAIM_01]]
```

## 13.2 Date tokens

Replace recognized dates with opaque tokens:

```text
[[DATE_K7M2]]
[[DATE_A91Q]]
```

Registry entry:

```json
{
  "token": "[[DATE_K7M2]]",
  "raw_text": "16 juillet 2025",
  "normalized": "2025-07-16",
  "document_id": "doc_001",
  "page": 13,
  "start_char": 482,
  "end_char": 497,
  "confidence": "high"
}
```

## 13.3 Date representation experiment

Test two variants.

### Variant A — opaque token

```text
[[DATE_K7M2]]
```

### Variant B — opaque token plus safe relative metadata

```json
{
  "token": "[[DATE_K7M2]]",
  "relative_order_within_report": 3,
  "relative_to_accident": "after",
  "label_context": "Date de l'examen"
}
```

Do not assume chronologically numbered token names are better. Compare correct-date recall.

## 13.4 Restoration

After extraction, local code maps the selected token back to the normalized date.

If it cannot be resolved:

- preserve the event;
- mark `date_unresolved`;
- show it separately.

---

# 14. Agent architecture

```text
Master Orchestrator
    ├── Scout Agent
    ├── Reader Workers
    ├── Gap Agent
    ├── Curator Agent
    └── Chat Agent — later
```

---

# 15. Master Orchestrator

## 15.1 Objective

Build the best supported chronology possible by examining current case state, assigning work, reviewing outputs and adapting when the first pass appears incomplete or inconsistent.

## 15.2 Inputs

- case objective;
- case instructions;
- baseline configuration;
- manifest;
- report map;
- task list;
- processing summary;
- candidate summary;
- coverage summary;
- failure summary;
- available tools and agents.

The orchestrator should not receive all page text in the main prompt.

## 15.3 Available actions

```text
INSPECT_CASE
INSPECT_DOCUMENT
READ_PAGES
RUN_SCOUT
CREATE_REPORT_UNITS
UPDATE_REPORT_UNIT
MERGE_REPORT_UNITS
SPLIT_REPORT_UNIT
DISPATCH_READERS
REREAD_REPORTS
SEARCH_CASE
RUN_GAP_REVIEW
RUN_CURATOR
INSPECT_CANDIDATES
FINISH
```

## 15.4 Termination conditions

The orchestrator may finish when:

- every page has a known disposition;
- every proposed report is read or marked unreadable;
- reader failures are retried or surfaced;
- high-priority gap suggestions are addressed;
- unresolved items are visible;
- curation is complete;
- another action is unlikely to materially improve the chronology.

POC execution limits:

```text
maximum orchestrator turns: 60
maximum gap iterations: 2
maximum reader passes per report: 3
maximum total reader jobs: configurable
maximum case cost: configurable
```

## 15.5 Orchestrator prompt

```text
You are the Ask ALIE Case Orchestrator.

Your goal is to build a complete, defensible and reviewable medical-legal
chronology from the local case workspace.

You supervise the work. Do not extract chronology events directly unless
explicitly instructed.

At every turn:
1. Inspect the current case state.
2. Identify the highest-value unresolved task.
3. Use the appropriate tool or specialist agent.
4. Review the result.
5. Update the plan.
6. Finish only when another action is unlikely to materially improve the case.

You may:
- ask the Scout to propose or revise report boundaries;
- dispatch report readers;
- re-read a report with targeted instructions;
- inspect suspicious pages;
- follow cross-references;
- run the Gap Agent;
- revise report units;
- run the Curator.

Do not assume the first segmentation or first reader pass is correct.
Do not silently discard candidate events.
Keep work grounded in source pages.
Prefer targeted follow-up work over repeating the whole case.
```

---

# 16. Scout Agent

## 16.1 Objective

Identify reports and meaningful document units inside one or more PDFs.

## 16.2 Input

- document manifest;
- page numbers;
- safe page text;
- current report map when revising;
- case instructions;
- baseline document-type guidance.

## 16.3 Output

```json
{
  "document_id": "doc_001",
  "proposed_units": [
    {
      "page_start": 1,
      "page_end": 2,
      "document_type": "cover_or_index",
      "title": "Bordereau",
      "confidence": "high",
      "reason": "Index format and no clinical narrative"
    },
    {
      "page_start": 3,
      "page_end": 5,
      "document_type": "medical_consultation",
      "title": "Consultation médicale",
      "confidence": "medium",
      "reason": "Physician header on page 3; signature on page 5"
    }
  ],
  "uncertain_ranges": [
    {
      "page_start": 18,
      "page_end": 20,
      "reason": "Possible attachment or second report"
    }
  ]
}
```

## 16.4 Behavior

The Scout may request fuller neighboring pages.

It distinguishes:

- separate report;
- continuation page;
- attachment;
- administrative cover;
- empty page;
- duplicate;
- uncertain page.

## 16.5 Initial strategy

1. Build a compact packet with the first 1,500 and final 500 characters of each page.
2. Ask the Scout for proposed units.
3. Send fuller text for uncertain seams.
4. Write the report map.
5. Allow later orchestrator revision.

---

# 17. Reader Workers

## 17.1 Objective

Read one complete report and extract every dated material event supported by it.

## 17.2 Input

- one report’s complete safe text;
- page markers;
- date token metadata;
- case instructions;
- ALIE baseline reader instructions;
- relevant skills when enabled;
- targeted re-read instruction when applicable.

## 17.3 Output

```json
{
  "report_id": "report_0042",
  "events": [],
  "report_summary": "...",
  "cross_references": [],
  "recommended_followups": [],
  "reader_assessment": {
    "report_type": "medical_consultation",
    "readability": "good",
    "possible_boundary_problem": false,
    "possible_missing_pages": false
  }
}
```

## 17.4 Reader prompt

```text
You are an Ask ALIE Report Reader.

Read the complete report provided to you.

Extract every dated event that is clinically or legally meaningful for a
medical-legal chronology. Do not limit yourself to one event per report.

For every event:
- select the correct event-date token;
- describe what occurred in concise French;
- preserve material diagnoses, findings, treatment, restrictions, work status,
  imaging conclusions and legal decisions;
- identify the author when available;
- cite the source page;
- reproduce a short supporting quote;
- state uncertainty rather than inventing facts.

Distinguish:
- event date;
- accident date;
- report creation date;
- dictation or signature date;
- historical dates mentioned in the narrative;
- planned future dates.

Return zero events when the report truly contains no chronology event.

Also report:
- cross-references to other reports or investigations;
- signs that report boundaries are wrong;
- signs that pages are missing;
- reasons another targeted pass may be useful.
```

## 17.5 Targeted re-read example

```text
Re-read this report specifically for:
- work-stoppage periods;
- changes in functional limitations;
- multiple treatment dates;
- historical imaging references;
- accepted and rejected diagnoses.
Do not repeat events already captured unless correcting them.
```

## 17.6 Concurrency

Start with:

```text
max_concurrency = 5
```

Increase only after observing rate behavior, report size, cost and local resource use.

---

# 18. Gap Agent

## 18.1 Objective

Review the completed first pass and identify areas where valuable reports or events may have been missed.

## 18.2 Input

- report map;
- reports with zero events;
- candidate summaries;
- page and date coverage summary;
- cross-references;
- unresolved Scout ranges;
- reader flags;
- case instructions;
- baseline required categories.

## 18.3 Output

The Gap Agent returns tasks, not chronology rows.

```json
{
  "tasks": [
    {
      "action": "reread_report",
      "target_ids": ["report_0042"],
      "priority": "high",
      "reason": "Six treatment dates appear but only one event was extracted",
      "instructions": "Extract each material treatment or meaningful change"
    },
    {
      "action": "inspect_pages",
      "target_ids": ["doc_001:p_0088", "doc_001:p_0089"],
      "priority": "high",
      "reason": "Possible CNESST decision absent from chronology"
    },
    {
      "action": "resegment",
      "target_ids": ["report_0020"],
      "priority": "medium",
      "reason": "Two authors and two signature blocks suggest two reports"
    }
  ],
  "assessment": "The first pass is likely incomplete in imaging and work status."
}
```

## 18.4 Useful gap signals

- reports with zero events;
- pages containing several date tokens but no cited event;
- referenced MRI, surgery, expertise or decision absent from the map;
- long report with one event;
- required legal decision type absent from chronology;
- changes in work status mentioned but not captured;
- reader indicating missing pages;
- conflicting events;
- suspiciously long report unit;
- multiple authors or signature blocks in one unit;
- unassigned pages.

Start with two gap iterations and measure the added value of each.

---

# 19. Curator Agent

## 19.1 Objective

Organize all supported candidate events into a compact default queue and a complete secondary queue.

## 19.2 Output

```json
{
  "event_id": "event_0104",
  "queue": "default",
  "reason": "Material change in symptoms and work capacity",
  "duplicate_of": null,
  "needs_review": false
}
```

## 19.3 Rules

- Curation does not delete candidates.
- Mandatory event types remain default under the baseline.
- Supported routine events may be secondary.
- Uncertain or conflicting events are flagged.
- Duplicate candidates may be linked.
- Extraction recall is measured before curation.

## 19.4 Initial mandatory-default categories

- accident or incident;
- emergency assessment;
- new diagnosis;
- material diagnostic change;
- imaging conclusion;
- surgery;
- specialist consultation;
- expertise;
- work stoppage;
- return-to-work change;
- functional limitations;
- consolidation or maximum medical improvement;
- permanent impairment;
- relapse, recurrence or aggravation;
- CNESST, SAAQ or IVAC decision;
- tribunal or review decision;
- material treatment change.

These are ALIE baseline rules, not a personalized firm profile.

---

# 20. Chat Agent — later phase

Do not build chat until chronology extraction passes validation.

Tools:

```text
search_events(query, filters)
search_reports(query, filters)
search_pages(query, filters)
open_report(report_id)
open_pages(page_ids)
get_case_summary()
get_unresolved_items()
```

Answers must:

- cite source pages;
- distinguish candidates from approved chronology rows;
- state uncertainty;
- avoid answering from model memory when case evidence is absent.

Qdrant and Ollama embeddings may be added here. They are not required for chronology generation.

---

# 21. Tool registry

Expose local functions through an in-process MCP server.

## 21.1 Read tools

### `get_case_state`

Returns a concise case summary.

```json
{
  "document_count": 13,
  "page_count": 363,
  "report_count": 94,
  "reports_read": 71,
  "candidate_count": 129,
  "pending_tasks": 8,
  "flags": []
}
```

### `inspect_document`

```json
{
  "document_id": "doc_001",
  "page_start": 1,
  "page_end": 20,
  "mode": "headers"
}
```

### `read_pages`

```json
{
  "page_ids": ["doc_001:p_0012", "doc_001:p_0013"],
  "safe_text_only": true
}
```

### `inspect_report`

```json
{
  "report_id": "report_0042",
  "include_reader_results": true
}
```

### `search_case`

```json
{
  "query": "IRM lombaire",
  "scope": "safe_pages",
  "max_results": 20
}
```

### `list_candidates`

```json
{
  "report_ids": [],
  "flags": [],
  "limit": 100
}
```

## 21.2 Write tools

### `save_report_map`

Stores Scout-proposed units.

### `update_report_units`

Supports split, merge, resize, relabel and mark uncertain.

### `dispatch_readers`

```json
{
  "report_ids": ["report_0042", "report_0043"],
  "reason": "initial",
  "instructions": null,
  "max_concurrency": 5
}
```

Returns:

```json
{
  "submitted": 2,
  "completed": 2,
  "failed": 0,
  "new_candidate_events": 6,
  "result_paths": [
    "readers/report_0042.result.json",
    "readers/report_0043.result.json"
  ]
}
```

### `create_tasks`

Writes Gap or orchestrator tasks.

### `resolve_tasks`

Marks tasks complete.

### `run_curator`

Runs curation over current candidates.

### `finish_case`

Finalizes outputs and metrics.

## 21.3 Tool rules

Each tool should:

- perform one understandable operation;
- use clear parameter names;
- return concise structured output;
- write large results to files and return paths;
- avoid returning hundreds of pages into agent context;
- provide explicit errors;
- be idempotent where practical.

---

# 22. Claude Agent SDK implementation

## 22.1 Stack

- Python 3.12
- `claude-agent-sdk`
- Pydantic 2
- FastAPI
- PyMuPDF
- Tesseract
- spaCy French
- Presidio or custom recognizers
- SQLite optional
- Next.js, React or Streamlit for the local UI
- pytest

## 22.2 Programmatic subagents

```python
from claude_agent_sdk import AgentDefinition

AGENTS = {
    "scout": AgentDefinition(
        description=(
            "Use when the case needs report boundaries proposed, reviewed "
            "or corrected."
        ),
        prompt=SCOUT_SYSTEM_PROMPT,
        tools=[
            "mcp__ask_alie__inspect_document",
            "mcp__ask_alie__read_pages",
            "mcp__ask_alie__save_report_map",
        ],
        model="sonnet",
    ),
    "gap-reviewer": AgentDefinition(
        description=(
            "Use after initial report reading to identify probable missing "
            "reports or events and propose targeted follow-up tasks."
        ),
        prompt=GAP_SYSTEM_PROMPT,
        tools=[
            "mcp__ask_alie__get_case_state",
            "mcp__ask_alie__inspect_report",
            "mcp__ask_alie__search_case",
            "mcp__ask_alie__create_tasks",
        ],
        model="sonnet",
    ),
    "curator": AgentDefinition(
        description=(
            "Use when candidate extraction and gap review are complete to "
            "assign default and secondary chronology queues."
        ),
        prompt=CURATOR_SYSTEM_PROMPT,
        tools=[
            "mcp__ask_alie__list_candidates",
            "mcp__ask_alie__run_curator",
        ],
        model="sonnet",
    ),
}
```

## 22.3 In-process MCP tools

```python
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    "get_case_state",
    "Return a concise summary of the current Ask ALIE case state.",
    {
        "include": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
)
async def get_case_state(args: dict[str, Any]) -> dict[str, Any]:
    state = load_case_state(args["include"])

    return {
        "content": [
            {"type": "text", "text": state.model_dump_json()}
        ],
        "structuredContent": state.model_dump(),
    }

ask_alie_server = create_sdk_mcp_server(
    name="ask_alie",
    version="0.1.0",
    tools=[
        get_case_state,
        inspect_document,
        read_pages,
        save_report_map,
        update_report_units,
        dispatch_readers,
        search_case,
        create_tasks,
        run_curator,
        finish_case,
    ],
)
```

## 22.4 Orchestrator session

```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

async def run_case(case_dir: str) -> None:
    options = ClaudeAgentOptions(
        cwd=case_dir,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        allowed_tools=[
            "Agent",
            "mcp__ask_alie__get_case_state",
            "mcp__ask_alie__inspect_document",
            "mcp__ask_alie__read_pages",
            "mcp__ask_alie__save_report_map",
            "mcp__ask_alie__update_report_units",
            "mcp__ask_alie__dispatch_readers",
            "mcp__ask_alie__search_case",
            "mcp__ask_alie__create_tasks",
            "mcp__ask_alie__run_curator",
            "mcp__ask_alie__finish_case",
        ],
        mcp_servers={"ask_alie": ask_alie_server},
        agents=AGENTS,
        setting_sources=["project"],
        skills=[],
        max_turns=60,
    )

    prompt = """
    Build the chronology for the case in this working directory.

    Start by inspecting the case state. Use the Scout when report units do not
    exist. Dispatch readers after the report map is usable. Review the results,
    run a gap review, perform targeted follow-up work, curate the candidates and
    finish the case.
    """

    async for message in query(prompt=prompt, options=options):
        stream_progress_to_ui(message)

        if isinstance(message, ResultMessage):
            save_session_result(message)

asyncio.run(run_case("workspace/cases/case_001"))
```

## 22.5 Structured output

Use Agent SDK structured outputs for:

- Scout results;
- Gap tasks;
- Curator assignments;
- Reader results.

Define Pydantic schemas and pass their generated JSON Schema through `output_format`. Do not parse arbitrary Markdown where validated structured output is available.

## 22.6 Sessions

Store:

- orchestrator session ID;
- reader session IDs;
- result paths;
- start and completion time;
- model;
- reason for execution.

Resume the orchestrator when reopening the case. The local case state remains authoritative even if a session is restarted.

---

# 23. Reader dispatcher

## 23.1 Purpose

Run many readers without filling the orchestrator context.

## 23.2 Execution

For each report:

1. Create reader prompt.
2. Start a fresh Agent SDK query session.
3. Allow only minimum tools.
4. Load the report file.
5. Return structured output.
6. Save result.
7. Append candidate events.
8. Return a concise batch summary.

## 23.3 Pseudocode

```python
async def dispatch_reader_jobs(
    report_ids: list[str],
    reason: str,
    instructions: str | None,
    max_concurrency: int = 5,
) -> DispatchSummary:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(report_id: str) -> ReaderJobResult:
        async with semaphore:
            report = load_report(report_id)

            try:
                result = await run_reader_agent(
                    report=report,
                    instructions=instructions,
                    reason=reason,
                )
                save_reader_result(result)
                append_candidate_events(result.events)
                return ReaderJobResult.success(result)
            except Exception as exc:
                record_reader_failure(report_id, exc)
                return ReaderJobResult.failure(report_id, str(exc))

    results = await asyncio.gather(
        *(run_one(report_id) for report_id in report_ids)
    )

    return summarize_dispatch(results)
```

## 23.4 Model strategy

Start with the same capable model for all readers. Test cheaper models only after the capable-model baseline is known.

---

# 24. Personalization architecture

Personalization is not required for the baseline POC, but the architecture must leave a clear path.

## 24.1 Layers

### Layer 1 — case instructions

Temporary and case-specific.

Examples:

- focus on work capacity;
- include every physiotherapy session;
- examine recurrence;
- prioritize imaging.

Stored in:

```text
cases/<case_id>/instructions.md
```

### Layer 2 — user preferences

Persistent presentation or prioritization choices.

Examples:

- concise wording;
- imaging conclusions verbatim;
- default queue density;
- terminology;
- export columns.

### Layer 3 — skills

Reusable task methods.

Examples:

- read a CNESST decision;
- extract imaging findings;
- track work capacity;
- review an expertise;
- find recurrence evidence.

### Layer 4 — profiles

A named bundle of:

- skills;
- preferences;
- materiality rules;
- output configuration.

### Layer 5 — learned review patterns

Suggestions derived from repeated reviewer actions.

Example:

> You moved every work-stoppage extension to the default queue in four cases. Save this as a preference?

Persistent changes require user approval.

## 24.2 Precedence

```text
Current-case instruction
    overrides
User-specific skill or preference
    overrides
Organization profile
    overrides
Practice-area profile
    overrides
ALIE baseline instructions
```

## 24.3 Rollout

### POC Phase A

- ALIE Legal Baseline only.
- Optional case instructions.
- No user-created skills.
- No profile-selection requirement.

### POC Phase B

- Record reviewer edits structurally.
- Add simple saved preferences.
- Keep suggestions manual.

### Product Phase C

- Create skills from corrections.
- Enable user and organization scopes.
- Build profile bundles.

### Product Phase D

- Suggest skills from repeated patterns.
- Add profile versioning and comparison.

---

# 25. Agent Skills

The Claude Agent SDK discovers Skills as filesystem artifacts.

## 25.1 Structure

```text
.claude/
  skills/
    read-cnesst-decision/
      SKILL.md
    read-imaging-report/
      SKILL.md
    track-work-capacity/
      SKILL.md
    analyze-relapse-recurrence/
      SKILL.md
```

## 25.2 Example Skill

```markdown
---
name: read-cnesst-decision
description: >
  Use when reading a CNESST administrative decision, review decision or
  entitlement determination.
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
```

For the initial POC, keep `skills=[]`. Introduce the first Skill only after the baseline reader and orchestrator work.

---

# 26. ALIE Legal Baseline configuration

```yaml
name: alie-legal-baseline-v1
language: fr-CA

reader:
  extract_multiple_events_per_report: true
  preserve_imaging_measurements: true
  preserve_diagnoses: true
  include_work_status: true
  include_functional_limitations: true

curation:
  mandatory_default:
    - accident
    - emergency_visit
    - imaging
    - surgery
    - expertise
    - work_stoppage
    - return_to_work_change
    - functional_limitation
    - consolidation
    - permanent_impairment
    - relapse_recurrence
    - administrative_decision

  likely_secondary:
    - routine_prescription_renewal
    - unchanged_followup
    - duplicate_fax
```

This is a test configuration, not a client profile.

---

# 27. Review UI requirements

## 27.1 Case list

- case name;
- status;
- page count;
- report count;
- run date;
- configuration;
- open button.

## 27.2 Run screen

Panels:

1. Documents
2. Progress
3. Agent activity
4. Report map
5. Candidate events
6. Flags

Activity entries:

```text
Scout proposed 94 report units.
71 reports completed their initial reader pass.
Gap review requested 8 follow-up tasks.
Report 42 was split into two units.
Curator assigned 58 events to default and 41 to secondary.
```

## 27.3 Chronology screen

Columns:

- Date
- Type
- Description
- Author
- Source
- Page
- Status

Expanded row:

- quote;
- report context;
- extraction pass;
- curator reason;
- flags;
- reviewer controls.

## 27.4 Secondary queue

One click away. Secondary means supported but lower priority, not unsupported.

## 27.5 Unresolved queue

Show:

- unreadable pages;
- unresolved dates;
- reader failures;
- uncertain boundaries;
- unsupported candidates;
- conflicts.

---

# 28. Evaluation design

## 28.1 Cases

```text
case1_cnesst
  Development case
  74 gold events

case2_saaq
  Locked validation
  36 gold events

case3_ivac
  Locked final validation
  61 gold events
```

## 28.2 Gold protection

Gold chronologies must not be:

- included in prompts;
- loaded into agent context;
- converted into skills;
- used as examples;
- used to write profiles;
- visible during blind validation.

## 28.3 Matching

Use:

- normalized date match;
- semantic event similarity;
- key fact overlap;
- manual adjudication for uncertain matches.

Store each match:

```json
{
  "gold_event_id": "gold_0012",
  "candidate_event_id": "event_0104",
  "date_match": true,
  "meaning_match": "full",
  "reviewer": "uzziel",
  "notes": null
}
```

## 28.4 Defensible extra rubric

An extra is defensible when:

- it is a real event;
- its date is supported;
- its description is supported;
- it is potentially useful to the lawyer;
- it is not merely a duplicate wording variation.

## 28.5 Stability

Run each major experiment twice and compare:

- exact candidate overlap;
- semantic overlap;
- gold capture variance;
- default queue variance;
- cost variance.

---

# 29. Experiment sequence

## Experiment 0 — ingest benchmark

Question:

> How much of Case 1 is native text versus OCR?

Measure:

- native pages;
- OCR pages;
- extraction duration;
- unusable pages.

## Experiment 1 — whole-report reader baseline

Use the best current report units. No adaptive loop.

Measure:

- candidate recall;
- wrong dates;
- rows emitted;
- report-level failures.

This isolates the value of whole-report reading.

## Experiment 2 — Scout segmentation

Generate new units with the Scout. Run the same readers.

Compare:

- segmentation quality;
- gold capture;
- emitted rows;
- report count;
- over- and under-segmentation.

## Experiment 3 — adaptive orchestrator

Add:

- state inspection;
- Gap Agent;
- targeted re-reading;
- boundary revision;
- cross-reference following.

Measure:

- events recovered after first pass;
- tasks executed;
- added cost;
- unsupported rows added.

## Experiment 4 — Curator

Measure:

- default count;
- gold events left in secondary;
- unsupported events in default;
- reviewer time.

## Experiment 5 — personalization pilot

After baseline success:

- add one case instruction;
- add one approved Skill;
- compare with baseline.

Do not build a profile editor.

## Experiment 6 — blind validation

Freeze prompts, configuration, Skills, model allocation and tool behavior. Run Cases 2 and 3.

---

# 30. Milestones

## Milestone 1 — repository and workspace

Deliver:

- project skeleton;
- environment setup;
- manifest creation;
- page storage;
- run command;
- test fixture.

Exit when:

```text
python -m ask_alie ingest <case_folder>
```

creates a complete workspace.

## Milestone 2 — ingest and tokenization

Deliver:

- native extraction;
- OCR fallback;
- page quality;
- entity tokens;
- date tokens;
- token maps.

Exit when Case 1 safe page text exists and date restoration is tested.

## Milestone 3 — reader baseline

Deliver:

- initial report map import;
- reader schema;
- dispatcher;
- candidate store;
- Case 1 evaluation.

Exit with a full candidate metric report.

## Milestone 4 — Scout

Deliver:

- Scout subagent;
- document packet builder;
- report map writer;
- uncertainty handling.

Exit with a comparison against current report units.

## Milestone 5 — orchestrator and tools

Deliver:

- in-process MCP server;
- orchestrator session;
- adaptive action loop;
- progress stream;
- task records.

Exit when the orchestrator can run the Scout and dispatch readers from case state.

## Milestone 6 — gap loop

Deliver:

- Gap Agent;
- task creation;
- targeted re-reading;
- report revision.

Exit with the number of events recovered by the gap loop.

## Milestone 7 — curation and UI

Deliver:

- Curator;
- default and secondary queues;
- review UI;
- reviewer actions;
- export.

Exit when a reviewer can approve a chronology.

## Milestone 8 — blind validation

Deliver:

- frozen Case 2 and Case 3 runs;
- stability results;
- cost report;
- recommendation.

Exit with a founder decision: continue, revise or stop.

## Milestone 9 — personalization

Only after the decision to continue.

Deliver:

- saved preferences;
- one Skill-creation workflow;
- profile bundle design.

---

# 31. Repository structure

```text
ask-alie-agentic/
  README.md
  pyproject.toml
  .env.example
  CLAUDE.md

  ask_alie/
    __init__.py
    cli.py
    config.py

    ingest/
      extract.py
      quality.py
      ocr.py
      render.py

    privacy/
      tokenize.py
      entities.py
      dates.py
      registry.py

    workspace/
      manifest.py
      paths.py
      state.py

    reports/
      models.py
      packet.py
      map.py
      service.py

    agents/
      runtime.py
      definitions.py
      prompts/
        orchestrator.md
        scout.md
        reader.md
        gap.md
        curator.md

    tools/
      case_state.py
      documents.py
      reports.py
      readers.py
      search.py
      tasks.py
      curation.py
      server.py

    readers/
      dispatcher.py
      runner.py
      schema.py
      merge.py

    events/
      models.py
      store.py
      restore.py
      duplicates.py

    curation/
      models.py
      service.py

    review/
      service.py
      export.py

    evals/
      gold.py
      match.py
      metrics.py
      report.py

  .claude/
    skills/
      # empty for baseline

  ui/
    # minimal local UI

  tests/
    unit/
    integration/
    fixtures/

  workspace/
    # gitignored
```

---

# 32. CLAUDE.md

Use `CLAUDE.md` for persistent project instructions.

```markdown
# Ask ALIE agent runtime

## Objective

Build a sourced chronology from the active case workspace.

## Persistent rules

- Never read files outside the active case directory.
- Use safe page and report text, not raw source text.
- Do not create events from unsupported assumptions.
- Preserve source page references.
- Do not silently delete candidate events.
- Use specialist agents for scouting, gap review and curation.
- Use the reader dispatcher for report extraction.
- Prefer targeted follow-up work to repeating the whole case.

## State

The authoritative state is stored in case JSON and JSONL files.
Do not rely only on conversation memory.

## Completion

Before finishing, inspect:
- report coverage;
- reader failures;
- pending high-priority tasks;
- Gap Agent output;
- curation status.
```

---

# 33. Minimal logging

One JSONL entry per meaningful action:

```json
{
  "timestamp": "...",
  "actor": "orchestrator",
  "action": "dispatch_readers",
  "targets": ["report_0042", "report_0043"],
  "reason": "Initial report pass",
  "result": {
    "completed": 2,
    "failed": 0,
    "candidate_events": 6
  }
}
```

Track:

- stage duration;
- model;
- input and output tokens;
- cost where available;
- retries;
- result path;
- error.

A generated `run_summary.md` is enough. Do not build a monitoring platform.

---

# 34. Failure handling

## OCR failure

- keep page image;
- mark unreadable;
- show it;
- continue.

## Scout uncertainty

- assign uncertain range;
- request neighboring pages;
- allow overlapping fallback unit;
- continue.

## Reader schema failure

- retry once;
- retry with a simpler prompt once;
- mark failed;
- expose to orchestrator.

## Reader timeout

- retry;
- split oversized report if necessary;
- preserve failure.

## Wrong boundary

- split or merge;
- invalidate only affected reader results;
- re-run affected units.

## Duplicate events

- link duplicates;
- do not delete during extraction;
- let Curator or reviewer merge them.

## Unbounded loop

Use the execution limits defined in Section 15.

## Invalid writes

Prefer validated domain tools over unrestricted file writes.

---

# 35. Testing strategy

## 35.1 Unit tests

- native-text quality;
- page IDs;
- report IDs;
- date parsing;
- token stability;
- date restoration;
- workspace paths;
- event serialization;
- metric calculations.

## 35.2 Integration test

Ingest a five-page fixture, tokenize it, create units, dispatch one reader, save a candidate, restore its date and export a chronology.

## 35.3 Agent test sets

### Scout

- two reports in one PDF;
- continuation without header;
- attachment;
- blank fax page;
- boundary near a page break.

### Reader

- one event;
- multiple events;
- several date roles;
- no event;
- imaging measurements;
- work-status changes.

### Gap

- zero-event report;
- missing referenced MRI;
- over-merged report;
- unrepresented decision.

### Curator

- mandatory default;
- routine secondary;
- duplicate;
- uncertain event.

---

# 36. Initial build checklist

## Environment

```text
[ ] Python 3.12
[ ] Tesseract installed
[ ] fra and eng language packs
[ ] ANTHROPIC_API_KEY configured
[ ] claude-agent-sdk installed
[ ] Case 1 bundle available
[ ] Gold chronology isolated from runtime
```

## Ingest

```text
[ ] PDFs enumerated
[ ] page images rendered
[ ] native text extracted
[ ] OCR fallback works
[ ] page quality stored
```

## Tokenization

```text
[ ] dates detected
[ ] stable date map written
[ ] basic entities tokenized
[ ] safe text written
[ ] restoration tested
```

## Reader baseline

```text
[ ] report fixture available
[ ] reader Pydantic schema
[ ] one reader run
[ ] parallel dispatcher
[ ] candidate store
[ ] Case 1 metrics
```

## Agentic loop

```text
[ ] custom MCP tools
[ ] Scout
[ ] Orchestrator
[ ] Gap Agent
[ ] task execution
[ ] Curator
```

## Review

```text
[ ] default queue
[ ] secondary queue
[ ] source quote
[ ] page reference
[ ] accept/edit/reject
[ ] export
```

---

# 37. Proposed commands

```bash
python -m ask_alie ingest \
  --input "C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\inputs" \
  --case-id case1-agentic

python -m ask_alie tokenize \
  --case workspace/cases/case1-agentic

python -m ask_alie readers \
  --case workspace/cases/case1-agentic \
  --concurrency 5

python -m ask_alie evaluate \
  --case workspace/cases/case1-agentic \
  --gold "C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\normalized\gold_events.jsonl"

python -m ask_alie run \
  --case workspace/cases/case1-agentic

python -m ask_alie serve \
  --case workspace/cases/case1-agentic
```

---

# 38. Immediate implementation order

## Step 1

Run a native-text versus OCR inventory on Case 1.

Output:

```text
total pages
native usable
OCR required
empty or unreadable
ingest duration
```

## Step 2

Create the workspace and stable date-token registry. Test restoration on real Case 1 pages.

## Step 3

Use existing report units or manually define 10–20 reports. Build the reader schema and dispatcher. Do not wait for the Scout.

## Step 4

Score the whole-report reader baseline.

This answers:

> Does giving the complete report to a model improve the chronology?

## Step 5

Build the Scout and generate an alternative report map. Run readers again and compare.

## Step 6

Build the orchestrator initially with only:

```text
get_case_state
inspect_document
dispatch_readers
search_case
create_tasks
run_curator
finish_case
```

Add split and merge tools when actually needed.

## Step 7

Add the Gap Agent. Measure events recovered after the initial pass.

## Step 8

Add Curator and review UI.

## Step 9

Freeze and validate.

## Step 10

Introduce the first personalized Skill only after baseline validation.

---

# 39. Decisions resolved

1. Build the legal CNESST baseline first.
2. Do not require profiles before the baseline works.
3. Allow optional case instructions from the beginning.
4. Introduce Skills later as reusable methods derived from demonstrated needs.
5. Use a real adaptive orchestrator, not only a fixed multi-call pipeline.
6. Use a bounded reader dispatcher for large fan-out.
7. Build chronology before chat.
8. Keep the POC local, simple and measurable.
9. Do not rebuild elaborate deterministic event machinery.
10. Judge the architecture by Case 1, Case 2 and Case 3 results.

---

# 40. Open implementation decisions

Resolve these with small experiments.

## Native extractor

Compare PyMuPDF, pypdf and pdfplumber.

## Date representation

Compare opaque tokens with opaque tokens plus relative metadata.

## Scout packet size

Compare header/footer summaries with full-page text and a two-stage request.

## Reader model

Start capable, then test cheaper.

## State storage

Start JSON/JSONL. Move to SQLite only if concurrent writes or queries become irritating.

## Evidence quote

Start with a returned quote and local substring verification. If mismatches become material, move to stable line or span IDs.

## UI

Use the fastest usable option: Next.js, FastAPI templates or Streamlit. Do not let UI architecture delay the extraction experiment.

---

# 41. Definition of done

The POC is complete when:

1. A user can select Case 1 and start a run.
2. Native and OCR pages are processed.
3. Identifiers and dates are replaced locally.
4. The Scout creates report units.
5. Reader workers process every usable report.
6. The orchestrator inspects the result.
7. The Gap Agent proposes targeted follow-ups.
8. The orchestrator executes useful follow-ups.
9. The Curator produces default and secondary queues.
10. The user can inspect every row’s source page and quote.
11. The user can edit, accept, reject or move rows.
12. The chronology can be exported.
13. The evaluation report shows captured gold events, total emitted, defensible extras, unsupported extras, correct-date rate, events recovered by the agentic loop, cost, duration and stability.
14. The team can state clearly whether the agentic loop materially improved the result.

---

# 42. Final product principle

Ask ALIE should not ask users to design the intelligence before they experience its value.

The product begins with:

> Upload the case, tell ALIE what matters in this file, and let it build the chronology.

Then:

> Review the result, correct it, and turn repeated corrections into reusable Skills.

The baseline proves the reasoning system.

Skills personalize specialized methods.

Preferences personalize presentation.

Profiles bundle proven Skills and preferences for a user, firm or practice area.

That is the path from a working agentic POC to a personalized “Claude for lawyers.”
