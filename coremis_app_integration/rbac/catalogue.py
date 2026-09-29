"""TASAFMIS business-role catalogue → openIMIS right codes.

Version-controlled source for the ``seed_tasaf_roles`` management command. Each entry becomes a
``core.Role`` (``tblRole``, ``is_system = 0`` so it stays UI-editable) with one ``core.RoleRight``
(``tblRoleRight``) per right code.

Right codes are the verified ones harvested from each module's ``apps.py`` ``DEFAULT_CONFIG`` — see
``docs/pssn/Roles/ROLE_RIGHTS_MAPPING.md`` (the source of truth). Codes still marked ``(confirm)`` in
that doc are deliberately excluded here until Phase 1 closes them.

Right-code convention: 6-digit ``MMEEAA`` = module(2) · entity(2) · action(2); action ``01`` search,
``02`` create, ``03`` update, ``04`` delete, ``10+`` special (approve / dispatch / import / run).

``group`` tags the PSSN III core user group (UG01–UG08) purely for traceability to the Guideline;
openIMIS itself has no group concept — the person's workstream lives in FreeIPA/Keycloak upstream.
``pilot`` marks the first-wave subset seeded by default (``--all`` seeds everything).
"""

# ── Named right codes ──────────────
# Core / administration
R_USER_SEARCH, R_USER_CREATE, R_USER_DELETE = 121701, 121702, 121704
R_ROLE_SEARCH, R_ROLE_CREATE, R_ROLE_UPDATE, R_ROLE_DELETE = 122001, 122002, 122003, 122004
R_LOC = [121901, 121902, 121903, 121904, 121905, 121906]
R_SCHEMA = [171001, 171002, 171003, 171004]
R_DEDUP = [172001, 172002]
R_FLOW = [240101, 240102, 240103, 240104]
R_VIEW_MASKED = 900101

# Access requests (module 23)
R_AR_SEARCH, R_AR_VIEW = 230101, 230102
R_AR_MANAGER_APPROVE, R_AR_ICT_APPROVE = 230201, 230202

# Individual & household registry
R_INDIV_SEARCH, R_INDIV_CREATE, R_INDIV_UPDATE = 159001, 159002, 159003
R_LEGACY_INDIV_SEARCH, R_LEGACY_GROUP_SEARCH = 260001, 260011
R_GROUP_SEARCH, R_GROUP_CREATE = 180001, 180002

# Social protection (benefit plan / enrolment / project)
R_BP_SEARCH, R_BP_CREATE, R_BP_UPDATE = 160001, 160002, 160003
R_ENROL_SEARCH, R_ENROL_CREATE, R_ENROL_UPDATE = 170001, 170002, 170003
R_PROJECT_SEARCH = 209001
R_INDIV_UPDATE_ = 159003 
R_GROUP_UPDATE = 180003
R_GRM_RESOLVE = 127006

# Payment cycle / payroll / reconciliation
R_CYCLE_SEARCH, R_CYCLE_CREATE = 200001, 200002
R_PAYROLL_SEARCH, R_PAYROLL_CREATE = 202001, 202002
R_RECON_SEARCH, R_RECON_CREATE = 206001, 206002

# TASAF payment (paylist)
R_PAYLIST_SEARCH, R_PAYLIST_GENERATE, R_PAYLIST_APPROVE, R_PAYLIST_SUBMIT = 270301, 270302, 270303, 270304
R_PAY_FEEDBACK_SEARCH = 270401
R_PAY_DASHBOARD = 270501

# Data imports — api_etl (module 95) and legacy_individual (module 26)
R_ETL_RULE_SEARCH, R_ETL_RULE_EXECUTE = 953001, 953002
R_LEGACY_IMPORT, R_LEGACY_MATCH_REVIEW, R_LEGACY_PROMOTE = 260021, 260031, 260041

# Grievance
R_GRM = [127000, 127001, 127002, 127003, 127004, 127005, 127006]
R_GRM_INTAKE = [127000, 127001]

# Training
R_TRAINING_REPORT = 211301
R_TRAINING_CATEGORY_SEARCH = 211001
R_TRAINING_JOB_TITLE_SEARCH = 211101
R_TRAINING_LEVEL_SEARCH = 211401
R_TRAINING_REFDATA = [R_TRAINING_CATEGORY_SEARCH, R_TRAINING_JOB_TITLE_SEARCH,
                      R_TRAINING_LEVEL_SEARCH]
R_TRAINING = [210101, 210102, 210103, 210104, 210110, R_TRAINING_REPORT] + R_TRAINING_REFDATA
R_TRAINING_DASHBOARD = 210601
R_TRAINING_PARTICIPANT_CREATE = 210702

