"""Holders of COUNTRYWIDE_ROLE_NAME get every active district."""
import logging

from django.core.cache import cache

from coremis_app_integration.rbac.catalogue import COUNTRYWIDE_ROLE_NAME

logger = logging.getLogger(__name__)

USER_MUTATIONS = {'CreateUserMutation', 'UpdateUserMutation'}


def active_district_ids():
    from location.models import Location
    return set(Location.objects.filter(
        type='D', validity_to__isnull=True, parent__isnull=False,
    ).values_list('id', flat=True))


def users_with_role(role_name=COUNTRYWIDE_ROLE_NAME):
    from core.models import InteractiveUser
    return InteractiveUser.objects.filter(
        validity_to__isnull=True,
        user_roles__validity_to__isnull=True,
        user_roles__role__validity_to__isnull=True,
        user_roles__role__name=role_name,
    ).distinct()


def has_countrywide_role(i_user):
    return users_with_role().filter(id=i_user.id).exists()


def grant_districts(i_user, audit_user_id, district_ids=None, dry_run=False):
    # Reopen end-dated rows: core's update_or_create on (user, location) breaks on duplicates.
    from location.models import UserDistrict, free_cache_for_user

    wanted = active_district_ids() if district_ids is None else set(district_ids)
    rows = UserDistrict.objects.filter(user=i_user, location_id__in=wanted)
    have = set(rows.filter(validity_to__isnull=True).values_list('location_id', flat=True))
    missing = wanted - have
    if not missing or dry_run:
        return len(missing)

    closed = {}
    for row_id, location_id in rows.filter(validity_to__isnull=False, location_id__in=missing) \
            .order_by('id').values_list('id', 'location_id'):
        closed[location_id] = row_id
    if closed:
        UserDistrict.objects.filter(id__in=closed.values()).update(
            validity_to=None, audit_user_id=audit_user_id)
    UserDistrict.objects.bulk_create([
        UserDistrict(user=i_user, location_id=loc, audit_user_id=audit_user_id)
        for loc in missing - closed.keys()
    ])

    free_cache_for_user(i_user.id)
    cache.delete(f"q_allowed_locations_{i_user.id}")
    logger.info("Country-wide access: gave user %s %s district(s)", i_user.login_name, len(missing))
    return len(missing)


def on_user_after_mutation(sender, **kwargs):
    if kwargs.get('error_messages') or kwargs.get('mutation_class') not in USER_MUTATIONS:
        return []
    username = (kwargs.get('data') or {}).get('username')
    if not username:
        return []
    from core.models import InteractiveUser
    i_user = InteractiveUser.objects.filter(login_name=username, validity_to__isnull=True).first()
    if not i_user or not has_countrywide_role(i_user):
        return []
    user = kwargs.get('user')
    audit_user_id = getattr(user, 'id_for_audit', None) or i_user.id
    try:
        grant_districts(i_user, audit_user_id)
    except Exception:
        logger.exception("Country-wide access: grant failed for user %s", username)
    return []


def on_location_saved(sender, instance, created, **kwargs):
    # An edit's history copy is also "created", but end-dated.
    if not created or instance.type != 'D' or instance.validity_to or not instance.parent_id:
        return
    for i_user in users_with_role():
        try:
            grant_districts(i_user, instance.audit_user_id, district_ids={instance.id})
        except Exception:
            logger.exception("Country-wide access: new district %s not given to %s",
                             instance.id, i_user.login_name)


def bind_signals():
    from django.db.models.signals import post_save
    from core.schema import signal_mutation_module_after_mutating
    from location.models import Location

    # Core replaces districts after roles, so grant after the mutation (sent for sync mutations only).
    signal_mutation_module_after_mutating['core'].connect(
        on_user_after_mutation, dispatch_uid='coremis_countrywide_user')
    post_save.connect(on_location_saved, sender=Location, dispatch_uid='coremis_countrywide_location')
