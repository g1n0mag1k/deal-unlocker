#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generates the ClearPath Health SIG Lite sample deliverable as print-ready HTML."""

import datetime

TODAY = datetime.date(2026, 10, 28)

def dplus(days):
    return (TODAY + datetime.timedelta(days=days)).strftime("%B %-d, %Y")

# ---------------------------------------------------------------------------
# Question bank: (id, domain, question, answer "Y"/"N", citation_or_finding,
#                 priority "High"/"Medium"/"Low" for gaps, days_out for gaps)
# ---------------------------------------------------------------------------

Q = []

def add(domain, qtext, ans, note, priority=None, days=None):
    qid = f"{len(Q)+1:02d}"
    Q.append(dict(id=qid, domain=domain, q=qtext, ans=ans, note=note,
                   priority=priority, days=days))

# ---- Asset Management (10) ----
add("Asset Management", "Does the organization maintain an inventory of all information system assets (hardware, software, cloud services)?", "Y", "Ref: Asset Inventory v1.3 (Asset Panda, reconciled monthly)")
add("Asset Management", "Is the asset inventory updated on a defined schedule?", "Y", "Ref: Asset Management Policy v1.1, §3.2 (monthly reconciliation)")
add("Asset Management", "Are all production servers and endpoints tagged with a data classification level?", "N", "Asset tagging exists for ownership but not for data classification level.", "Medium", 60)
add("Asset Management", "Is there a documented asset decommissioning/disposal procedure, including data sanitization?", "Y", "Ref: Asset Decommissioning SOP v1.0")
add("Asset Management", "Are mobile devices used to access company systems enrolled in a mobile device management (MDM) solution?", "Y", "Ref: MDM Enrollment Policy v1.0 (Jamf / Microsoft Intune)")
add("Asset Management", "Is full-disk encryption enforced on all laptops issued to employees?", "Y", "Ref: Endpoint Encryption Standard v1.0 (BitLocker/FileVault, enforced via MDM)")
add("Asset Management", "Does the organization maintain a software bill of materials (SBOM) for its production application?", "N", "No SBOM currently generated for the production codebase or its dependencies.", "Low", 90)
add("Asset Management", "Are end-of-life / end-of-support dates tracked for all software and operating system versions in use?", "N", "No centralized EOL/EOS tracking process exists; currently ad hoc.", "Medium", 75)
add("Asset Management", "Is there a formal asset ownership assignment, with each asset mapped to a named owner?", "Y", "Ref: Asset Inventory v1.3, “Owner” field")
add("Asset Management", "Are removable media (USB drives, external storage) restricted or prohibited on company endpoints?", "Y", "Ref: Endpoint Security Policy v1.0, §4 (USB write-block enforced via MDM)")

# ---- Data Management (14) ----
add("Data Management", "Does the organization maintain a data classification policy (e.g., public / internal / confidential / restricted)?", "Y", "Ref: Data Classification Policy v1.0")
add("Data Management", "Is PHI / ePHI specifically identified and labeled as a distinct data classification tier?", "Y", "Ref: Data Classification Policy v1.0, §2.3 (PHI tier)")
add("Data Management", "Is data encrypted at rest for all production databases?", "Y", "Ref: Encryption Standard v1.0 (AES-256, AWS RDS storage encryption enabled)")
add("Data Management", "Is data encrypted in transit (TLS 1.2 or higher) for all external connections?", "Y", "Ref: Encryption Standard v1.0, §3 (TLS 1.2 minimum, enforced at load balancer)")
add("Data Management", "Does the organization maintain a documented data retention schedule?", "N", "No formal retention schedule; data is retained indefinitely by default.", "High", 60)
add("Data Management", "Is there a documented and tested data deletion/destruction procedure upon client request or contract termination?", "N", "No formal procedure; deletions have been handled manually on an ad hoc basis.", "High", 60)
add("Data Management", "Are database backups encrypted?", "Y", "Ref: Backup & Recovery Policy v1.0, §2 (encrypted snapshots, AWS KMS)")
add("Data Management", "Is production data used in non-production (development/test/staging) environments?", "N", "Production PHI is currently copied to staging without masking or de-identification.", "High", 45)
add("Data Management", "Is there a data masking or de-identification process for any non-production use of data?", "N", "No masking/synthetic-data process exists for staging or developer environments.", "High", 45)
add("Data Management", "Does the organization maintain a documented data flow diagram showing where PHI is collected, stored, processed, and transmitted?", "Y", "Ref: Data Flow Diagram v1.0 (reviewed August 2026)")
add("Data Management", "Are database administrative credentials stored in a secrets manager rather than hardcoded or in plaintext?", "Y", "Ref: Secrets Management Standard v1.0 (AWS Secrets Manager)")
add("Data Management", "Is there a defined data owner or steward for each major data category?", "Y", "Ref: Data Classification Policy v1.0, Appendix A")
add("Data Management", "Does the organization encrypt data stored on backup media or offsite backups?", "Y", "Ref: Backup & Recovery Policy v1.0, §2")
add("Data Management", "Is there a process to ensure data minimization, i.e., collecting only data necessary for the stated purpose?", "Y", "Ref: Privacy-by-Design Checklist v1.0, applied at feature intake")

