#!/usr/bin/env python3
"""
AIDEN Review Pack Generator
============================
Generates a single PDF review pack from AIDEN engine output artifacts.

Inputs:
    - review-data.json     — structured review results (section profiles, guard decisions)
    - gate-decision.json   — gate outcome and autonomy ledger entry
    - bias-audit.json      — bias audit results
    - TEVB Markdown views  — functional, procedural, role-enactor, module-interface

Output:
    - <proposal-id>-review-pack.pdf

Usage:
    python review_pack_generator.py \\
        --review-data ./out/review-data.json \\
        --gate-decision ./out/gate-decision.json \\
        --bias-audit ./out/bias-audit.json \\
        --tevb-dir ./out/tevb/ \\
        --output ./out/review-pack.pdf
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader
from weasyprint import HTML, CSS

# ── Jinja2 Template ───────────────────────────────────────────────────────────

REVIEW_PACK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AIDEN Review Pack — {{ proposal_name }}</title>
<style>
  @page {
    size: A4;
    margin: 2cm 2cm 2cm 2cm;
    @bottom-center { content: "Page " counter(page) " of " counter(pages); font-size: 9pt; color: #666; }
  }
  body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 10pt; color: #222; line-height: 1.5; }
  h1 { font-size: 20pt; color: #1a1a2e; border-bottom: 2px solid #0066cc; padding-bottom: 6pt; }
  h2 { font-size: 14pt; color: #0066cc; margin-top: 18pt; border-bottom: 1px solid #cce0ff; padding-bottom: 3pt; }
  h3 { font-size: 11pt; color: #333; margin-top: 12pt; }
  .meta { color: #555; font-size: 9pt; margin-bottom: 12pt; }
  .gate-badge {
    display: inline-block; padding: 4pt 12pt; border-radius: 4pt; font-size: 14pt; font-weight: bold;
    margin: 8pt 0;
  }
  .gate-APPROVE { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
  .gate-CONDITIONAL { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
  .gate-BLOCK { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
  table { width: 100%; border-collapse: collapse; margin: 8pt 0; font-size: 9pt; }
  th { background: #0066cc; color: white; padding: 4pt 6pt; text-align: left; }
  td { padding: 3pt 6pt; border-bottom: 1px solid #eee; }
  tr:nth-child(even) { background: #f8f9ff; }
  .pass { color: #155724; font-weight: bold; }
  .fail { color: #721c24; font-weight: bold; }
  .degrade { color: #856404; font-weight: bold; }
  .abstain { color: #6c757d; }
  .waived { color: #004085; }
  .section-break { page-break-before: always; }
  .r-eff-bar { height: 8pt; background: #e9ecef; border-radius: 4pt; margin: 4pt 0; }
  .r-eff-fill { height: 8pt; border-radius: 4pt; }
  .r-eff-high { background: #28a745; }
  .r-eff-med { background: #ffc107; }
  .r-eff-low { background: #dc3545; }
  .rationale-list { margin: 0; padding-left: 16pt; }
  .tevb-section { font-size: 9pt; background: #f8f9fa; padding: 8pt; border-left: 3px solid #0066cc; margin: 6pt 0; }
  pre { font-family: 'Courier New', monospace; font-size: 8pt; background: #f4f4f4; padding: 6pt; overflow-wrap: break-word; }
  .footer-note { font-size: 8pt; color: #888; margin-top: 24pt; border-top: 1px solid #eee; padding-top: 6pt; }
</style>
</head>
<body>

<h1>AIDEN Policy Review Pack</h1>
<div class="meta">
  <strong>Proposal:</strong> {{ proposal_name }} ({{ proposal_id }})<br>
  <strong>Team:</strong> {{ team }}<br>
  <strong>Submitted by:</strong> {{ submitted_by }} on {{ submitted_at }}<br>
  <strong>Tier:</strong> {{ tier }}<br>
  <strong>Review generated:</strong> {{ reviewed_at }}<br>
  <strong>Engine version:</strong> {{ engine_version }}
</div>

<!-- ── Gate Decision ────────────────────────────────────────── -->
<h2>Gate Decision</h2>
<div class="gate-badge gate-{{ gate_outcome }}">{{ gate_outcome }}</div>
<p><strong>Overall R_eff:</strong> {{ overall_r_eff | default("—") }}
   &nbsp;|&nbsp; <strong>Formality:</strong> {{ overall_formality | default("—") }}</p>

{% if rationale %}
<h3>Rationale</h3>
<ul class="rationale-list">
  {% for r in rationale %}<li>{{ r }}</li>{% endfor %}
</ul>
{% endif %}

{% if waivers_applied %}
<h3>Waivers Applied</h3>
<ul>{% for w in waivers_applied %}<li>{{ w }}</li>{% endfor %}</ul>
{% endif %}

{% if escalation_required %}
<p><strong>⚠ Escalation required.</strong> Override requires: {{ override_requires | join(", ") }}</p>
{% endif %}

<!-- ── Section Profiles ─────────────────────────────────────── -->
<h2>Section Assurance Profiles</h2>
<table>
  <tr>
    <th>Domain</th><th>F</th><th>RuleCoverage</th><th>R_eff</th>
    <th>Pass</th><th>Fail</th><th>Abstain</th><th>Degrade</th><th>Waived</th>
  </tr>
  {% for s in sections %}
  <tr>
    <td>{{ s.domain }}</td>
    <td>{{ s.formality }}</td>
    <td>{{ "%.3f" | format(s.ruleCoverage) }}</td>
    <td>{% if s.rEff is not none %}{{ "%.3f" | format(s.rEff) }}{% else %}null{% endif %}</td>
    <td class="pass">{{ s.tallies.passed }}</td>
    <td class="fail">{{ s.tallies.failed }}</td>
    <td class="abstain">{{ s.tallies.abstained }}</td>
    <td class="degrade">{{ s.tallies.degraded }}</td>
    <td class="waived">{{ s.tallies.waived }}</td>
  </tr>
  {% endfor %}
</table>

<!-- ── Guard Decisions ──────────────────────────────────────── -->
<h2>Guard Decision Detail</h2>
{% for s in sections %}
<h3>{{ s.domain | title }}</h3>
<table>
  <tr><th>Rule ID</th><th>Outcome</th><th>Severity</th><th>Field Path</th><th>Reason</th></tr>
  {% for d in s.guardDecisions %}
  <tr>
    <td>{{ d.ruleId }}</td>
    <td class="{{ d.outcome }}">{{ d.outcome | upper }}</td>
    <td>{{ d.severity | default("—") }}</td>
    <td>{{ d.fieldPath | default("—") }}</td>
    <td>{{ d.reason }}</td>
  </tr>
  {% endfor %}
</table>
{% endfor %}

<!-- ── Bias Audit ────────────────────────────────────────────── -->
{% if bias_audit %}
<div class="section-break"></div>
<h2>Bias Audit</h2>
<p><strong>Overall Risk:</strong> {{ bias_audit.get("overallRisk", "unknown") }}
   &nbsp;|&nbsp; <strong>Panel Review Required:</strong> {{ "Yes" if bias_audit.get("panelReviewRequired") else "No" }}</p>

{% if bias_audit.get("vectors") %}
<table>
  <tr><th>Bias Vector</th><th>Severity</th><th>Affected Populations</th><th>Mitigations</th></tr>
  {% for v in bias_audit.get("vectors", []) %}
  <tr>
    <td>{{ v.vector }}</td>
    <td>{{ v.severity }}</td>
    <td>{{ v.affectedPopulations | join(", ") if v.affectedPopulations else "—" }}</td>
    <td>{{ v.mitigations | join("; ") if v.mitigations else "—" }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}
{% endif %}

<!-- ── TEVB Views ─────────────────────────────────────────────── -->
{% if tevb_views %}
<div class="section-break"></div>
<h2>TEVB Architecture Views</h2>
{% for view_name, view_content in tevb_views.items() %}
<h3>{{ view_name | replace("-", " ") | title }}</h3>
<div class="tevb-section">{{ view_content }}</div>
{% endfor %}
{% endif %}

<div class="footer-note">
  Generated by AIDEN v1 MVE · {{ reviewed_at }} ·
  This document is auto-generated from machine-readable evidence. Human review is required before any approval decision.
</div>

</body>
</html>
"""


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_pdf(context: dict, output_path: Path) -> None:
    """Render the review pack HTML template to PDF using WeasyPrint."""
    env = Environment(loader=BaseLoader())
    template = env.from_string(REVIEW_PACK_HTML)
    html_content = template.render(**context)
    HTML(string=html_content).write_pdf(str(output_path))


