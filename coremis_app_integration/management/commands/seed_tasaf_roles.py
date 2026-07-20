"""``manage.py seed_tasaf_roles`` — seed TASAFMIS business roles idempotently.

Creates ``tblRole`` / ``tblRoleRight`` rows from the version-controlled
``coremis_app_integration.rbac.catalogue.ROLE_CATALOGUE``. Safe to re-run: adds only what's missing,
never touches system roles, and only removes catalogue-managed rights with ``--prune``.

See ``docs/pssn/Roles/OPENIMIS_ROLE_SEED_PLAN.md``.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from coremis_app_integration.rbac.catalogue import ROLE_CATALOGUE
from coremis_app_integration.rbac.seeder import seed_roles


class Command(BaseCommand):
    help = ('Seed TASAFMIS business roles (tblRole/tblRoleRight) from the versioned catalogue. '
            'Idempotent; pilot subset by default.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--all', action='store_true', dest='seed_all',
            help='Seed the full catalogue (default: only the pilot subset).')
        parser.add_argument(
            '--prune', action='store_true',
            help='Also soft-remove catalogue-managed RoleRights no longer listed for a role.')
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help='Report what would change without writing (rolls back).')

    def handle(self, *args, **options):
        pilot_only = not options['seed_all']
        dry_run = options['dry_run']
        prune = options['prune']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Seeding TASAF roles ({'PILOT' if pilot_only else 'FULL'} catalogue)"
            f"{' [dry-run]' if dry_run else ''}{' [prune]' if prune else ''}"))

        with transaction.atomic():
            summary = seed_roles(
                ROLE_CATALOGUE, pilot_only=pilot_only, prune=prune,
                dry_run=dry_run, emit=self.stdout.write,
            )
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            "Done. "
            f"created={summary['created']} updated={summary['updated']} "
            f"rights_added={summary['rights_added']} rights_pruned={summary['rights_pruned']} "
            f"skipped_system={summary['skipped_system']}"))
        if not dry_run and (summary['rights_added'] or summary['rights_pruned']):
            self.stdout.write(self.style.WARNING(
                "If any changed role is already assigned to users, clear the Redis 'rights_<userId>' "
                "cache so the new rights take effect (see docs/pssn/error-fixes)."))