# ---- Security Policy (10) ----
add("Security Policy", "Does the organization maintain a formal, leadership-approved information security policy?", "Y", "Ref: Information Security Policy v1.2 (approved by CEO, March 2026)")
add("Security Policy", "Is the information security policy reviewed and updated at least annually?", "Y", "Ref: Information Security Policy v1.2, §1 (annual review cycle)")
add("Security Policy", "Does the organization have a designated individual responsible for information security (CISO, Security Officer, or equivalent)?", "Y", "Ref: Information Security Policy v1.2, §2 (Security Officer designated)")
add("Security Policy", "Is there a documented acceptable use policy for company systems?", "Y", "Ref: Acceptable Use Policy v1.0")
add("Security Policy", "Do employees receive security awareness training upon hire and annually thereafter?", "Y", "Ref: Security Awareness Training Log 2026 (KnowBe4, 100% completion)")
add("Security Policy", "Does the organization conduct a periodic (at least annual) formal risk assessment?", "N", "No formal, documented risk assessment has been completed to date.", "High", 60)
add("Security Policy", "Is there a documented change management policy for production systems?", "Y", "Ref: Change Management Policy v1.0")
add("Security Policy", "Does the organization have a formal exception process for policy deviations?", "N", "Policy exceptions are currently handled informally with no documented process.", "Low", 90)
add("Security Policy", "Is there a documented password policy meeting minimum complexity and rotation standards?", "Y", "Ref: Identity & Access Management Policy v1.1, §3")
add("Security Policy", "Has the organization completed a SOC 2 Type I or Type II audit, or a formal HITRUST assessment?", "N", "SOC 2 Type I readiness assessment is in progress; no completed audit yet.", "Medium", 90)

