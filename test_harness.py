"""
AIDEN Python Harness — Smoke Tests

Validates:
  - Null handling: field present with null is NOT treated as missing
  - Sample proposal produces R_eff = 0.69 and CONDITIONAL gate
  - Harness matches TS engine output
"""

import pytest
from pathlib import Path
from eval_harness import (
    evaluate_proposal,
    compute_gate,
    resolve_field_path,
    load_yaml,
    discover_policy_files,
)

ROOT_DIR = Path(__file__).parent.parent
POLICIES_DIR = ROOT_DIR / "policies"
PROPOSALS_DIR = ROOT_DIR / "proposals"
SAMPLE_PROPOSAL_PATH = PROPOSALS_DIR / "2026-03-09_ai-code-review-assistant" / "proposal.yaml"


@pytest.fixture(scope="module")
def sample_proposal() -> dict:
    return load_yaml(SAMPLE_PROPOSAL_PATH)


@pytest.fixture(scope="module")
def tiers_config() -> dict:
    return load_yaml(POLICIES_DIR / "tiers.yaml")


@pytest.fixture(scope="module")
def policy_files() -> list[Path]:
    return discover_policy_files(POLICIES_DIR)


@pytest.fixture(scope="module")
def internal_tool_tier(tiers_config) -> dict:
    return tiers_config["tiers"]["internal-tool"]


# ── Null handling tests ──────────────────────────────────────────────────────


class TestNullHandling:
    """Verify that field-present-with-null is treated as a real value, not missing."""

    def test_resolve_field_path_present_null(self):
        """Field present with value None should return (True, None)."""
        obj = {"security": {"break_glass_procedure": None}}
        exists, value = resolve_field_path(obj, "security.break_glass_procedure")
        assert exists is True
        assert value is None

    def test_resolve_field_path_missing(self):
        """Field entirely absent should return (False, None)."""
        obj = {"security": {}}
        exists, value = resolve_field_path(obj, "security.break_glass_procedure")
        assert exists is False
        assert value is None

    def test_null_value_runs_check_not_on_missing(self, sample_proposal, policy_files, internal_tool_tier):
        """When a field is null, the check should execute (and likely fail),
        NOT silently apply on_missing behavior."""
        result = evaluate_proposal(sample_proposal, policy_files, internal_tool_tier, "internal-tool")
        security = result["sections"].get("security", {})
        # Null fields like break_glass_procedure should produce 'fail' (check runs against None),
        # NOT 'abstain' (which would happen if on_missing were applied)
        guard_decisions = security.get("guardDecisions", [])
        break_glass = [d for d in guard_decisions if d["ruleId"] == "SEC-RBAC-002"]
        if break_glass:
            assert break_glass[0]["outcome"] == "fail", (
                "SEC-RBAC-002: null break_glass_procedure should FAIL the check, not abstain"
            )


# ── Sample proposal smoke test ───────────────────────────────────────────────


class TestSampleProposal:
    """Verify the canonical sample proposal produces expected results matching TS engine."""

    def test_overall_r_eff(self, sample_proposal, policy_files, internal_tool_tier):
        result = evaluate_proposal(sample_proposal, policy_files, internal_tool_tier, "internal-tool")
        assert result["overallREff"] == 0.69, f"Expected R_eff 0.69, got {result['overallREff']}"

    def test_gate_conditional(self, sample_proposal, policy_files, internal_tool_tier, tiers_config):
        tier_cfg = tiers_config["tiers"]["internal-tool"]
        result = evaluate_proposal(sample_proposal, policy_files, internal_tool_tier, "internal-tool")
        gate = compute_gate(result, tier_cfg)
        assert gate == "CONDITIONAL", f"Expected CONDITIONAL, got {gate}"

    def test_security_is_weakest(self, sample_proposal, policy_files, internal_tool_tier):
        result = evaluate_proposal(sample_proposal, policy_files, internal_tool_tier, "internal-tool")
        sections = result["sections"]
        valid = {k: v for k, v in sections.items() if v.get("rEff") is not None}
        weakest_domain = min(valid, key=lambda k: valid[k]["rEff"])
        assert weakest_domain == "security", f"Expected weakest=security, got {weakest_domain}"

    def test_security_r_eff(self, sample_proposal, policy_files, internal_tool_tier):
        result = evaluate_proposal(sample_proposal, policy_files, internal_tool_tier, "internal-tool")
        security = result["sections"]["security"]
        assert security["rEff"] == 0.69, f"Expected security R_eff 0.69, got {security['rEff']}"
