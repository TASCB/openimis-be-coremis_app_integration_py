"""Idempotent seeding of TASAFMIS business roles into ``tblRole`` / ``tblRoleRight``.

Rules (see ``docs/pssn/Roles/OPENIMIS_ROLE_SEED_PLAN.md``):
- Roles are matched by **name** (their idempotency key) among live rows (``validity_to IS NULL``).
- Missing roles are created ``is_system = 0`` (editable in Administration → Roles).
- Missing ``RoleRight`` rows are added; existing ones are left alone.
- **System roles** (``is_system != 0`` — e.g. the IMIS Administrator 64) are never modified.
- Extra rights are removed only when ``prune=True``, and then **soft**-removed (set ``validity_to``)
  per the ``VersionedModel`` convention — never hard-deleted.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# openIMIS bootstrap admin user id used for audit stamping (matches the module rights-seed migrations).
ADMIN_AUDIT_USER_ID = 1
ROLE_NAME_MAX = 50


def seed_roles(catalogue, *, pilot_only=True, prune=False, dry_run=False, emit=None):
    """Create/reconcile roles from ``catalogue``. Returns a summary dict.

    ``emit`` is an optional ``callable(str)`` for progress lines (the command passes
    ``self.stdout.write``); logging happens regardless.
    """
    from core.models import Role, RoleRight

    def _log(msg):
        logger.info(msg)
        if emit:
            emit(msg)

    prefix = '[dry-run] ' if dry_run else ''
    selected = {
        name: entry for name, entry in catalogue.items()
        if (entry.get('pilot', False) or not pilot_only)
    }
    summary = {'created': 0, 'updated': 0, 'rights_added': 0, 'rights_pruned': 0, 'skipped_system': 0}

    for name, entry in selected.items():
        wanted = {int(r) for r in entry['rights']}
        role = Role.objects.filter(name=name, validity_to__isnull=True).order_by('id').first()

        if role and role.is_system and int(role.is_system) != 0:
            _log(f'SKIP system role {name!r} (is_system={role.is_system}) — not managed by the seeder')
            summary['skipped_system'] += 1
            continue

        if not role:
            _log(f'{prefix}CREATE role {name!r} ({len(wanted)} rights)')
            summary['created'] += 1
            if not dry_run:
                role = Role.objects.create(
                    name=name[:ROLE_NAME_MAX], is_system=0, is_blocked=False,
                    audit_user_id=ADMIN_AUDIT_USER_ID,
                )
        else:
            summary['updated'] += 1

        # Without a persisted role (dry-run create) we can't diff rights — count them as would-add.
        if role is None:
            for rid in sorted(wanted):
                _log(f'{prefix}  + right {rid} -> {name!r}')
                summary['rights_added'] += 1
            continue

        have = {rr.right_id for rr in RoleRight.objects.filter(role=role, validity_to__isnull=True)}
        for rid in sorted(wanted - have):
            _log(f'{prefix}  + right {rid} -> {name!r}')
            summary['rights_added'] += 1
            if not dry_run:
                RoleRight.objects.create(role=role, right_id=rid, audit_user_id=ADMIN_AUDIT_USER_ID)

        if prune:
            for rid in sorted(have - wanted):
                _log(f'{prefix}  - right {rid} (prune) from {name!r}')
                summary['rights_pruned'] += 1
                if not dry_run:
                    RoleRight.objects.filter(
                        role=role, right_id=rid, validity_to__isnull=True,
                    ).update(validity_to=timezone.now())

    return summary
