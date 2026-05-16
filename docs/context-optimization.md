# Intelligent Context Optimization

How Context-Life classifies, evaluates, and decides what to do with your prompts — so you don't waste tokens or risk hallucinations.

---

## What Problem Does It Solve?

When you send a prompt to an AI, the model has to work with whatever context it receives. The problem is:

- **Under-optimized prompts** waste tokens and slow down responses
- **Ambiguous prompts** without enough context cause AI hallucinations
- **Over-optimization** (adding context that wasn't needed) inflates input size without benefit

Context-Life's intelligent optimization layer evaluates every prompt and decides: **does this need help, and what kind?**

---

## The Three States

| State | What It Means | Action |
|-------|---------------|--------|
| **LIGHT** | Your prompt is clear and has enough context | Continue normally. No optimizations called. |
| **REQUIRED** | Your prompt has intent but is disorganized or ambiguous | Get clarification or context before proceeding |
| **CRITICAL** | Your prompt has contradictions or high hallucination risk | **HALT** — do not generate code until the conflict is resolved |

### State: LIGHT

**When**: Your prompt is clear, specific, and has enough context.

**How to identify**:
- Contains explicit file paths (`src/auth/service.ts`)
- Has action verbs ("Refactor", "Add", "Investigate")
- Mentions the tech stack ("using Python + FastAPI")
- Has clear constraints ("must use existing architecture")

**Confidence threshold**: ≥ 0.80

**What happens**:
```json
{
  "d4": {
    "state": "LIGHT",
    "confidence": 0.86,
    "next_action": "continue"
  }
}
```

No extra context is injected. The orchestration layer proceeds without calling `optimize_messages` or `cache_context`.

**Output token overhead**: ~17 tokens (~24% over legacy baseline)

---

### State: REQUIRED

**When**: Your prompt is salvageable but needs structure or missing context.

**How to identify**:
- Vague goal ("fix something", "improve code")
- No explicit files mentioned
- Stack not specified
- Missing constraints or requirements

**Confidence threshold**: 0.55 – 0.79

**What happens**:
```json
{
  "d4": {
    "state": "REQUIRED",
    "confidence": 0.74,
    "next_action": "ask_clarification",
    "missing_context": ["specify_stack", "list_affected_files"]
  }
}
```

The orchestration layer is told to ask for clarification or get minimal context via `cache_context` — but NOT to run full `optimize_messages` yet.

**Output token overhead**: ~38 tokens (~54% over legacy baseline)

---

### State: CRITICAL

**When**: There is a contradiction, decision ambiguity, or high hallucination risk.

**Trigger conditions** (any one is enough):

| Trigger | Example |
|---------|---------|
| **README vs package.json mismatch** | README says React, but package.json uses Next.js |
| **Memory policy conflict** | Memory says "don't use Prisma", but the code uses it |
| **Destructive operation** | "Delete all user records" without backup plan |
| **Breaking public API change** | Semver-major change implied without test coverage |
| **Ambiguous architecture** | Two different architecture patterns both possible |
| **Stack mismatch** | User asks for MySQL but project uses PostgreSQL |

**Confidence threshold**: Any confidence — conflict forces CRITICAL regardless of score.

**What happens**:
```json
{
  "d4": {
    "state": "CRITICAL",
    "confidence": 0.41,
    "next_action": "halt",
    "halt": {
      "detected_goal": ["Implement dashboard for business metrics"],
      "conflict": [
        "Source A: README.md indicates 'React for frontend'",
        "Source B: package.json / recent git indicates 'Next.js + API routes'"
      ],
      "risk": "Continuing could generate solution incompatible with real stack.",
      "required_decision": [
        "Use README.md as source of truth",
        "Use package.json and current code as source of truth",
        "Inspect project before deciding"
      ]
    }
  }
}
```

**Output token overhead**: ~87 tokens (~122% over legacy baseline)

**Behavior**: The orchestration layer is told to **HALT** and present the conflict to the user. No code is generated until the user resolves the contradiction.

---

## How Classification Works

```
Your Prompt
     │
     ▼
┌────────────────────────────┐
│  PromptContextClassifier   │
│  ├─ Extract signals        │
│  ├─ Compute confidence     │
│  └─ Determine state        │
└────────────────────────────┘
     │
     ▼
┌────────────────────────────┐
│    ConflictDetector        │ (runs in parallel)
│  ├─ README vs deps         │
│  ├─ Memory vs code         │
│  ├─ Git vs structure       │
│  └─ Prompt vs stack        │
└────────────────────────────┘
     │
     ▼ (if conflict → CRITICAL)
┌────────────────────────────┐
│   ProjectContextResolver    │
│  ├─ Check Engram memory    │
│  ├─ Check sdd-init cache   │
│  └─ Fallback to filesystem │
└────────────────────────────┘
     │
     ▼
┌────────────────────────────┐
│    ContextPackBuilder       │
│  └─ Build compact JSON     │
└────────────────────────────┘
```

---

## Confidence Scoring

The confidence score is **deterministic**: the same prompt always produces the same score.

| Score | State | Formula |
|-------|-------|---------|
| base = 0.50 | — | Start |
| +0.15 per LIGHT signal | LIGHT | `clear_goal`, `explicit_files`, `stack_mentioned`, `constraint_listed` |
| +0.05 per REQUIRED signal | REQUIRED | `vague_goal`, `partial_files`, `implicit_stack`, `loose_constraints` |
| Any CRITICAL trigger | CRITICAL | Forces state regardless of confidence |

Final score: `min(1.0, max(0.0, base))`

| Threshold | Meaning |
|-----------|---------|
| ≥ 0.80 | LIGHT — prompt is good enough |
| 0.55 – 0.79 | REQUIRED — needs restructuring or context |
| < 0.55 | REQUIRED — unless conflict forces CRITICAL |
| Conflict detected | CRITICAL — halt immediately |

---

## What the Orchestration Layer Receives

`intercept_user_request` returns both the **legacy contract** and the **D4 decision** merged:

```json
{
  "intent": "feature_request",
  "keywords": ["dashboard", "metrics"],
  "advice": {
    "recommended_next_tool": "search_context"
  },
  "applied_process": ["normalize_request"],
  "d4": {
    "state": "LIGHT",
    "confidence": 0.86,
    "next_action": "continue"
  }
}
```

For CRITICAL:
```json
{
  "intent": "feature_request",
  "keywords": ["dashboard"],
  "advice": {
    "recommended_next_tool": "halt"
  },
  "applied_process": ["normalize_request", "d4_evaluation"],
  "d4": {
    "state": "CRITICAL",
    "confidence": 0.41,
    "next_action": "halt",
    "halt": {
      "detected_goal": ["..."],
      "conflict": ["..."],
      "risk": "...",
      "required_decision": ["..."]
    }
  }
}
```

---

## Rules by State

| State | Don't call | Do call |
|-------|-----------|---------|
| **LIGHT** | `optimize_messages` · `cache_context` | Continue normally |
| **REQUIRED** | `optimize_messages` | `cache_context` only if context gap affects the answer |
| **CRITICAL** | Any optimization tool | HALT and present conflict to user |

---

## Token Cost Summary

| State | Overhead (tokens) | Overhead (%) |
|-------|-------------------|--------------|
| LIGHT | ~17 | ~24% |
| REQUIRED | ~38 | ~54% |
| CRITICAL | ~87 | ~122% |

Baseline legacy output: ~71 tokens.

**The real savings come from not calling expensive tools** (`optimize_messages`, `cache_context`) when they aren't needed — not from compressing the response.

---

## Integration with Gentle AI / SDD Orchestrator

Context-Life is designed to work as a **pre-processor** for AI orchestrators like Gentle AI:

1. The user's raw prompt goes to `intercept_user_request`
2. D4 classifies it as LIGHT / REQUIRED / CRITICAL
3. The orchestrator receives the merged response and decides what to do:
   - LIGHT → proceed with planning
   - REQUIRED → fetch context or ask user
   - CRITICAL → show HALT and wait for user decision

D4 does NOT replace Gentle AI's `sdd-init`, Engram, or orchestrator. It just tells them what they need to know before they start working.

---

## Context Budget

D4 also tells the orchestrator how much context to budget:

| Budget | Tokens | When |
|--------|--------|------|
| `tiny` | ~200 | CRITICAL (HALT) or very short prompt |
| `small` | ~500 | LIGHT with stale/missing context |
| `medium` | ~1000 | REQUIRED or LIGHT with partial context |
| `full` | no limit | LIGHT with fresh complete context |

This helps the orchestrator know how much context to inject from Engram or project files.

---

## Signal Reference

### LIGHT Signals
- `clear_goal` — prompt has specific, non-vague intent
- `explicit_files` — file paths are explicitly mentioned
- `stack_mentioned` — tech stack is specified
- `constraint_listed` — constraints or requirements are explicit

### REQUIRED Signals
- `vague_goal` — uses vague language ("fix it", "improve stuff")
- `partial_files` — no explicit files mentioned
- `implicit_stack` — stack is implied but not stated
- `loose_constraints` — constraints are missing or vague

### CRITICAL Triggers
- `readme_stack_mismatch` — README and package.json disagree on framework
- `memory_policy_conflict` — memory policy forbids something the code uses
- `destructive_operation` — data deletion, auth migration, security changes
- `breaking_public_api` — semver-major change implied
- `ambiguous_architecture` — multiple valid architecture paths exist

---

## Open Items

- **Scoop manifest hash**: The Windows Scoop installation manifest uses placeholder hashes. Real SHA256 hashes will be added at release time.
- **Preflight prompt**: The `preflight_request` prompt template operates independently and is not affected by D4 decisions.