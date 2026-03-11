"""
pytest configuration and shared fixtures for AIDEN Python tool tests.
"""

import json
import pytest
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).parent.parent
POLICIES_DIR = ROOT_DIR / "policies"
PROPOSALS_DIR = ROOT_DIR / "proposals"
SAMPLE_PROPOSAL_PATH = PROPOSALS_DIR / "2026-03-09_ai-code-review-assistant" / "proposal.yaml"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def sample_proposal_yaml() -> str:
    """Return the raw YAML text of the sample AI Code Review Assistant proposal."""
    return SAMPLE_PROPOSAL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sample_proposal(sample_proposal_yaml) -> dict:
    """Return the parsed sample proposal as a dict."""
    import yaml
    return yaml.safe_load(sample_proposal_yaml)


@pytest.fixture(scope="session")
def tiers_config() -> dict:
    """Return the parsed tiers.yaml config."""
    import yaml
    return yaml.safe_load((POLICIES_DIR / "tiers.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def all_policy_files() -> list[Path]:
    """Return all policy YAML files (excluding tiers.yaml and schema files)."""
    result = []
    for p in POLICIES_DIR.rglob("*.yaml"):
        if p.name in ("tiers.yaml", "bridge-manifest.yaml"):
            continue
        if "schema" in p.parts:
            continue
        result.append(p)
    return sorted(result)


@pytest.fixture
def internal_tool_tier(tiers_config) -> dict:
    """Return the internal-tool tier configuration."""
    return tiers_config["tiers"]["internal-tool"]


@pytest.fixture
def production_tier(tiers_config) -> dict:
    """Return the production tier configuration."""
    return tiers_config["tiers"]["production"]


@pytest.fixture
def sample_review_data() -> dict:
    """Minimal review-data.json structure for PDF generation tests."""
    return {
        "proposalId": "2026-03-09_ai-code-review-assistant",
        "proposalName": "AI Code Review Assistant",
        "proposal": {
            "name": "AI Code Review Assistant",
            "team": "Platform Engineering",
            "submitted_by": "proposal-author",
            "submitted_at": "2026-03-09T10:00:00Z",
        },
        "tier": "internal-tool",
        "overallREff": 0.69,
        "overallFormality": "F1",
        "reviewedAt": "2026-03-10T00:00:00Z",
        "engineVersion": "1.0.0",
        "sections": [
            {
                "domain": "data-privacy",
                "formality": "F2",
                "ruleCoverage": 1.0,
                "rEff": 0.827,
                "tallies": {"passed": 6, "failed": 1, "abstained": 0, "degraded": 0, "waived": 0},
                "criticalFails": 0,
                "highFails": 1,
                "guardDecisions": [],
            },
            {
                "domain": "security",
                "formality": "F2",
                "ruleCoverage": 0.889,
                "rEff": 0.69,
                "tallies": {"passed": 6, "failed": 2, "abstained": 0, "degraded": 0, "waived": 1},
                "criticalFails": 0,
                "highFails": 2,
                "guardDecisions": [],
            },
        ],
    }


@pytest.fixture
def sample_gate_decision() -> dict:
    """Minimal gate-decision.json structure for tests."""
    return {
        "outcome": "CONDITIONAL",
        "rationale": [
            "R_eff 0.69 is below approve threshold 0.75",
            "Security: 2 high-severity failures (SEC-RBAC-002, SEC-VUL-002)",
        ],
        "requiresHuman": True,
        "autonomyBudget": {"consumed": 0, "remaining": 0, "ceiling": 0},
        "escalationRequired": False,
        "overrideRequires": ["engineering-director", "compliance-officer"],
        "tier": "internal-tool",
        "waiversApplied": ["ARCH-MULTI-REGION", "ARCH-DR-STRATEGY", "SEC-PEN-TEST"],
        "timestamp": "2026-03-10T00:00:00Z",
    }