# Communications (module 22): entity → 01 search, 02 create, 03 update, 04 delete
R_COMMS_SEARCH = 220101
R_COMMS_DASHBOARD = 221201
COMMS_WORK_ENTITIES = [2201, 2204, 2205, 2206, 2208, 2210, 2211, 2214, 2215, 2216, 2218, 2219]
COMMS_REFERENCE_ENTITIES = [2202, 2203, 2209, 2213, 2217]
R_COMMS_ATTACHMENT = [220701, 220702]
R_COMMS_ACTIVITY_APPROVE, R_COMMS_CHANNEL_DISPATCH, R_COMMS_POST_PUBLISH = 220110, 220305, 221505
R_COMMS_SEARCH_ALL = [e * 100 + 1 for e in COMMS_WORK_ENTITIES + COMMS_REFERENCE_ENTITIES] + [220701]
R_COMMS_MAKE = [e * 100 + a for e in COMMS_WORK_ENTITIES for a in (2, 3)] + R_COMMS_ATTACHMENT
R_COMMS_DELETE = [e * 100 + 4 for e in COMMS_WORK_ENTITIES] + [220704]
R_COMMS_REFERENCE_MANAGE = [e * 100 + a for e in COMMS_REFERENCE_ENTITIES for a in (2, 3, 4)]

# Coordination (module built in this repo; block 2511xx)
R_COORD_SEARCH, R_COORD_CREATE, R_COORD_UPDATE, R_COORD_DELETE = 251101, 251102, 251103, 251104
R_COORD_MANAGER_APPROVE, R_COORD_OFFICER_APPROVE, R_COORD_DEPT_APPROVE = 251110, 251111, 251112
R_COORD_DEPT_MANAGE, R_COORD_DASHBOARD, R_COORD_ADMIN = 251202, 251601, 251901
R_UNIFIED_CALENDAR = 251602

# Case management (module 29). Household/member edits are maker-checker: the maker holds the
# registry update rights, the checker holds R_CASE_PENDING_DECIDE, never both.
R_CASE_CONSOLE, R_CASE_VIEW = 290101, 290102
R_CASE_PAYMENT_CHANGE_SEARCH, R_CASE_ACCOUNT_CORRECTION = 290201, 290205
R_CASE_DEACTIVATION_SEARCH, R_CASE_FOLLOWUP_SEARCH = 290301, 290401
R_CASE_PENDING_SEARCH, R_CASE_PENDING_DECIDE = 290501, 290502
CASE_READ_ALL = [R_CASE_CONSOLE, R_CASE_VIEW, R_CASE_PAYMENT_CHANGE_SEARCH, R_CASE_ACCOUNT_CORRECTION,
                 R_CASE_DEACTIVATION_SEARCH, R_CASE_FOLLOWUP_SEARCH, R_CASE_PENDING_SEARCH]

# Read-only "search" set used by oversight roles (Auditor / M&E / ED).
READ_ACROSS = [
    R_INDIV_SEARCH, R_GROUP_SEARCH, R_BP_SEARCH, R_ENROL_SEARCH, R_PROJECT_SEARCH,
    R_CYCLE_SEARCH, R_PAYROLL_SEARCH, R_PAYLIST_SEARCH, R_PAY_FEEDBACK_SEARCH,
    R_GRM[0], 210101, R_COMMS_SEARCH, R_TRAINING_REPORT,
]
DASHBOARDS = [R_PAY_DASHBOARD, R_TRAINING_DASHBOARD, R_COMMS_DASHBOARD, R_COORD_DASHBOARD,
              R_UNIFIED_CALENDAR]

# PSSN II (legacy) registry, read-only.
LEGACY_REGISTRY_READ = [R_LEGACY_INDIV_SEARCH, R_LEGACY_GROUP_SEARCH]


def _role(group, description, rights, pilot=True):
    # De-dup while preserving order.
    seen, ordered = set(), []
    for r in rights:
        if r not in seen:
            seen.add(r)
            ordered.append(int(r))
    return {'group': group, 'description': description, 'rights': ordered, 'pilot': pilot}