# ---- Access Control (14) ----
add("Access Control", "Is access to production systems granted based on least privilege / role-based access control (RBAC)?", "Y", "Ref: Identity & Access Management Policy v1.1, §2")
add("Access Control", "Is multi-factor authentication (MFA) enforced for all remote/VPN access?", "Y", "Ref: IAM Policy v1.1, §4 (Okta MFA enforced)")
add("Access Control", "Is MFA enforced for access to production cloud infrastructure (AWS/Azure/GCP console)?", "Y", "Ref: IAM Policy v1.1, §4 (AWS IAM + Okta SSO, MFA required)")
add("Access Control", "Is MFA enforced for access to the application containing PHI?", "Y", "Ref: IAM Policy v1.1, §4")
add("Access Control", "Are user access rights reviewed on a periodic (at least quarterly) basis?", "N", "No periodic access recertification process exists; access reviews have been reactive only.", "High", 60)
add("Access Control", "Is there a documented, timely offboarding procedure that revokes access upon termination?", "Y", "Ref: Offboarding SOP v1.0 (access revoked within 4 business hours of termination notice)")
add("Access Control", "Are privileged/administrative accounts separate from standard user accounts?", "Y", "Ref: IAM Policy v1.1, §5 (separate admin accounts; no shared root use)")
add("Access Control", "Is shared or generic account usage prohibited, i.e., does each user have a unique ID?", "Y", "Ref: IAM Policy v1.1, §1")
add("Access Control", "Is there a formal access request and approval workflow requiring manager/owner sign-off?", "Y", "Ref: Access Request SOP v1.0 (Jira-based approval workflow)")
add("Access Control", "Are session timeouts enforced for applications handling PHI?", "Y", "Ref: Application Security Standard v1.0, §2 (15-minute idle timeout)")
add("Access Control", "Is remote access to the corporate network restricted to company-managed, MDM-enrolled devices?", "N", "Some staff access company systems from unmanaged personal devices.", "Medium", 75)
add("Access Control", "Does the organization log and actively monitor privileged account activity?", "N", "Privileged activity is logged but not actively monitored or alerted on.", "High", 60)
add("Access Control", "Is there a documented process for emergency (“break-glass”) access to production systems?", "N", "No formal break-glass procedure is documented.", "Medium", 75)
add("Access Control", "Are failed login attempts monitored and accounts locked out after a defined threshold?", "Y", "Ref: IAM Policy v1.1, §3 (5 failed attempts, 30-minute lockout)")

# ---- Incident Management (12) ----
add("Incident Management", "Does the organization maintain a documented security incident response plan?", "Y", "Ref: Incident Response Plan v1.0")
add("Incident Management", "Is the incident response plan tested via tabletop exercise or similar at least annually?", "N", "The IR plan has not yet been exercised through a tabletop simulation.", "Medium", 75)
add("Incident Management", "Is there a designated incident response team with defined roles and responsibilities?", "Y", "Ref: Incident Response Plan v1.0, §2")
add("Incident Management", "Does the organization have a documented breach notification procedure consistent with the HIPAA Breach Notification Rule (45 CFR §§ 164.400–414) timelines?", "Y", "Ref: Breach Notification SOP v1.0")
add("Incident Management", "Is there defined, continuous monitoring and alerting for security events on production systems?", "N", "Logs are collected but not continuously monitored; no alerting pipeline is configured.", "High", 45)
add("Incident Management", "Does the organization maintain centralized logging for production systems (application, infrastructure, and access logs)?", "Y", "Ref: Logging Standard v1.0 (CloudWatch + centralized log aggregation)")
add("Incident Management", "Are logs retained for a minimum of one year, or per applicable regulatory requirement?", "Y", "Ref: Logging Standard v1.0, §3 (13-month retention)")
add("Incident Management", "Is there a documented process for notifying affected customers/business associates in the event of a breach involving their data?", "Y", "Ref: Breach Notification SOP v1.0, §4")
add("Incident Management", "Has the organization experienced a reportable security incident or breach in the past 12 months?", "Y", "Ref: Incident Log 2026 — zero reportable incidents on record as of this disclosure")
add("Incident Management", "Is there a post-incident review / lessons-learned process?", "Y", "Ref: Incident Response Plan v1.0, §6")
add("Incident Management", "Does the organization maintain cyber liability / technology errors & omissions (E&O) insurance?", "N", "Coverage has not yet been bound; quotes are being evaluated.", "High", 45)
add("Incident Management", "Is there a defined escalation path to executive leadership for high-severity incidents?", "Y", "Ref: Incident Response Plan v1.0, §3")

