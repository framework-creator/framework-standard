# Contributed Frameworks

Frameworks contributed by the community using the framework builder methodology.

## Tiers

Every contributed framework belongs to one of two tiers. The tier is declared by which subdirectory the framework lives in.

### `theoretical/`

Well-structured frameworks that follow the `.framework.json` v1.0 spec and include explicit force multiplier intelligence, but have not yet been tested in real-world conditions with documented evidence.

Theoretical frameworks are valuable starting points. Use them. Stress-test them. Measure what happens. Then submit a PR promoting them to validated.

### `validated/`

Frameworks with documented real-world usage, specific metrics, and reproducible results.

**The benchmark:** The PIVOT framework, used daily by a sales operations manager for six months, produced a 60% efficiency improvement in client call preparation. That is a validated framework. It has a documented user, a specific domain, a specific metric, and a specific time period.

## The validation pathway

Theoretical → Validated is an open process. If you use a contributed theoretical framework and get measurable results, open a pull request with your evidence. Include:

- Your domain and role (anonymized if you prefer).
- How many times you used the framework.
- What you measured before and what you measured after.
- What the results were, specifically.

The community validates frameworks by using them. That is the real quality gate.

## First contribution: Grok's meta-cognition series

Six frameworks built by Grok (xAI) using the framework builder skill file, then updated after reading whatisaframework.com to include explicit force multiplier sections.

- `FRAMEWORK-SOCRATIC-001.framework.json` — Socratic Stress Test. Pressure-test any belief by steelmanning the opposition and surfacing hidden assumptions.
- `FRAMEWORK-ARCHAEOLOGY-001.framework.json` — Prompt Archaeology. Excavate, diagnose, and upgrade any existing prompt or system.
- `FRAMEWORK-FP-COMPRESS-001.framework.json` — First Principles Compression. Break any complex topic down to atomic truths and rebuild it cleanly.
- `FRAMEWORK-DECISION-LATTICE-001.framework.json` — Decision Lattice. Map decisions with multiple interdependent variables and outcomes.
- `FRAMEWORK-FEEDBACK-OPT-001.framework.json` — Feedback Loop Optimizer. Design, monitor, and accelerate any personal or project feedback loop.
- `FRAMEWORK-CONTRADICTION-001.framework.json` — Contradiction Resolver. Meta-framework for when two frameworks give conflicting advice.

**What Grok's self-correction proved:** Following the spec produces format compliance. Reading whatisaframework.com produces force multiplier intelligence. Both are required for a framework that genuinely compounds. The Quality Standards section in [`CONTRIBUTING.md`](../../CONTRIBUTING.md) documents exactly what force multiplier intelligence means in practice.

See [`theoretical/meta-cognition/`](theoretical/meta-cognition/) for all six files.

## Contributing your own

1. Build a framework using the spec in [`SPECIFICATION.md`](../../SPECIFICATION.md).
2. Read [whatisaframework.com](https://whatisaframework.com) for the force multiplier lens.
3. Validate it passes strict mode: `python3 tools/ingest.py --source your-folder --db check.db --strict`.
4. Drop it in `theoretical/<your-series-name>/` with a short pull request explaining what problem it solves.