def load_json_file(path: Path) -> dict | None:
    """Load a JSON file, return None if not found."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tevb_views(tevb_dir: Path) -> dict[str, str]:
    """Load TEVB Markdown view files from a directory."""
    views = {}
    if not tevb_dir or not tevb_dir.exists():
        return views

    view_files = {
        "functional": "functional.md",
        "procedural": "procedural.md",
        "role-enactor": "role-enactor.md",
        "module-interface": "module-interface.md",
    }
    for view_name, filename in view_files.items():
        fp = tevb_dir / filename
        if fp.exists():
            views[view_name] = fp.read_text(encoding="utf-8")
    return views


def build_context(review_data: dict, gate_decision: dict,
                   bias_audit: dict | None, tevb_views: dict) -> dict:
    """Build the Jinja2 template context from raw artifacts.

    Consumes the engine's actual output schema (review-data.json):
      - overallProfile: { fEff, rEff, sections, unevaluableSections, criticalAbstains }
      - sectionProfiles: [ { domain, F, ruleCoverage, rEff, tallies, ... } ]
      - gaps, exceptionSuggestions, policyVersions

    Maps these into the template variables expected by REVIEW_PACK_HTML.
    """
    overall_profile = review_data.get("overallProfile", {})
    section_profiles = review_data.get("sectionProfiles", [])

    # Map engine sectionProfiles into template sections.
    # Engine uses "F" (int) for formality; template expects "formality" as "F0"–"F3".
    sections_list = []
    for sp in section_profiles:
        sections_list.append({
            "domain": sp.get("domain", "unknown"),
            "formality": f"F{sp.get('F', 0)}",
            "ruleCoverage": sp.get("ruleCoverage", 0),
            "rEff": sp.get("rEff"),
            "tallies": sp.get("tallies", {}),
            "criticalFails": sp.get("criticalFails", 0),
            "highFails": sp.get("highFails", 0),
            "guardDecisions": sp.get("guardDecisions", []),
        })

    # Derive overall R_eff and formality from overallProfile
    overall_r_eff = overall_profile.get("rEff")
    overall_formality = f"F{overall_profile.get('fEff', 0)}" if overall_profile else "F0"

    return {
        "proposal_id": review_data.get("proposalId", "unknown"),
        "proposal_name": review_data.get("proposalName", "Unknown"),
        "team": "—",
        "submitted_by": "—",
        "submitted_at": "—",
        "tier": review_data.get("tier", "—"),
        "reviewed_at": review_data.get("generatedAt") or datetime.utcnow().isoformat() + "Z",
        "engine_version": review_data.get("engineVersion", "1.0.0"),
        "overall_r_eff": overall_r_eff,
        "overall_formality": overall_formality,
        "gate_outcome": gate_decision.get("outcome", "BLOCK"),
        "rationale": gate_decision.get("rationale", []),
        "waivers_applied": gate_decision.get("waiversApplied", []),
        "escalation_required": gate_decision.get("escalationRequired", False),
        "override_requires": gate_decision.get("overrideRequires", []),
        "sections": sections_list,
        "bias_audit": bias_audit,
        "tevb_views": tevb_views,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a PDF AIDEN review pack from engine output artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--review-data", required=True, help="Path to review-data.json")
    parser.add_argument("--gate-decision", required=True, help="Path to gate-decision.json")
    parser.add_argument("--bias-audit", default=None, help="Path to bias-audit.json (optional)")
    parser.add_argument("--tevb-dir", default=None, help="Directory containing TEVB .md view files (optional)")
    parser.add_argument("--output", required=True, help="Output PDF file path")
    args = parser.parse_args()

    review_data_path = Path(args.review_data)
    gate_decision_path = Path(args.gate_decision)
    bias_audit_path = Path(args.bias_audit) if args.bias_audit else None
    tevb_dir = Path(args.tevb_dir) if args.tevb_dir else None
    output_path = Path(args.output)

    # Validate inputs
    for p in [review_data_path, gate_decision_path]:
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading review data from {review_data_path}...")
    review_data = load_json_file(review_data_path) or {}

    print(f"Loading gate decision from {gate_decision_path}...")
    gate_decision = load_json_file(gate_decision_path) or {}

    bias_audit = load_json_file(bias_audit_path) if bias_audit_path else None
    if bias_audit:
        print(f"Loaded bias audit from {bias_audit_path}")

    tevb_views = load_tevb_views(tevb_dir) if tevb_dir else {}
    if tevb_views:
        print(f"Loaded {len(tevb_views)} TEVB view(s) from {tevb_dir}")

    context = build_context(review_data, gate_decision, bias_audit, tevb_views)
    print(f"Rendering PDF review pack to {output_path}...")
    render_pdf(context, output_path)

    print(f"✓ Review pack generated: {output_path} ({output_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
