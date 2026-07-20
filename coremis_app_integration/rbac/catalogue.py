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

# ── Named right codes (for readability; keep in sync with ROLE_RIGHTS_MAPPING.md) ──────────────
# Core / administration
R_USER_SEARCH, R_USER_CREATE, R_USER_DELETE = 121701, 121702, 121704
R_ROLE_SEARCH, R_ROLE_CREATE, R_ROLE_UPDATE, R_ROLE_DELETE = 122001, 122002, 122003, 122004
R_LOC = [121901, 121902, 121903, 121904, 121905, 121906]
R_SCHEMA = [171001, 171002, 171003, 171004]
R_DEDUP = [172001, 172002]
R_FLOW = [240101, 240102, 240103, 240104]
R_VIEW_MASKED = 900101

# Individual & household registry
R_INDIV_SEARCH, R_INDIV_CREATE, R_INDIV_UPDATE = 159001, 159002, 159003
R_GROUP_SEARCH, R_GROUP_CREATE = 180001, 180002

# Social protection (benefit plan / enrolment / project)
R_BP_SEARCH, R_BP_CREATE, R_BP_UPDATE = 160001, 160002, 160003
R_ENROL_SEARCH, R_ENROL_CREATE, R_ENROL_UPDATE = 170001, 170002, 170003
R_PROJECT_SEARCH = 209001
R_INDIV_UPDATE_ = 159003  # registry correction (WEO/Council)
R_GROUP_UPDATE = 180003
R_GRM_RESOLVE = 127006

# Payment cycle / payroll / reconciliation
R_CYCLE_SEARCH, R_CYCLE_CREATE = 200001, 200002
R_PAYROLL_SEARCH, R_PAYROLL_CREATE = 202001, 202002
R_RECON_SEARCH, R_RECON_CREATE = 206001, 206002

# TASAF payment (paylist)
R_PAYLIST_SEARCH, R_PAYLIST_GENERATE, R_PAYLIST_APPROVE, R_PAYLIST_SUBMIT = 152301, 152302, 152303, 152304
R_PAY_FEEDBACK_SEARCH = 152401
R_PAY_DASHBOARD = 152501

# Grievance
R_GRM = [127000, 127001, 127002, 127003, 127004, 127005, 127006]
R_GRM_INTAKE = [127000, 127001]

# Training
R_TRAINING = [210101, 210102, 210103, 210104, 210110]
R_TRAINING_DASHBOARD = 210601
R_TRAINING_PARTICIPANT_CREATE = 210702

# Communications
R_COMMS_SEARCH = 220101
R_COMMS_DASHBOARD = 221201

# Coordination (module built in this repo; block 2511xx)
R_COORD_SEARCH, R_COORD_CREATE, R_COORD_UPDATE, R_COORD_DELETE = 251101, 251102, 251103, 251104
R_COORD_MANAGER_APPROVE, R_COORD_OFFICER_APPROVE, R_COORD_DEPT_APPROVE = 251110, 251111, 251112
R_COORD_DEPT_MANAGE, R_COORD_DASHBOARD, R_COORD_ADMIN = 251202, 251601, 251901

# Read-only "search" set used by oversight roles (Auditor / M&E / ED).
READ_ACROSS = [
    R_INDIV_SEARCH, R_GROUP_SEARCH, R_BP_SEARCH, R_ENROL_SEARCH, R_PROJECT_SEARCH,
    R_CYCLE_SEARCH, R_PAYROLL_SEARCH, R_PAYLIST_SEARCH, R_PAY_FEEDBACK_SEARCH,
    R_GRM[0], 210101, R_COMMS_SEARCH,
]
DASHBOARDS = [R_PAY_DASHBOARD, R_TRAINING_DASHBOARD, R_COMMS_DASHBOARD, R_COORD_DASHBOARD]


def _role(group, description, rights, pilot=True):
    # De-dup while preserving order.
    seen, ordered = set(), []
    for r in rights:
        if r not in seen:
            seen.add(r)
            ordered.append(int(r))
    return {'group': group, 'description': description, 'rights': ordered, 'pilot': pilot}


