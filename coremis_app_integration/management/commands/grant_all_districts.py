from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from coremis_app_integration.rbac.catalogue import COUNTRYWIDE_ROLE_NAME
from coremis_app_integration.rbac.countrywide import grant_districts, users_with_role
from coremis_app_integration.rbac.seeder import ADMIN_AUDIT_USER_ID


class Command(BaseCommand):
    help = f"Give users every active district (default: holders of '{COUNTRYWIDE_ROLE_NAME}')."

    def add_arguments(self, parser):
        parser.add_argument('--login', action='append', dest='logins', default=[],
                            help='Login name; repeat for several. Overrides --role.')
        parser.add_argument('--role', default=COUNTRYWIDE_ROLE_NAME,
                            help='Give every holder of this role all districts.')
        parser.add_argument('--dry-run', action='store_true', dest='dry_run')

    def handle(self, *args, **options):
        from core.models import InteractiveUser

        if options['logins']:
            users = list(InteractiveUser.objects.filter(
                login_name__in=options['logins'], validity_to__isnull=True))
            unknown = set(options['logins']) - {u.login_name for u in users}
            if unknown:
                raise CommandError(f"Unknown login(s): {', '.join(sorted(unknown))}")
        else:
            users = list(users_with_role(options['role']))
            if not users:
                self.stdout.write(self.style.WARNING(f"No active user holds role {options['role']!r}."))
                return

        dry = options['dry_run']
        total = 0
        with transaction.atomic():
            for u in users:
                added = grant_districts(u, ADMIN_AUDIT_USER_ID, dry_run=dry)
                total += added
                self.stdout.write(f"{'[dry-run] ' if dry else ''}{u.login_name}: +{added} district(s)")
        self.stdout.write(self.style.SUCCESS(f"Done. users={len(users)} districts_added={total}"))
