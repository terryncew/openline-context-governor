# OpenLine Context Governor

**v0.1 experimental**

Make agents faster by teaching them when small context is enough — and when it is dangerous.

Big context windows give models more room.

OpenLine Context Governor asks a smaller question:

> What context can safely shrink?

It sits between the user and an answer agent. It builds a small digest, runs a witness check, writes an OpenLine-style receipt, and decides whether the agent can continue with the digest or must pull the fuller record.

This repo is not claiming to solve context compression. It is a harness for testing context handoffs.

## Why this exists

A summary can preserve the words and lose the meaning.

The dangerous case is a digest that drops a constraint, flips a negation, loses the user preference, or drags stale context into a new task.

OpenLine Context Governor treats compression as a handoff boundary.

If the digest preserves the task and constraints, the result is green.

If the digest looks thin, ambiguous, high-stakes, missing a file, or likely to have lost a negation, the result is amber or red and the governor requests fuller context.

## Core idea

```text
latest message + context
  -> adaptive digest
  -> witness check
  -> receipt
  -> green: pass digest
  -> amber/red: pull fuller context
```

A digest is not memory.

It is a pointer with proof.

## Files

```text
context_governor.py
adaptive_digest_benchmark.py
receipts.jsonl
examples/messy_contexts.jsonl
.github/workflows/ci.yml
```

## Run

```bash
python adaptive_digest_benchmark.py
```

The benchmark is intentionally small and adversarial. It includes constraints, preferences, stale context risk, uploaded-file risk, tool-required risk, and negation risk.

## Receipt fields

Each run emits a JSONL receipt with:

```text
claim
action
evidence_hash
digest_hash
full_context_hash
timestamp
witness
result
preserved_task
preserved_claim
preserved_constraint
preserved_preference
risk_flag
pullback_reason
tokens_input_est
tokens_digest_est
next_use_note
```

## Pullback reasons

```text
constraint_missing
negation_lost
preference_missing
claim_ambiguous
stale_context_risk
high_stakes_context
uploaded_file_needed
tool_required
```

## Known v0.1 failure

The current digest and witness logic are crude heuristics.

The failure class to watch is negation loss.

Example:

```text
Do this without using conda or pip.
```

A bad digest can quietly become:

```text
Do this using conda or pip.
```

That is exactly why this repo exists. The witness layer should catch that class of failure and trigger pullback. Treat this repo as a test harness, not a finished compression system.

## How it fits OpenLine

OpenLine Memory decides what can come back.

Context Governor decides what can safely shrink.

OpenLine receipts prove what crossed the boundary.

The current public OpenLine stack centers portable cryptographic AI agent receipts, OpenTelemetry governance, compliance, and cross-vendor verification. This repo is the context-handoff version of that same idea: compress only when the boundary conditions survive.


## License

MIT
