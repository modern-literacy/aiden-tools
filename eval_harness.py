#!/usr/bin/env python3
"""
AIDEN Evaluation Harness
========================
CLI tool for batch-evaluating AI system proposals against AIDEN policy files.

Usage:
    python eval_harness.py \\
        --proposals ../proposals \\
        --policies ../policies \\
        --tiers ../policies/tiers.yaml \\
        --output results.json

Outputs:
    - Rich comparison table to stdout
    - JSON results file (if --output specified)
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table
from rich import box
from tabulate import tabulate

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    """Load a YAML file and return as dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_field_path(obj: Any, path: str) -> tuple[bool, Any]:
    """
    Resolve a dot-notation field path against a nested dict.
    Returns (field_exists: bool, value: Any).
    """
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def evaluate_check(expression: str, value: Any) -> bool:
    """
    Evaluate a simple boolean check expression with 'value' as the variable.
    Supports: !== null, === true/false, >= N, Array.isArray, .includes(), .toLowerCase()
    Uses a whitelist approach — NOT eval().
    """
    expr = expression.strip()

    # value !== null && value !== undefined && value !== ''
    if "value !== null" in expr and "value !== undefined" in expr and "value !== ''" in expr:
        return value is not None and value != ""

    # value === true
    if expr == "value === true":
        return value is True

    # value === false
    if expr == "value === false":
        return value is False

    # value === true || value === false
    if "value === true || value === false" in expr:
        return value is True or value is False

    # value !== null && value !== undefined
    if "value !== null" in expr and "value !== undefined" in expr:
        return value is not None

    # value !== null
    if expr == "value !== null":
        return value is not None

    # Array.isArray(value) && value.length > 0
    if "Array.isArray" in expr and "length > 0" in expr:
        return isinstance(value, list) and len(value) > 0

    # value >= N
    if expr.startswith("value >= "):
        try:
            threshold = float(expr.split("value >= ")[1])
            return isinstance(value, (int, float)) and value >= threshold
        except (ValueError, IndexError):
            return False

    # value.toLowerCase().includes(...)
    if ".toLowerCase().includes(" in expr and "value !== null" not in expr:
        try:
            substr = expr.split(".toLowerCase().includes('")[1].rstrip("')")
            return isinstance(value, str) and substr.lower() in value.lower()
        except IndexError:
            return False

    # Compound OR for .includes checks (SEC-NET-001 pattern)
    if "||" in expr and ".includes(" in expr:
        clauses = expr.split("||")
        for clause in clauses:
            clause = clause.strip()
            if "value !== null" in clause and "value !== undefined" in clause:
                if value is None:
                    return False
                continue
            if ".includes(" in clause:
                try:
                    substr = clause.split(".includes('")[1].rstrip("')").lower()
                    if isinstance(value, str) and substr in value.lower():
                        return True
                except IndexError:
                    pass
        return False

    # Default: treat non-null/non-empty as pass
    console.print(f"[yellow]Warning: unrecognized check expression '{expr}', defaulting to value is not None[/yellow]")
    return value is not None and value != ""


def get_tier_severity(rule: dict, tier_adjustments: dict) -> str:
    """Apply tier-level severity adjustments to a rule."""
    rule_id = rule.get("id", "")
    return tier_adjustments.get(rule_id, rule.get("severity", "medium"))


# ── Core Evaluator ────────────────────────────────────────────────────────────

SEVERITY_PENALTIES = {"critical": 0.05, "high": 0.03, "medium": 0.01, "low": 0.00}
DEGRADATION_WEIGHT = 0.02

DOMAIN_FORMALITY = {
    "data-privacy": "F2",
    "architecture": "F2",
    "security": "F2",
    "operations": "F1",
    "governance": "F1",
}

TIER_ORDER = ["internal-tool", "production", "critical-infrastructure"]


