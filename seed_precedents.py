#!/usr/bin/env python3
"""
AIDEN Precedent Seeder
=======================
Generates synthetic ExceptionRecord entries and reviewer decision history
for populating the exception-intel engine's precedent database.

Uses Faker for realistic names and dates. Outputs JSON to stdout or file.

Usage:
    python seed_precedents.py --count 50 --output precedents.json
    python seed_precedents.py --count 100 --seed 42 --output precedents.json
"""

import json
import random
import argparse
from datetime import datetime, timedelta
from typing import Any

from faker import Faker

fake = Faker()

# ── Constants ─────────────────────────────────────────────────────────────────

TIERS = ["internal-tool", "production", "critical-infrastructure"]
DOMAINS = ["data-privacy", "architecture", "security", "operations", "governance"]
SEVERITIES = ["critical", "high", "medium", "low"]
RULE_IDS = [
    "HIPAA-PHI-001", "HIPAA-PHI-002", "HIPAA-PHI-003", "HIPAA-PHI-004",
    "HIPAA-PHI-005", "HIPAA-PHI-006", "HIPAA-PHI-007",
    "ARCH-HOST-001", "ARCH-INT-001", "ARCH-MODEL-001", "ARCH-AVAIL-001",
    "ARCH-SCALE-001", "ARCH-DEP-001", "ARCH-MULTI-REGION", "ARCH-DR-STRATEGY",
    "SEC-AUTH-001", "SEC-AUTH-002", "SEC-RBAC-001", "SEC-RBAC-002",
    "SEC-CRED-001", "SEC-NET-001", "SEC-VUL-001", "SEC-VUL-002", "SEC-PEN-TEST",
    "OPS-MON-001", "OPS-CICD-001", "OPS-INC-001", "OPS-CAP-001",
    "OPS-DISABLE-001", "OPS-RUN-001", "OPS-SLA-001", "OPS-ROLLBACK-001",
    "GOV-RAI-001", "GOV-OVER-001", "GOV-LIFE-001", "GOV-BIAS-001",
    "GOV-RESP-001", "GOV-RESP-002",
]
RECOMMENDED_PATHS = ["waiver", "remediate", "escalate", "no_precedent"]
DECISION_OUTCOMES = ["approved", "conditionally_approved", "rejected", "waived"]
ROLES = [
    "engineering-director", "compliance-officer", "ciso", "security-lead",
    "ml-engineer", "data-steward", "product-owner", "devops-engineer",
    "vp-engineering", "chief-compliance-officer",
]

# Weighting: more 'remediate' and 'waiver' paths, fewer 'no_precedent'
RECOMMENDED_PATH_WEIGHTS = [0.35, 0.40, 0.15, 0.10]

PROPOSAL_NAME_TEMPLATES = [
    "AI {adjective} {use_case} System",
    "{use_case} Intelligence Platform",
    "Automated {use_case} Assistant",
    "ML-Powered {use_case} Engine",
    "{adjective} {use_case} Service",
]
ADJECTIVES = ["Predictive", "Adaptive", "Intelligent", "Automated", "Smart",
               "Conversational", "Generative", "Analytical", "Proactive", "Contextual"]
USE_CASES = ["Claims Processing", "Care Management", "Code Review", "Document Analysis",
              "Member Outreach", "Quality Assurance", "Risk Scoring", "Prior Authorization",
              "Workforce Planning", "Fraud Detection", "Benefits Advisory", "Scheduling"]


