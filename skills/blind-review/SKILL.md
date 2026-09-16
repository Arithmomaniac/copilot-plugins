---
name: blind-review
description: Review an artifact through fresh, deliberately constrained context as an uninvolved third party. Use only when the user explicitly requests context isolation with phrases such as "blind reviewer", "blank reviewer", "oblivious reviewer", "fresh-eyes review", "third-party review", "review without context", or "triple blind review". Do not infer it merely because another review might help.
---

> Created/edited by GitHub Copilot with human review/feedback by avilevin.

# Blind Review

Review an artifact as though encountering the finished deliverable for the first time. The defining constraint is context isolation, not model count.

## When to use

- The user asks for a blind, blank, oblivious, fresh-eyes, or third-party review.
- The user explicitly wants to know whether an artifact makes sense without its development or investigation history.
- The user asks for a double or triple blind review using independent models.

## When not to use

- For ordinary code-defect review, use `code-review`.
- For multi-model code review with full task context, use `tri-review`.
- For collaborative design critique where the reviewer should know the reasoning history, use `rubber-duck`.
- Do not activate merely because an artifact could benefit from another review or might contain assumptions its author no longer notices.
- Do not use this for anonymous academic peer review or accessibility-related uses of "blind".

## Model selection

Blind review benefits more from independence and repeatability than maximum single-call depth. Read [reference.md](reference.md) when selecting reviewer models or constructing the reviewer prompt. Use the default context tier unless the supplied artifact requires long context.

## Workflow

### 1. Define the review boundary

Identify:

- the exact artifact or diff to review;
- which supplied artifact is primary, and which artifacts are references, evidence, or answer keys;
- its intended audience and purpose;
- whether it is expected to stand alone;
- any review lens explicitly requested by the user.

Also define the artifact's **depth boundary** before reviewing. A proposal should be complete enough to support a decision and identify deferred design work; it should not be judged as though it were already the implementation specification. A primer should explain concepts without resolving every downstream API choice. Reviewers must assess the artifact against its stated purpose, not against the most detailed artifact that could theoretically be written.

When the task asks the reviewer to reconstruct meaning independently, do not expose the reference or answer key until after the reconstruction is complete.

Do not add suspected defects to the prompt unless the user explicitly requests a focused review. Seeding the reviewer with the parent's theory weakens the blind test.

### 2. Create a fresh reviewer

Launch a new subagent that receives only:

- the artifact or exact review scope;
- its intended audience and purpose;
- the role of each supplied artifact: primary subject, reference, evidence, or answer key;
- the review rubric;
- essential domain facts a real reader would reasonably possess.

Do not disclose:

- authoring, investigation, or conversation history;
- earlier reviewer findings;
- the parent's conclusions or suspected defects;
- why particular decisions were made;
- discarded alternatives or iterative corrections.

Use a read-only reviewer. The reviewer reports findings and must not edit the artifact.

### 3. Apply the default rubric

Ask whether the artifact:

- makes sense on its own to the intended audience;
- contains development history, verification asides, migration residue, or commentary about earlier versions;
- bears scars of an agent correcting its own work;
- assumes unstated context or uses undefined internal jargon;
- contradicts itself or blurs current, proposed, and historical behavior;
- overstates evidence, causality, confidence, or implementation status;
- explains the writing process instead of helping the eventual reader;
- omits prerequisites, limitations, ownership, or concrete next actions.

Missing context is an artifact finding. The reviewer must not request hidden authoring history merely to make the artifact appear coherent.

When a reference or answer key is supplied, first record the independent interpretation of the primary artifact, then compare it with the reference.

### 4. Apply a materiality threshold

A finding is material only when it causes a realistic outside reader to:

- misunderstand the artifact's decision, behavior, scope, status, or next action;
- encounter a contradiction between sections, diagrams, examples, or gates;
- be unable to act because a necessary prerequisite, owner, dependency, or boundary is missing;
- rely on an overstated or unsupported claim.

Do not report:

- requests to turn a proposal into a complete implementation specification;
- implementation choices the artifact explicitly and appropriately defers;
- additive detail that would be useful but is not needed for the artifact's purpose;
- stylistic preferences, optional examples, or "could be clearer" comments without a concrete misunderstanding;
- attribution/disclaimer text required by the artifact's documentation convention;
- a concern created only because an earlier review fix added unnecessary detail.

Prefer the smallest **subtractive** correction. Remove ambiguity or excess text before adding new machinery, contracts, diagrams, or sections.

### 5. Use independent reviewers for multi-model review

For a triple blind review, use the current tri-review skill's three-family selection, including its active-family exclusion and maximum-depth rules, but give each reviewer the blind-review rubric rather than the code-review rubric. Launch all three reviewers in parallel and do not reveal one reviewer's output to another.

### 6. Adjudicate

After the reviewers finish:

1. Merge duplicate findings.
2. Treat consensus as stronger evidence, not automatic truth.
3. Verify findings against the artifact.
4. Discard speculative or purely stylistic comments.
5. Preserve a single-reviewer finding only when it identifies a concrete outsider-facing problem.
6. Reject findings that exceed the artifact's depth boundary.
7. Move legitimate implementation questions into an explicit deferred-decisions section rather than expanding the main artifact into a specification.

Do not edit the artifact unless the user also asked for fixes.

### 7. Re-review is opt-in

Every re-review must launch a new subagent. Never reuse a reviewer that saw an earlier version or previous findings.

By default, perform **exactly one review round**. After reporting findings:

- do not apply fixes unless the user asks;
- if the user asks for fixes, apply them but do not automatically re-review;
- do not launch another reviewer unless the user explicitly asks for a re-review or loop.

Re-review or looping is enabled only by explicit language such as:

- "review again";
- "next pass";
- "re-review after fixing";
- "loop until clear";
- "continue reviewing until satisfied."

When looping is explicitly enabled, the review budget is:

- the initial review round;
- at most two fix-and-re-review rounds;
- after a triple review, use one fresh standard reviewer for rechecks unless the user explicitly requests another triple review.

For an opted-in loop:

1. Apply only adjudicated material fixes, preferring deletions and local clarifications.
2. Launch a fresh reviewer.
3. Stop when the adjudicated verdict is `CLEAR` **or functionally clear**: no finding remains that blocks the artifact's stated purpose.
4. Stop after the review budget even if a fresh reviewer can still suggest more detail. Report the remaining non-blocking questions and ask before spending another review budget.

Do not treat literal reviewer output as the stopping authority. The parent adjudicator decides whether the artifact is functionally clear.

### 8. Detect review churn

When a loop was explicitly requested, stop it early when any of these occur:

- consecutive rounds move into narrower implementation mechanics rather than outsider-facing clarity;
- fixes increase the artifact's size or conceptual surface without resolving a blocker;
- new findings are consequences of detail added solely to satisfy earlier reviewers;
- only single-reviewer findings remain and they do not pass the materiality threshold;
- the same concern category returns after two attempted fixes;
- the artifact's purpose has shifted during review.

When churn is detected:

1. Do not apply the latest finding automatically.
2. Restore or prefer the simpler statement when possible.
3. Summarize which remaining questions belong in implementation planning, not the reviewed artifact.
4. Return the adjudicated verdict based on fitness for purpose.

## Reviewer prompt

Use the exact prompt in [reference.md](reference.md). Keep the prompt isolated from authoring history and prior findings.

## Output

Present:

1. **Verdict:** `CLEAR` or `NEEDS WORK`
2. **Consensus findings:** when multiple reviewers agree
3. **Material single-reviewer findings:** only after adjudication
4. **Assessment:** whether the artifact works as a finished third-party deliverable

Do not mechanically forward every reviewer comment.

If the review budget ends without literal `CLEAR`, distinguish:

- **Blocking findings** that prevent the artifact from serving its purpose;
- **Deferred implementation questions** that belong in later design work;
- **Non-blocking polish** that should not extend the review loop.