def evaluate_proposal(proposal: dict, policy_files: list[Path], tier_config: dict,
                       tier_name: str) -> dict:
    """
    Evaluate a single proposal against all policy files for the given tier.
    Returns a structured result dict.
    """
    waived_rules: set[str] = set(tier_config.get("waived_rules", []))
    severity_adjustments: dict[str, str] = tier_config.get("severity_adjustments", {})
    proposal_tier_idx = TIER_ORDER.index(tier_name) if tier_name in TIER_ORDER else 0

    sections: dict[str, dict] = {}

    for policy_path in policy_files:
        policy = load_yaml(policy_path)
        domain = policy.get("domain", "unknown")
        formality = policy.get("formality", "F1")
        total_rules = len(policy.get("rules", []))
        min_threshold = policy.get("min_rules_threshold", 1)

        tallies = {"passed": 0, "failed": 0, "abstained": 0, "degraded": 0, "waived": 0}
        critical_fails = 0
        high_fails = 0
        active_rules = 0
        guard_decisions = []

        for rule in policy.get("rules", []):
            rule_id = rule.get("id", "")

            # Check tier_minimum — skip rules above current tier
            tier_min = rule.get("tier_minimum")
            if tier_min and tier_min in TIER_ORDER:
                tier_min_idx = TIER_ORDER.index(tier_min)
                if tier_min_idx > proposal_tier_idx:
                    # Not active at this tier — excluded from active count
                    continue

            active_rules += 1

            # Check if waived for this tier
            if rule_id in waived_rules:
                tallies["waived"] += 1
                guard_decisions.append({
                    "ruleId": rule_id,
                    "outcome": "waived",
                    "reason": f"Waived for {tier_name} tier",
                })
                continue

            predicate = rule.get("predicate", {})
            field_path = predicate.get("field_path", "")
            check_expr = predicate.get("check", "value !== null")
            on_missing = predicate.get("on_missing", "abstain")

            # Apply severity adjustment
            severity = get_tier_severity(rule, severity_adjustments)

            # Resolve field path
            field_exists, value = resolve_field_path(proposal, field_path)

            if not field_exists:
                # Field path is entirely absent from proposal => on_missing
                outcome = on_missing  # "abstain" or "degrade"
            else:
                passes = evaluate_check(check_expr, value)
                outcome = "pass" if passes else "fail"

            tallies_key = {"pass": "passed", "fail": "failed",
                           "abstain": "abstained", "degrade": "degraded"}.get(outcome, "abstained")
            tallies[tallies_key] += 1

            if outcome == "fail":
                if severity == "critical":
                    critical_fails += 1
                elif severity == "high":
                    high_fails += 1

            guard_decisions.append({
                "ruleId": rule_id,
                "outcome": outcome,
                "fieldPath": field_path,
                "actualValue": value,
                "severity": severity,
                "reason": f"Field '{field_path}' evaluated: outcome={outcome}",
            })

        # Compute R_eff
        evaluable = tallies["passed"] + tallies["failed"] + tallies["degraded"]
        if evaluable < min_threshold:
            r_eff = None
        else:
            r_raw = tallies["passed"] / evaluable if evaluable > 0 else 0.0
            penalty = (critical_fails * SEVERITY_PENALTIES["critical"] +
                       high_fails * SEVERITY_PENALTIES["high"])
            degradation = tallies["degraded"] * DEGRADATION_WEIGHT
            r_eff = max(0.0, r_raw - penalty - degradation)

        # RuleCoverage = non-waived active rules / total rules in policy
        # active_rules already accounts for tier_minimum skips; waived_count reduces from active
        non_waived_active = active_rules - tallies["waived"]
        rule_coverage = non_waived_active / total_rules if total_rules > 0 else 0.0

        sections[domain] = {
            "domain": domain,
            "formality": formality,
            "ruleCoverage": round(rule_coverage, 3),
            "rEff": round(r_eff, 3) if r_eff is not None else None,
            "tallies": tallies,
            "criticalFails": critical_fails,
            "highFails": high_fails,
            "guardDecisions": guard_decisions,
            "activeRules": active_rules,
            "totalRules": total_rules,
        }

    # Overall scores
    valid_r_effs = [s["rEff"] for s in sections.values() if s["rEff"] is not None]
    overall_r_eff = min(valid_r_effs) if valid_r_effs else None

    formality_map = {"F0": 0, "F1": 1, "F2": 2, "F3": 3}
    formalities = [formality_map.get(s["formality"], 0) for s in sections.values()]
    overall_formality = f"F{min(formalities)}" if formalities else "F0"

    return {
        "proposalId": proposal.get("id", "unknown"),
        "proposalName": proposal.get("name", "Unknown"),
        "tier": tier_name,
        "sections": sections,
        "overallREff": round(overall_r_eff, 3) if overall_r_eff is not None else None,
        "overallFormality": overall_formality,
        "evaluatedAt": datetime.utcnow().isoformat() + "Z",
    }


def compute_gate(result: dict, tier_config: dict) -> str:
    """Determine gate outcome based on overall R_eff and thresholds."""
    r_eff = result.get("overallREff")
    if r_eff is None:
        return "BLOCK"

    approve_threshold = tier_config.get("approve_threshold", 0.75)
    block_threshold = tier_config.get("block_threshold", 0.40)

    if r_eff >= approve_threshold:
        return "APPROVE"
    elif r_eff >= block_threshold:
        return "CONDITIONAL"
    else:
        return "BLOCK"


# ── CLI ───────────────────────────────────────────────────────────────────────

def discover_proposals(proposals_dir: Path) -> list[Path]:
    """Find all proposal.yaml files recursively."""
    return sorted(proposals_dir.rglob("proposal.yaml"))


