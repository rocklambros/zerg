# New Templates for brainstorm.details.md

## 1. Saturation Detection

**Definition**: Discovery is saturated when 2 consecutive answers introduce zero new entities, constraints, or requirements compared to what is already captured.

**Signal phrases**: "that's about it", "nothing else", "same as before", confirmations reiterating prior points without new information.

**Rules**:
- Minimum 3 questions before checking for saturation
- Count new entities/constraints/requirements per answer
- If count == 0 for 2 consecutive answers -> stop
- Announce: "Discovery complete -- your answers have converged."

**Entity tracking**: Maintain a running set of {entities, constraints, requirements} extracted from each answer. Compare each answer's extracted set against the cumulative set. New items = set difference.

---

## 2. Trade-off Round Templates

Present architectural alternatives via AskUserQuestion. Each option carries a one-line pro and one-line con so the user can make an informed choice without leaving the conversation.

### Format

```
AskUserQuestion:
  header: "Trade-off {N}"
  question: "{description of architectural decision}"
  multiSelect: false
  options:
    - label: "{Option A}"
      description: "Pro: {benefit}. Con: {drawback}."
    - label: "{Option B}"
      description: "Pro: {benefit}. Con: {drawback}."
    - label: "{Option C}"
      description: "Pro: {benefit}. Con: {drawback}."
```

### When to trigger

- After Socratic discovery surfaces a decision with 2+ viable approaches
- Before validation checkpoints (trade-offs feed into what gets validated)
- Whenever the user says "not sure which" or "what do you recommend"

### Common Trade-offs by Domain

| Domain | Typical Decision | Options |
|--------|-----------------|---------|
| Auth | Session storage | JWT vs server-side sessions vs hybrid |
| API | Protocol | REST vs GraphQL vs gRPC |
| Data | Processing | Batch vs streaming vs hybrid |
| UI | Rendering | SSR vs CSR vs SSG vs ISR |
| Infra | Hosting | Managed vs self-hosted vs serverless |
| State | Management | Local vs global store vs server state |
| Storage | Database | SQL vs document vs graph vs key-value |
| Caching | Strategy | Client-side vs CDN vs server-side vs multi-layer |

### Recording

After the user selects an option, record the outcome in the transcript:
```
Trade-off {N}: {decision} -> Chose {label}. Rejected: {other labels}.
```

---

## 3. Validation Checkpoint Templates

Run 4 checkpoints after discovery and trade-off rounds. Each checkpoint summarizes what was captured for one area and asks the user to confirm, revise, or add.

### Checkpoint 1: Scope

```
AskUserQuestion:
  header: "Validate: Scope"
  question: "{summary of project scope, boundaries, and out-of-scope items}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for scope."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 2: Entities

```
AskUserQuestion:
  header: "Validate: Entities"
  question: "{list of entities, their attributes, and relationships}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for entities."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 3: Workflows

```
AskUserQuestion:
  header: "Validate: Workflows"
  question: "{user flows and interaction sequences}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for workflows."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 4: Non-Functional Requirements

```
AskUserQuestion:
  header: "Validate: NFRs"
  question: "{performance, security, scalability, and reliability requirements}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for NFRs."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Revision loop

If the user selects "Revise" or "Add", ask a free-form follow-up, incorporate the changes, and re-present the same checkpoint. Continue until "Confirmed".

### Output: validated-design.md

```markdown
# Validated Design: {domain}

## Scope (Confirmed/Revised at checkpoint 1)
{scope description}

## Entities (Confirmed/Revised at checkpoint 2)
{entity list with relationships}

## Workflows (Confirmed/Revised at checkpoint 3)
{user flow descriptions}

## Non-Functional Requirements (Confirmed/Revised at checkpoint 4)
{performance, security, scalability requirements}
```

---

## 4. YAGNI Gate Template

After validation, present all discovered features and let the user select which to build NOW. Unselected features are deferred, not discarded.

### Format

```
AskUserQuestion:
  header: "YAGNI Gate"
  question: "Select the features to build NOW. Unselected features will be deferred to a future iteration."
  multiSelect: true
  options:
    - label: "{Feature 1}"
      description: "{one-line summary of what it does}"
    - label: "{Feature 2}"
      description: "{one-line summary of what it does}"
    - label: "{Feature 3}"
      description: "{one-line summary of what it does}"
```

### Deferred Feature Log (deferred.md)

```markdown
# Deferred Features: {domain}

| Feature | Reason | Revisit When |
|---------|--------|--------------|
| {feature} | Deferred at YAGNI gate | Next iteration |
```

### Rules
- Present features in priority order (core first, nice-to-have last)
- Mark dependencies: if Feature B depends on Feature A, note it in the description
- Minimum 1 feature must be selected (empty selection triggers re-prompt)

---

## 5. Updated Transcript Template

Record all brainstorm phases in a single transcript for downstream consumption by `/zerg:plan`.

```markdown
### Socratic Discovery (--socratic mode)
- **Q{N}** [{domain} tree / LLM follow-up]: {question}
  **A**: {answer} | New entities: {count}

### Trade-off Outcomes
| Decision | Chosen | Alternatives Considered |
|----------|--------|------------------------|
| {decision} | {chosen option} | {other options} |

### Validation Results
| Checkpoint | Status | Notes |
|------------|--------|-------|
| Scope | Confirmed/Revised | {notes} |
| Entities | Confirmed/Revised | {notes} |
| Workflows | Confirmed/Revised | {notes} |
| NFRs | Confirmed/Revised | {notes} |

### YAGNI Gate
- **Kept**: {comma-separated list of features selected for this iteration}
- **Deferred**: {comma-separated list of features moved to deferred.md}
```