# ── The catalogue ──────────────────────────────────────────────────────────────────────────────
# Name ≤ 50 chars (tblRole.RoleName limit). Names are the idempotency key — do not rename casually.
ROLE_CATALOGUE = {
    # UG03 — Finance, Disbursement & E-Payment (maker → reviewer → approver kept separate)
    'TASAF Disbursement Maker': _role(
        'UG03', 'Prepares payment cycles, payroll, reconciliation and paylists. Cannot approve.',
        [R_CYCLE_SEARCH, R_CYCLE_CREATE, R_PAYROLL_SEARCH, R_PAYROLL_CREATE,
         R_RECON_SEARCH, R_RECON_CREATE, R_PAYLIST_SEARCH, R_PAYLIST_GENERATE]),
    'TASAF Finance Manager (Reviewer)': _role(
        'UG03', 'Reviews/reconciles payment work. No final authorisation.',
        [R_CYCLE_SEARCH, R_PAYROLL_SEARCH, R_RECON_SEARCH, R_PAYLIST_SEARCH, R_PAY_FEEDBACK_SEARCH]),
    'TASAF Payment Approver': _role(
        'UG03', 'Final disbursement authority (paylist approve/submit). No preparation.',
        [R_PAYLIST_APPROVE, R_PAYLIST_SUBMIT, R_PAYLIST_SEARCH, R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH]),

    # UG06 — Programs, PCT & Economic Inclusion
    'TASAF PCT Officer': _role(
        'UG06', 'Enrolment maker; records training/participation; raises grievances.',
        [R_ENROL_SEARCH, R_ENROL_CREATE, R_ENROL_UPDATE, R_INDIV_SEARCH, R_GROUP_SEARCH,
         210101, 210102, R_TRAINING_PARTICIPANT_CREATE, 127000, 127001, 127002]),
    'TASAF PCT Manager': _role(
        'UG06', 'Reviews programme work; owns the Training module.',
        [R_ENROL_SEARCH, R_BP_SEARCH, R_PROJECT_SEARCH, R_INDIV_SEARCH, R_GROUP_SEARCH, 127000] + R_TRAINING),

    # UG07 — CSPW / Safeguards / GRM
    'TASAF GRM Intake': _role(
        'UG07', 'Registers grievances and initial info; no sensitive-case closure.',
        R_GRM_INTAKE + [R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH]),
    'TASAF Grievance Officer': _role(
        'UG07', 'Full grievance CRUD incl. resolve; reads registry/enrolment/payment.',
        R_GRM + [R_INDIV_SEARCH, R_GROUP_SEARCH, R_ENROL_SEARCH, R_PAYLIST_SEARCH]),

    # UG08 — Monitoring, Evaluation & Data (read-only across modules + reporting)
    'TASAF M&E Officer': _role(
        'UG08', 'Reads approved data across modules; dashboards. No CRUD outside M&E.',
        READ_ACROSS + DASHBOARDS),
    'TASAF M&E Manager': _role(
        'UG08', 'Broader cross-module read + reporting/dashboards management.',
        READ_ACROSS + DASHBOARDS + [R_BP_SEARCH, R_PROJECT_SEARCH]),

    # UG05 — ICT, Systems & Digital Delivery (config only; NO business approval)
    'TASAF System Administrator': _role(
        'UG05', 'Configures users/roles/locations/schema/flows/dedup. No business approvals.',
        [R_USER_SEARCH, R_USER_CREATE, R_USER_DELETE, R_ROLE_SEARCH, R_ROLE_CREATE, R_ROLE_UPDATE,
         R_ROLE_DELETE] + R_LOC + R_SCHEMA + R_FLOW + R_DEDUP),

    # UG02 — Internal Audit & Assurance (read-only + masked data)
    'TASAF Internal Auditor': _role(
        'UG02', 'Reads everything (incl. masked data); changes nothing.',
        READ_ACROSS + DASHBOARDS + [R_VIEW_MASKED]),

    # Field / Directorate tiers that the enrolment approval cascade routes to (Phase 3).
    'TASAF Council Coordinator': _role(
        'UG07', 'Endorses council enrolment; registry corrections; resolves council grievances.',
        [R_INDIV_SEARCH, R_INDIV_UPDATE_, R_GROUP_SEARCH, R_GROUP_UPDATE,
         R_ENROL_SEARCH, R_ENROL_UPDATE, R_GRM_RESOLVE, R_PAYLIST_SEARCH]),
    'TASAF Director of Programs': _role(
        'UG06', 'Final programme/enrolment approver; benefit-plan setup; training certification.',
        [R_ENROL_SEARCH, R_ENROL_UPDATE, R_BP_SEARCH, R_BP_CREATE, R_BP_UPDATE, R_PROJECT_SEARCH,
         R_INDIV_SEARCH, R_GROUP_SEARCH, R_GRM_RESOLVE, 210110] + DASHBOARDS),

    # UG01 — Coordination module approval chain (submit → manager → officer → dept)
    'TASAF Coordination Officer (maker)': _role(
        'UG01', 'Creates/updates and submits coordination activities.',
        [R_COORD_SEARCH, R_COORD_CREATE, R_COORD_UPDATE]),
    'TASAF Coordination Line Manager': _role(
        'UG01', 'First approval hop: manager-approve submitted activities.',
        [R_COORD_SEARCH, R_COORD_MANAGER_APPROVE]),
    'TASAF Coordination Officer (approver)': _role(
        'UG01', 'Second approval hop: coordination-officer approve.',
        [R_COORD_SEARCH, R_COORD_OFFICER_APPROVE]),
    'TASAF Coordination Manager': _role(
        'UG01', 'Final approval hop + department admin/settings for Coordination.',
        [R_COORD_SEARCH, R_COORD_DEPT_APPROVE, R_COORD_DEPT_MANAGE, R_COORD_DASHBOARD, R_COORD_ADMIN]),
}

PILOT_ROLE_NAMES = [name for name, entry in ROLE_CATALOGUE.items() if entry['pilot']]
