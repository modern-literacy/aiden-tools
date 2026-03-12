# aiden-tools

Python tooling for the AIDEN system.

These tools operate on engine outputs and pinned policy artifacts so reviewers can batch-run proposals, assemble review packs, and seed demo-safe precedent data.

## Tools
- `eval_harness.py` — batch evaluation harness
- `review_pack_generator.py` — assembles review packs from engine output and publication views
- `seed_precedents.py` — seeds synthetic precedent history for demo and evaluation scenarios

## Inputs it expects
- deterministic review data
- gate decision output
- bounded assistive traces when available
- publication views (TEVB implementation, FPF-aligned)

## Setup
```bash
pip install -r requirements.txt
```

## Testing
`test_harness.py` and `pytest` validate the canonical sample inputs and outputs.