def random_proposal_name() -> str:
    template = random.choice(PROPOSAL_NAME_TEMPLATES)
    return template.format(
        adjective=random.choice(ADJECTIVES),
        use_case=random.choice(USE_CASES),
    )


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def generate_exception_record(record_id: int) -> dict:
    """Generate a single synthetic ExceptionRecord."""
    failing_rules = random.sample(RULE_IDS, k=random.randint(1, 4))
    tier = random.choice(TIERS)
    domain = random.choice(DOMAINS)
    recommended_path = random.choices(RECOMMENDED_PATHS, weights=RECOMMENDED_PATH_WEIGHTS, k=1)[0]

    submitted_date = random_date(
        datetime(2024, 1, 1),
        datetime(2026, 3, 1),
    )
    resolved_date = submitted_date + timedelta(days=random.randint(2, 45))
    decision_outcome = random.choice(DECISION_OUTCOMES)

    confidence = round(random.uniform(0.50, 0.98), 2)
    estimated_approval_probability = round(random.uniform(0.30, 0.95), 2)

    conditions = []
    if recommended_path in ("waiver", "remediate") and decision_outcome != "rejected":
        n_conditions = random.randint(1, 3)
        condition_templates = [
            "Provide {doc} documentation within {days} days",
            "Remediate {rule} before production deployment",
            "Obtain sign-off from {role}",
            "Submit quarterly review for {domain} compliance",
            "Enable {control} in CI/CD pipeline",
            "Complete {task} by {date}",
        ]
        for _ in range(n_conditions):
            template = random.choice(condition_templates)
            conditions.append(template.format(
                doc=random.choice(["break-glass", "runbook", "DR strategy", "bias monitoring", "SLA"]),
                days=random.choice([30, 60, 90]),
                rule=random.choice(failing_rules),
                role=random.choice(ROLES),
                domain=domain,
                control=random.choice(["Trivy scanning", "binary authorization", "RBAC", "secrets management"]),
                task=random.choice(["penetration test", "model validation", "data classification audit"]),
                date=(resolved_date + timedelta(days=random.randint(30, 180))).strftime("%Y-%m-%d"),
            ))

    reviewer_name = fake.name()
    reviewer_role = random.choice(ROLES)

    return {
        "id": f"EXCEPTION-{record_id:05d}",
        "proposalId": f"{submitted_date.strftime('%Y-%m-%d')}_{fake.slug()}",
        "proposalName": random_proposal_name(),
        "team": fake.company(),
        "tier": tier,
        "failingRules": failing_rules,
        "domain": domain,
        "recommendedPath": recommended_path,
        "confidence": confidence,
        "estimatedApprovalProbability": estimated_approval_probability,
        "decisionOutcome": decision_outcome,
        "suggestedConditions": conditions,
        "submittedAt": submitted_date.isoformat() + "Z",
        "resolvedAt": resolved_date.isoformat() + "Z",
        "reviewedBy": {
            "name": reviewer_name,
            "role": reviewer_role,
        },
        "rationaleSummary": _generate_rationale(recommended_path, failing_rules, decision_outcome),
        "evidenceProvided": random.sample([
            "Architecture diagram",
            "Security assessment",
            "Runbook draft",
            "Vendor BAA",
            "Penetration test results",
            "DR plan",
            "SLA document",
            "Bias monitoring report",
        ], k=random.randint(0, 3)),
        "rEffAtReview": round(random.uniform(0.45, 0.95), 3),
    }


def generate_reviewer_history_entry(record_id: int) -> dict:
    """Generate a synthetic reviewer decision history entry."""
    reviewer_name = fake.name()
    reviewer_role = random.choice(ROLES)
    decision_date = random_date(datetime(2024, 1, 1), datetime(2026, 3, 1))
    outcome = random.choice(DECISION_OUTCOMES)

    return {
        "id": f"REVIEW-{record_id:05d}",
        "reviewerId": fake.uuid4(),
        "reviewerName": reviewer_name,
        "reviewerRole": reviewer_role,
        "proposalId": f"{decision_date.strftime('%Y-%m-%d')}_{fake.slug()}",
        "decisionDate": decision_date.isoformat() + "Z",
        "outcome": outcome,
        "tier": random.choice(TIERS),
        "cycleTimeHours": round(random.uniform(0.5, 72), 1),
        "rulesReviewed": random.randint(5, 40),
        "rulesFailingAtReview": random.randint(0, 8),
        "conditionsImposed": random.randint(0, 5),
        "escalationRequired": random.random() < 0.2,
        "sodViolationDetected": random.random() < 0.05,
        "notes": fake.sentence() if random.random() < 0.4 else None,
    }


def _generate_rationale(recommended_path: str, failing_rules: list[str],
                          decision_outcome: str) -> str:
    """Generate a plausible rationale string."""
    rule_str = ", ".join(failing_rules[:2])
    if recommended_path == "waiver":
        return (f"Team requested waiver for {rule_str}. "
                f"Risk accepted with compensating controls. Decision: {decision_outcome}.")
    elif recommended_path == "remediate":
        return (f"Remediation path identified for {rule_str}. "
                f"Team committed to evidence submission timeline. Decision: {decision_outcome}.")
    elif recommended_path == "escalate":
        return (f"Escalated to senior leadership due to {rule_str} failures. "
                f"Additional review required. Decision: {decision_outcome}.")
    else:
        return f"No precedent found for {rule_str}. Manual review required."


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic AIDEN exception records and reviewer decision history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=50,
                        help="Number of exception records to generate (default: 50)")
    parser.add_argument("--history-count", type=int, default=None,
                        help="Number of reviewer history entries (default: same as --count)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path (default: stdout)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)

    history_count = args.history_count if args.history_count is not None else args.count

    print(f"Generating {args.count} exception records and {history_count} history entries...",
          flush=True)

    exception_records = [
        generate_exception_record(i + 1) for i in range(args.count)
    ]
    reviewer_history = [
        generate_reviewer_history_entry(i + 1) for i in range(history_count)
    ]

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "seed": args.seed,
        "totalExceptionRecords": len(exception_records),
        "totalReviewerHistoryEntries": len(reviewer_history),
        "exceptionRecords": exception_records,
        "reviewerHistory": reviewer_history,
    }

    json_output = json.dumps(output, indent=2, default=str)

    if args.output:
        output_path = Path(args.output) if hasattr(args, "output") else None
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"✓ Written to {args.output} ({len(json_output):,} bytes)")
    else:
        print(json_output)


# Ensure Path is available
from pathlib import Path

if __name__ == "__main__":
    main()