# ── The catalogue ──────────────────────────────────────────────────────────────────────────────
ROLE_CATALOGUE = {
    # UG03 — Finance, Disbursement & E-Payment (maker → reviewer → approver kept separate)
    'Disbursement Maker': _role(
        'UG03', 'Prepares payment cycles, payroll, reconciliation and paylists. Cannot approve.',
        [R_CYCLE_SEARCH, R_CYCLE_CREATE, R_PAYROLL_SEARCH, R_PAYROLL_CREATE,
         R_RECON_SEARCH, R_RECON_CREATE, R_PAYLIST_SEARCH, R_PAYLIST_GENERATE]),
    'Finance Manager (Reviewer)': _role(
        'UG03', 'Reviews/reconciles payment work. No final authorisation.',
        [R_CYCLE_SEARCH, R_PAYROLL_SEARCH, R_RECON_SEARCH, R_PAYLIST_SEARCH, R_PAY_FEEDBACK_SEARCH]),
    'Payment Approver': _role(
        'UG03', 'Final disbursement authority (paylist approve/submit). No preparation.',
        [R_PAYLIST_APPROVE, R_PAYLIST_SUBMIT, R_PAYLIST_SEARCH, R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH]),

    # UG06 — Programs, PCT & Economic Inclusion
    'PCT Officer': _role(
        'UG06', 'Enrolment maker; records training/participation; raises grievances. '
                'Sees the whole case-management cycle read-only (submissions, decisions, follow-ups).',
        [R_ENROL_SEARCH, R_ENROL_CREATE, R_ENROL_UPDATE, R_INDIV_SEARCH, R_GROUP_SEARCH,
         210101, 210102, R_TRAINING_PARTICIPANT_CREATE, R_TRAINING_CATEGORY_SEARCH,
         R_TRAINING_LEVEL_SEARCH,
         R_TRAINING_REPORT, 127000, 127001, 127002] + CASE_READ_ALL),
    'PCT Manager': _role(
        'UG06', 'Reviews programme work; owns the Training module.',
        [R_ENROL_SEARCH, R_BP_SEARCH, R_PROJECT_SEARCH, R_INDIV_SEARCH, R_GROUP_SEARCH,
         127000, R_UNIFIED_CALENDAR] + R_TRAINING),

    # UG07 — CSPW / Safeguards / GRM
    'GRM Intake': _role(
        'UG07', 'Registers grievances and initial info; no sensitive-case closure.',
        R_GRM_INTAKE + [R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH]),
    'Grievance Officer': _role(
        'UG07', 'Full grievance CRUD incl. resolve; reads registry/enrolment/payment.',
        R_GRM + [R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH, R_PAYLIST_SEARCH]),

    # UG08 — Monitoring, Evaluation & Data (read-only across modules + reporting)
    'M&E Officer': _role(
        'UG08', 'Reads approved data across modules; dashboards. No CRUD outside M&E.',
        READ_ACROSS + DASHBOARDS + LEGACY_REGISTRY_READ),
    'M&E Manager': _role(
        'UG08', 'Broader cross-module read + reporting/dashboards management.',
        READ_ACROSS + DASHBOARDS + LEGACY_REGISTRY_READ + [R_BP_SEARCH, R_PROJECT_SEARCH]),

    # UG05 — ICT, Systems & Digital Delivery (config only; NO business approval)
    'System Administrator': _role(
        'UG05', 'Configures users/roles/locations/schema/flows/dedup. No business approvals.',
        [R_USER_SEARCH, R_USER_CREATE, R_USER_DELETE, R_ROLE_SEARCH, R_ROLE_CREATE, R_ROLE_UPDATE,
         R_ROLE_DELETE] + R_LOC + R_SCHEMA + R_FLOW + R_DEDUP),

    # Access-request sign-off — kept out of System Administrator (config only, no approvals).
    'Access Request Sponsor': _role(
        'UG04', 'Department/unit manager sign-off on access requests (MANAGER step).',
        [R_AR_SEARCH, R_AR_VIEW, R_AR_MANAGER_APPROVE]),
    'ICT Access Approver': _role(
        'UG05', 'ICT sign-off on access requests (ICT step). Approval only.',
        [R_AR_SEARCH, R_AR_VIEW, R_AR_ICT_APPROVE]),

    # UG02 — Internal Audit & Assurance (read-only + masked data)
    'Internal Auditor': _role(
        'UG02', 'Reads everything (incl. masked data); changes nothing.',
        READ_ACROSS + DASHBOARDS + [R_VIEW_MASKED]),

    # Field / Directorate tiers that the enrolment approval cascade routes to (Phase 3).
    'Council Coordinator': _role(
        'UG07', 'Endorses council enrolment; registry corrections; resolves council grievances.',
        [R_INDIV_SEARCH, R_INDIV_UPDATE_, R_GROUP_SEARCH, R_GROUP_UPDATE,
         R_ENROL_SEARCH, R_ENROL_UPDATE, R_GRM_RESOLVE, R_PAYLIST_SEARCH]),
    'Director of Programs': _role(
        'UG06', 'Final programme/enrolment approver; benefit-plan setup; training certification.',
        [R_ENROL_SEARCH, R_ENROL_UPDATE, R_BP_SEARCH, R_BP_CREATE, R_BP_UPDATE, R_PROJECT_SEARCH,
         R_INDIV_SEARCH, R_GROUP_SEARCH, R_GRM_RESOLVE, 210110,
         R_TRAINING_REPORT] + DASHBOARDS),

    # PAA household/member data updates: PAAF submits (mobile), TMO approves. Scope to the PAA
    # comes from the user's assigned locations, not the role.
    'PAA Facilitator': _role(
        'UG07', 'PAAF: submits household and member changes (mobile app); they wait for TMO '
                'approval. Tracks own district\'s submissions. Cannot approve.',
        [R_INDIV_SEARCH, R_INDIV_UPDATE, R_GROUP_SEARCH, R_GROUP_UPDATE,
         R_CASE_CONSOLE, R_CASE_VIEW, R_CASE_PENDING_SEARCH]),
    'TMO': _role(
        'UG07', 'TASAF Monitoring Officer: approves or rejects PAAF household/member changes in '
                'Pending updates. Makes no registry changes.',
        [R_INDIV_SEARCH, R_GROUP_SEARCH,
         R_CASE_CONSOLE, R_CASE_VIEW, R_CASE_PENDING_SEARCH, R_CASE_PENDING_DECIDE]),

    # UG01 — Coordination module approval chain (submit → manager → officer → dept)
    'Coordination Officer (maker)': _role(
        'UG01', 'Creates/updates and submits coordination activities.',
        [R_COORD_SEARCH, R_COORD_CREATE, R_COORD_UPDATE, R_UNIFIED_CALENDAR]),
    'Coordination Line Manager': _role(
        'UG01', 'First approval hop: manager-approve submitted activities.',
        [R_COORD_SEARCH, R_COORD_MANAGER_APPROVE]),
    'Coordination Officer (approver)': _role(
        'UG01', 'Second approval hop: coordination-officer approve.',
        [R_COORD_SEARCH, R_COORD_OFFICER_APPROVE]),
    'Coordination Manager': _role(
        'UG01', 'Final approval hop + department admin/settings for Coordination.',
        [R_COORD_SEARCH, R_COORD_DEPT_APPROVE, R_COORD_DEPT_MANAGE, R_COORD_DASHBOARD,
         R_COORD_ADMIN, R_UNIFIED_CALENDAR]),

    # UG08 — data imports (ETL pull from the SS server, legacy PSSN import and match review)
    'Data Import Officer': _role(
        'UG08', 'Runs ETL and legacy imports, reviews matches, promotes to the registry. No deletes.',
        [R_ETL_RULE_SEARCH, R_ETL_RULE_EXECUTE, R_LEGACY_INDIV_SEARCH, R_LEGACY_GROUP_SEARCH,
         R_LEGACY_IMPORT, R_LEGACY_MATCH_REVIEW, R_LEGACY_PROMOTE,
         R_INDIV_SEARCH, R_INDIV_CREATE, R_GROUP_SEARCH]),

    # UG01 — Communications maker-checker (SN 13, 14)
    'Communications Officer': _role(
        'UG01', 'Creates and updates activities, posts, registries and events. Cannot approve, '
                'publish or dispatch.',
        R_COMMS_SEARCH_ALL + R_COMMS_MAKE + [R_COMMS_DASHBOARD]),
    'Communications Manager': _role(
        'UG01', 'Approves activities, publishes posts, dispatches channels; deletes; manages '
                'reference lists.',
        R_COMMS_SEARCH_ALL + R_COMMS_DELETE + R_COMMS_REFERENCE_MANAGE
        + [R_COMMS_ACTIVITY_APPROVE, R_COMMS_CHANNEL_DISPATCH, R_COMMS_POST_PUBLISH,
           R_COMMS_DASHBOARD]),
    # Stubs: no rights until the module exists. Add codes here and re-seed when it lands.
    # docs/RBAC_TITLE_TO_ROLE_MAPPING_PROPOSAL.md §3.
    'Procurement (stub)': _role('UG01', 'Placeholder — SN 7, 48, 49.', []),
    'Legal (stub)': _role('UG01', 'Placeholder — SN 36, 57.', []),
    'Registry and Records (stub)': _role('UG04', 'Placeholder — SN 6, 42, 50, 51, 52.', []),
    'Supplies, Inventory and Transport (stub)': _role('UG04', 'Placeholder — SN 8, 39, 53, 63.', []),
    'Corporate Administration (stub)': _role('UG04', 'Placeholder — SN 1, 5, 41.', []),
    'ICT Support and Development (stub)': _role('UG05', 'Placeholder — SN 9, 34, 54, 56, 59.', []),
    'CSPW and Field Safeguards (stub)': _role('UG07', 'Placeholder — SN 15, 16, 45, 46, 47.', []),
    'Targeted Infrastructure (stub)': _role('UG07', 'Placeholder — SN 60, 61.', []),
}

PILOT_ROLE_NAMES = [name for name, entry in ROLE_CATALOGUE.items() if entry['pilot']]

STUB_ROLE_NAMES = [name for name, entry in ROLE_CATALOGUE.items() if not entry['rights']]