def discover_policy_files(policies_dir: Path) -> list[Path]:
    """Find all policy YAML files (excluding tiers.yaml and schema files)."""
    result = []
    for p in policies_dir.rglob("*.yaml"):
        if p.name in ("tiers.yaml", "bridge-manifest.yaml"):
            continue
        if "schema" in p.parts:
            continue
        result.append(p)
    return sorted(result)


def render_table(results: list[dict], tiers: dict) -> None:
    """Render a Rich comparison table to stdout."""
    table = Table(
        title="AIDEN Batch Evaluation Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Proposal", style="bold", max_width=35)
    table.add_column("Tier", max_width=18)
    table.add_column("Gate", max_width=12)
    table.add_column("R_eff", justify="right", max_width=8)
    table.add_column("Form.", max_width=6)
    table.add_column("Data&Priv", justify="right", max_width=10)
    table.add_column("Arch", justify="right", max_width=8)
    table.add_column("Security", justify="right", max_width=9)
    table.add_column("Ops", justify="right", max_width=8)
    table.add_column("Gov", justify="right", max_width=8)

    gate_styles = {"APPROVE": "green", "CONDITIONAL": "yellow", "BLOCK": "red"}

    for r in results:
        tier_name = r["tier"]
        tier_cfg = tiers.get("tiers", {}).get(tier_name, {})
        gate = compute_gate(r, tier_cfg)
        sections = r.get("sections", {})

        def fmt_section(domain_key: str) -> str:
            s = sections.get(domain_key, {})
            reff = s.get("rEff")
            return f"{reff:.3f}" if reff is not None else "—"

        gate_style = gate_styles.get(gate, "white")
        r_eff_val = r.get("overallREff")
        r_eff_str = f"{r_eff_val:.3f}" if r_eff_val is not None else "—"

        table.add_row(
            r.get("proposalName", r.get("proposalId", "?")),
            tier_name,
            f"[{gate_style}]{gate}[/{gate_style}]",
            r_eff_str,
            r.get("overallFormality", "?"),
            fmt_section("data-privacy"),
            fmt_section("architecture"),
            fmt_section("security"),
            fmt_section("operations"),
            fmt_section("governance"),
        )

    console.print(table)

    # Per-proposal detail
    for r in results:
        console.print(f"\n[bold]{r.get('proposalName')}[/bold] ({r.get('proposalId')})")
        for domain, section in r.get("sections", {}).items():
            t = section["tallies"]
            console.print(
                f"  {domain:20s} | RC={section['ruleCoverage']:.3f} | "
                f"R_eff={section['rEff'] if section['rEff'] is not None else 'null':>6} | "
                f"P={t['passed']} F={t['failed']} A={t['abstained']} D={t['degraded']} W={t['waived']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AIDEN batch evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--proposals", required=True,
                        help="Path to proposals directory")
    parser.add_argument("--policies", required=True,
                        help="Path to policies directory")
    parser.add_argument("--tiers", default=None,
                        help="Path to tiers.yaml (default: <policies>/tiers.yaml)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path")
    parser.add_argument("--tier-override", default=None,
                        help="Override tier for all proposals (for testing)")
    args = parser.parse_args()

    proposals_dir = Path(args.proposals)
    policies_dir = Path(args.policies)
    tiers_path = Path(args.tiers) if args.tiers else policies_dir / "tiers.yaml"

    if not proposals_dir.exists():
        console.print(f"[red]Proposals directory not found: {proposals_dir}[/red]")
        sys.exit(1)
    if not tiers_path.exists():
        console.print(f"[red]Tiers file not found: {tiers_path}[/red]")
        sys.exit(1)

    tiers = load_yaml(tiers_path)
    policy_files = discover_policy_files(policies_dir)
    proposal_paths = discover_proposals(proposals_dir)

    if not proposal_paths:
        console.print("[yellow]No proposal.yaml files found.[/yellow]")
        sys.exit(0)

    console.print(f"[cyan]Found {len(proposal_paths)} proposal(s) and {len(policy_files)} policy file(s)[/cyan]")

    results = []
    for proposal_path in proposal_paths:
        proposal = load_yaml(proposal_path)
        tier_name = args.tier_override or proposal.get("scope", {}).get("tier", "internal-tool")
        tier_cfg = tiers.get("tiers", {}).get(tier_name, {})

        if not tier_cfg:
            console.print(f"[yellow]Unknown tier '{tier_name}' for {proposal_path.name}, skipping[/yellow]")
            continue

        result = evaluate_proposal(proposal, policy_files, tier_cfg, tier_name)
        result["gateSummary"] = compute_gate(result, tier_cfg)
        results.append(result)
        console.print(f"  ✓ {proposal.get('name', proposal_path.name)}: "
                      f"R_eff={result['overallREff']} → {result['gateSummary']}")

    render_table(results, tiers)

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        console.print(f"\n[green]Results written to {output_path}[/green]")


if __name__ == "__main__":
    main()