# ---- Third-Party Management (12) ----
add("Third-Party Management", "Does the organization maintain an inventory of all third-party vendors/subprocessors with access to PHI or company systems?", "Y", "Ref: Subprocessor Register v1.0")
add("Third-Party Management", "Are Business Associate Agreements (BAAs) executed with all subprocessors that handle PHI?", "N", "2 of 9 listed subprocessors do not yet have an executed BAA on file.", "High", 30)
add("Third-Party Management", "Is there a vendor risk assessment performed prior to onboarding a new vendor?", "N", "No formal pre-onboarding risk assessment process exists.", "Medium", 75)
add("Third-Party Management", "Does the organization review vendor SOC 2 reports or equivalent security attestations prior to engagement?", "N", "Vendor security attestations are not consistently collected or reviewed.", "Medium", 75)
add("Third-Party Management", "Is a documented subprocessor list made available to customers (e.g., in a DPA or published list)?", "Y", "Ref: Subprocessor Register v1.0 (published at clearpathhealth.com/subprocessors)")
add("Third-Party Management", "Are vendors contractually required to notify the organization of a security incident affecting shared data?", "Y", "Ref: Standard Vendor Agreement Template v1.0, §7 (incident notification clause)")
add("Third-Party Management", "Is vendor access to production systems reviewed or re-certified periodically?", "N", "No periodic re-certification of vendor access currently takes place.", "Medium", 75)
add("Third-Party Management", "Does the organization have a process to offboard vendors and revoke their access upon contract termination?", "Y", "Ref: Vendor Offboarding SOP v1.0")
add("Third-Party Management", "Is the cloud infrastructure provider (AWS) contractually bound by a signed BAA?", "Y", "Ref: AWS Business Associate Addendum (executed January 2025)")
add("Third-Party Management", "Is there a documented approval process before employees adopt new third-party SaaS or AI tools?", "N", "No formal intake/approval process exists for new SaaS or AI tool adoption.", "High", 45)
add("Third-Party Management", "Does the organization require vendors handling PHI to maintain encryption at rest and in transit?", "Y", "Ref: Standard Vendor Agreement Template v1.0, §8")
add("Third-Party Management", "Is there a named individual responsible for vendor/third-party risk management?", "Y", "Ref: Information Security Policy v1.2, §2 (Security Officer)")

# ---- Business Continuity (8) ----
add("Business Continuity", "Does the organization maintain a documented business continuity / disaster recovery (BC/DR) plan?", "Y", "Ref: Business Continuity & DR Plan v1.0")
add("Business Continuity", "Is the BC/DR plan tested at least annually?", "N", "The BC/DR plan has not yet been formally tested.", "Medium", 75)
add("Business Continuity", "Are production database backups performed on a defined schedule (e.g., daily)?", "Y", "Ref: Backup & Recovery Policy v1.0, §1 (automated daily snapshots)")
add("Business Continuity", "Are backups tested for restorability on a periodic basis?", "N", "Backup restoration has not been formally tested within the past 12 months.", "High", 60)
add("Business Continuity", "Does the organization have a defined Recovery Time Objective (RTO) and Recovery Point Objective (RPO)?", "Y", "Ref: Business Continuity & DR Plan v1.0, §3 (RTO: 8 hrs, RPO: 1 hr)")
add("Business Continuity", "Is production infrastructure deployed across multiple availability zones/regions to support failover?", "Y", "Ref: Infrastructure Architecture Diagram v1.0 (multi-AZ AWS deployment)")
add("Business Continuity", "Does the organization maintain an alternate communication plan for use during an outage or incident?", "N", "No documented out-of-band communication plan exists for staff or customers during an outage.", "Low", 90)
add("Business Continuity", "Is there a documented succession plan for key personnel (e.g., Security Officer, CTO)?", "N", "No formal succession plan exists for key security/technical roles.", "Low", 90)

assert len(Q) == 80, f"expected 80 questions, got {len(Q)}"

gaps = [q for q in Q if q["ans"] == "N"]
yes_count = len(Q) - len(gaps)

domains_order = ["Asset Management", "Data Management", "Security Policy",
                  "Access Control", "Incident Management",
                  "Third-Party Management", "Business Continuity"]

domain_gap_counts = {d: sum(1 for g in gaps if g["domain"] == d) for d in domains_order}
domain_totals = {d: sum(1 for q in Q if q["domain"] == d) for d in domains_order}

high_gaps = [g for g in gaps if g["priority"] == "High"]
med_gaps = [g for g in gaps if g["priority"] == "Medium"]
low_gaps = [g for g in gaps if g["priority"] == "Low"]

print(f"Total questions: {len(Q)} | Yes: {yes_count} | Gaps: {len(gaps)}")
print(f"High: {len(high_gaps)} Medium: {len(med_gaps)} Low: {len(low_gaps)}")

# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def pill(ans):
    if ans == "Y":
        return '<span class="pill pill-yes">YES</span>'
    return '<span class="pill pill-no">NO</span>'

def priority_pill(p):
    cls = {"High": "pr-high", "Medium": "pr-med", "Low": "pr-low"}[p]
    return f'<span class="pr-pill {cls}">{p}</span>'

rows_by_domain = {}
for q in Q:
    rows_by_domain.setdefault(q["domain"], []).append(q)

domain_anchor = lambda d: "dom-" + d.lower().replace(" ", "-").replace("/", "-")

qa_sections = []
for d in domains_order:
    items = rows_by_domain[d]
    rows_html = []
    for q in items:
        if q["ans"] == "Y":
            note_html = f'<span class="citation">{esc(q["note"])}</span>'
        else:
            note_html = f'<span class="finding">{esc(q["note"])}</span> <span class="see-gap">— see Gap Register, target {dplus(q["days"])}</span>'
        rows_html.append(f"""
        <tr>
          <td class="qid">SIG-{q['id']}</td>
          <td class="qtext">{esc(q['q'])}</td>
          <td class="qans">{pill(q['ans'])}</td>
          <td class="qnote">{note_html}</td>
        </tr>""")
    gap_n = domain_gap_counts[d]
    tot_n = domain_totals[d]
    qa_sections.append(f"""
    <section class="domain-section" id="{domain_anchor(d)}">
      <h3>{esc(d)} <span class="domain-tally">{tot_n - gap_n}/{tot_n} satisfied</span></h3>
      <table class="qa-table">
        <thead>
          <tr><th class="col-id">ID</th><th class="col-q">Question</th><th class="col-ans">Answer</th><th class="col-note">Artifact / Finding</th></tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </section>""")

qa_html = "\n".join(qa_sections)

# Gap Register table, sorted by priority then domain
priority_rank = {"High": 0, "Medium": 1, "Low": 2}
gaps_sorted = sorted(gaps, key=lambda g: (priority_rank[g["priority"]], domains_order.index(g["domain"])))

gap_rows = []
for g in gaps_sorted:
    artifact_req = {
        3: "Data Classification Tagging Standard (updated)",
        7: "Software Bill of Materials (SBOM)",
        8: "EOL/EOS Tracking Register",
        15: "Data Retention Schedule",
        16: "Data Deletion & Destruction SOP",
        18: "Non-Production Data Handling Policy",
        19: "Data Masking / Synthetic Data Procedure",
        26: "Annual Risk Assessment Report",
        28: "Policy Exception Log & Procedure",
        30: "SOC 2 Type I Report",
        35: "Quarterly Access Recertification Log",
        41: "Mobile/Remote Access Device Policy (MDM-only enforcement)",
        42: "Privileged Access Monitoring & Alerting SOP",
        43: "Break-Glass Access Procedure",
        46: "Tabletop Exercise After-Action Report",
        49: "Security Monitoring & Alerting Runbook",
        51: "Cyber Liability / Tech E&O Insurance Certificate",
        53: "Vendor BAA Tracker (2 outstanding)",
        54: "Vendor Risk Assessment SOP",
        55: "Vendor Security Attestation Collection Log",
        57: "Vendor Access Re-certification SOP",
        60: "AI/SaaS Tool Intake & Approval Policy",
        66: "BC/DR Tabletop Test Report",
        68: "Backup Restoration Test Report",
        71: "Alternate Communications Plan",
        72: "Key Personnel Succession Plan",
    }.get(int(g["id"]), "Remediation Evidence (TBD)")
    gap_rows.append(f"""
        <tr>
          <td>{priority_pill(g['priority'])}</td>
          <td class="gap-domain">{esc(g['domain'])}</td>
          <td class="gap-control">{esc(g['q'])}</td>
          <td class="gap-finding">{esc(g['note'])}</td>
          <td class="gap-date">{dplus(g['days'])}</td>
          <td class="gap-artifact">{esc(artifact_req)}</td>
        </tr>""")

