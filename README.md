# aiden-tools

Python tooling for the AIDEN (Architecture Intake & Decision Engine) system. Provides batch evaluation, review pack generation, and precedent seeding utilities.

## Tools

- **`eval_harness.py`** — CLI for batch-evaluating AI system proposals against AIDEN policy files. Produces R_eff scores, gate decisions, and rich comparison tables.
- **`review_pack_generator.py`** — Generates PDF review packs from AIDEN engine output artifacts (review data, gate decisions, bias audits, TEVB views).
- **`seed_precedents.py`** — Generates synthetic ExceptionRecord entries and reviewer decision history for populating the exception-intel engine's precedent database.

## Testing

- **`test_harness.py`** — Smoke tests validating null handling, R_eff computation, and gate decisions against the canonical sample proposal.
- **`conftest.py`** — Shared pytest fixtures for test configuration.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Batch Evaluation

```bash
python eval_harness.py \
    --proposals ../proposals \
    --policies ../policies \
    --tiers ../policies/tiers.yaml \
    --output results.json
```

### Review Pack Generation

```bash
python review_pack_generator.py \
    --review-data ./out/review-data.json \
    --gate-decision ./out/gate-decision.json \
    --bias-audit ./out/bias-audit.json \
    --tevb-dir ./out/tevb/ \
    --output ./out/review-pack.pdf
```

### Precedent Seeding

```bash
python seed_precedents.py --count 50 --seed 42 --output precedents.json
```

## Ownership

Owned by the **Data & ML Engineering** team. See `CODEOWNERS` for review assignments.