gap_register_html = "\n".join(gap_rows)

toc_items = "".join(
    f'<li><a href="#{domain_anchor(d)}">{esc(d)} <span class="toc-count">({domain_totals[d]} questions, {domain_gap_counts[d]} open)</span></a></li>'
    for d in domains_order
)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ClearPath Health — SIG Lite Response &amp; Gap Register</title>
<style>
  :root {{
    --navy: #0f2a4a;
    --navy-light: #1d4273;
    --accent: #1a73a3;
    --accent-light: #e8f1f6;
    --ink: #1c242e;
    --muted: #5b6672;
    --border: #d7dde3;
    --bg-soft: #f6f8fa;
    --yes: #1b7a43;
    --yes-bg: #e5f5ea;
    --no: #b23b2e;
    --no-bg: #fbeae7;
    --high: #b23b2e;
    --high-bg: #fbeae7;
    --med: #a4700a;
    --med-bg: #fbf1de;
    --low: #4c5a68;
    --low-bg: #eef1f4;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    color: var(--ink);
    margin: 0;
    background: #fff;
    font-size: 13.5px;
    line-height: 1.5;
  }}
  .page {{ max-width: 980px; margin: 0 auto; padding: 40px 48px 64px; }}

  /* ---- Masthead ---- */
  .masthead {{
    display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 3px solid var(--navy); padding-bottom: 18px; margin-bottom: 28px;
  }}
  .masthead h1 {{ font-size: 22px; margin: 0 0 4px; color: var(--navy); letter-spacing: -0.2px; }}
  .masthead .sub {{ color: var(--muted); font-size: 13px; }}
  .masthead .meta {{ text-align: right; font-size: 12px; color: var(--muted); line-height: 1.7; }}
  .masthead .meta strong {{ color: var(--ink); }}
  .doc-tag {{
    display: inline-block; background: var(--navy); color: #fff; font-size: 10.5px;
    font-weight: 600; letter-spacing: 0.06em; padding: 3px 9px; border-radius: 3px;
    text-transform: uppercase; margin-bottom: 8px;
  }}

  /* ---- Reviewer Brief ---- */
  .brief {{
    background: var(--bg-soft); border: 1px solid var(--border); border-left: 5px solid var(--navy);
    border-radius: 6px; padding: 22px 26px; margin-bottom: 34px; page-break-inside: avoid;
  }}
  .brief h2 {{ margin: 0 0 14px; font-size: 16.5px; color: var(--navy); }}
  .brief-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; margin-bottom: 16px; }}
  .brief-grid .label {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 2px; }}
  .brief-grid .value {{ font-size: 13.5px; }}
  .stat-row {{ display: flex; gap: 14px; margin: 14px 0 16px; flex-wrap: wrap; }}
  .stat-box {{ background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 10px 16px; min-width: 108px; text-align: center; }}
  .stat-box .num {{ font-size: 22px; font-weight: 700; color: var(--navy); line-height: 1.1; }}
  .stat-box.alert .num {{ color: var(--high); }}
  .stat-box .lbl {{ font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }}
  .brief p {{ margin: 8px 0; }}
  .brief .priority-line {{ font-size: 12.5px; color: var(--muted); }}
  .brief .priority-line b {{ color: var(--ink); }}

  /* ---- TOC ---- */
  .toc {{ margin-bottom: 30px; }}
  .toc h3 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; }}
  .toc ul {{ list-style: none; margin: 0; padding: 0; columns: 2; column-gap: 32px; }}
  .toc li {{ margin-bottom: 6px; break-inside: avoid; }}
  .toc a {{ color: var(--accent); text-decoration: none; font-size: 12.5px; }}
  .toc-count {{ color: var(--muted); font-size: 11px; }}

  h2.section-title {{
    font-size: 16px; color: var(--navy); border-bottom: 2px solid var(--border);
    padding-bottom: 6px; margin: 38px 0 18px;
  }}

  /* ---- Domain / Q&A tables ---- */
  .domain-section {{ margin-bottom: 26px; page-break-inside: avoid; }}
  .domain-section h3 {{
    font-size: 13.5px; color: var(--navy-light); background: var(--accent-light);
    padding: 7px 12px; border-radius: 4px; margin: 0 0 8px; display: flex;
    justify-content: space-between; align-items: center;
  }}
  .domain-tally {{ font-size: 11px; font-weight: 500; color: var(--navy); }}
  table.qa-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  table.qa-table th {{
    text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--muted); border-bottom: 1px solid var(--border); padding: 5px 8px;
  }}
  table.qa-table td {{ padding: 7px 8px; border-bottom: 1px solid #ecf0f3; vertical-align: top; }}
  .col-id {{ width: 7%; }} .col-q {{ width: 40%; }} .col-ans {{ width: 8%; }} .col-note {{ width: 45%; }}
  .qid {{ font-family: "SFMono-Regular", Consolas, monospace; font-size: 10.5px; color: var(--muted); }}
  .pill {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.03em; }}
  .pill-yes {{ background: var(--yes-bg); color: var(--yes); }}
  .pill-no {{ background: var(--no-bg); color: var(--no); }}
  .citation {{ color: var(--muted); font-style: italic; }}
  .finding {{ color: var(--no); }}
  .see-gap {{ color: var(--muted); font-size: 11px; }}

  /* ---- Gap Register ---- */
  table.gap-table {{ width: 100%; border-collapse: collapse; font-size: 11.8px; margin-top: 6px; }}
  table.gap-table th {{
    text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    color: #fff; background: var(--navy); padding: 8px; position: sticky; top: 0;
  }}
  table.gap-table td {{ padding: 8px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  table.gap-table tr:nth-child(even) td {{ background: #fafbfc; }}
  .gap-control {{ font-weight: 600; width: 22%; }}
  .gap-finding {{ color: var(--muted); width: 26%; }}
  .gap-date {{ white-space: nowrap; font-weight: 600; color: var(--navy); }}
  .gap-domain {{ color: var(--muted); font-size: 11px; white-space: nowrap; }}
  .gap-artifact {{ width: 20%; }}
  .pr-pill {{ font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }}
  .pr-high {{ background: var(--high-bg); color: var(--high); }}
  .pr-med {{ background: var(--med-bg); color: var(--med); }}
  .pr-low {{ background: var(--low-bg); color: var(--low); }}

  .footer {{
    margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border);
    font-size: 10.5px; color: var(--muted); display: flex; justify-content: space-between;
  }}
  .sample-watermark {{
    position: fixed; top: 46%; left: 50%; transform: translate(-50%,-50%) rotate(-28deg);
    font-size: 86px; font-weight: 800; color: rgba(15,42,74,0.06); z-index: -1;
    letter-spacing: 0.05em; pointer-events: none; white-space: nowrap;
  }}

  @media print {{
    .page {{ padding: 0.3in 0.5in; }}
    .domain-section {{ break-inside: avoid; }}
    table.gap-table {{ break-inside: auto; }}
    table.gap-table tr {{ break-inside: avoid; }}
    a {{ color: inherit; text-decoration: none; }}
  }}
  @page {{ margin: 0.5in; size: letter; }}
</style>
</head>
<body>
<div class="sample-watermark">SAMPLE — FICTIONAL DATA</div>
<div class="page">

  <div class="masthead">
    <div>
      <div class="doc-tag">SIG Lite Response &amp; Gap Register</div>
      <h1>ClearPath Health, Inc.</h1>
      <div class="sub">Standardized Information Gathering (SIG) Lite &mdash; Security Questionnaire Response</div>
    </div>
    <div class="meta">
      <div><strong>Prepared for:</strong> Enterprise Buyer Security Review Team</div>
      <div><strong>Prepared:</strong> {TODAY.strftime('%B %-d, %Y')}</div>
      <div><strong>Scope:</strong> ClearPath Patient Engagement Platform (production)</div>
      <div><strong>Document support:</strong> Sui-Generis LLC &mdash; Deal Unlocker</div>
    </div>
  </div>

  <div class="brief">
    <h2>Reviewer Brief</h2>
    <div class="brief-grid">
      <div>
        <div class="label">Company</div>
        <div class="value">ClearPath Health, Inc. &mdash; 15-employee healthtech SaaS company providing patient engagement software to hospital systems and ambulatory networks.</div>
      </div>
      <div>
        <div class="label">Product in scope</div>
        <div class="value">ClearPath patient engagement platform (web application, mobile app, and supporting AWS infrastructure). Processes and stores ePHI on behalf of covered-entity customers under executed Business Associate Agreements.</div>
      </div>
      <div>
        <div class="label">Questionnaire</div>
        <div class="value">SIG Lite, 80 questions, standard domains. Answered by ClearPath's Security Officer and reviewed for completeness prior to delivery.</div>
      </div>
      <div>
        <div class="label">Overall posture summary</div>
        <div class="value">Core technical controls (encryption, MFA, RBAC, network architecture) are in place and evidenced. Open items cluster in governance cadence (periodic reviews, testing, formal risk assessment) rather than foundational control gaps &mdash; consistent with a 15-person company at this stage of growth.</div>
      </div>
    </div>
    <div class="stat-row">
      <div class="stat-box"><div class="num">{len(Q)}</div><div class="lbl">Questions</div></div>
      <div class="stat-box"><div class="num">{yes_count}</div><div class="lbl">Satisfied</div></div>
      <div class="stat-box alert"><div class="num">{len(gaps)}</div><div class="lbl">Open gaps</div></div>
      <div class="stat-box alert"><div class="num">{len(high_gaps)}</div><div class="lbl">High priority</div></div>
      <div class="stat-box"><div class="num">{len(med_gaps)}</div><div class="lbl">Medium priority</div></div>
      <div class="stat-box"><div class="num">{len(low_gaps)}</div><div class="lbl">Low priority</div></div>
    </div>
    <p class="priority-line"><b>Fastest-closing high-priority items:</b> staging PHI masking (Dec 12), outstanding subprocessor BAAs (Nov 27), security monitoring/alerting (Dec 12), AI/SaaS tool intake policy (Dec 12), cyber E&amp;O coverage (Dec 12). Full remediation timeline and artifact requirements follow in the Gap Register below.</p>
    <p class="priority-line">This brief and the attached answer set are intended to give your security review team a complete, source-cited picture of ClearPath's control environment in a single pass, with named artifacts available for follow-up evidence requests. No statement in this document should be read as a legal compliance or certification conclusion.</p>
  </div>

  <div class="toc">
    <h3>Domains in this response</h3>
    <ul>{toc_items}</ul>
  </div>

  <h2 class="section-title">Part 1 &mdash; SIG Lite Answer Set (80 Questions)</h2>
  {qa_html}

  <h2 class="section-title">Part 2 &mdash; Gap Register</h2>
  <p style="color:var(--muted); font-size:12.5px; margin-bottom:14px;">
    Every "No" response above is tracked here as a dated remediation item. Target dates reflect priority:
    High-priority items are scheduled within 30&ndash;60 days, Medium within 75 days, and Low within 90 days of this
    assessment ({TODAY.strftime('%B %-d, %Y')}). This register is the forward plan ClearPath's Security Officer
    is accountable for; it is not a representation that the organization is "compliant" with any specific
    regulation or framework.
  </p>
  <table class="gap-table">
    <thead>
      <tr><th style="width:8%">Priority</th><th style="width:11%">Domain</th><th>Control</th><th>Finding</th><th style="width:10%">Target Date</th><th>Artifact Required</th></tr>
    </thead>
    <tbody>
      {gap_register_html}
    </tbody>
  </table>

  <div class="footer">
    <div>ClearPath Health, Inc. &mdash; SIG Lite Response &amp; Gap Register &mdash; Fictional sample for demonstration purposes only.</div>
    <div>Prepared with Deal Unlocker by Sui-Generis LLC &mdash; Knoxville, TN</div>
  </div>

</div>
</body>
</html>
"""

with open("/tmp/deliverables/clearpath-health-sig-lite.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Wrote clearpath-health-sig-lite.html")
