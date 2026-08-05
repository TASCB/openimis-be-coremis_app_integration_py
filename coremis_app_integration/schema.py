"""GraphQL schema for the coremis_app_integration module.

Concatenated into the global openIMIS schema by the assembly (same mechanism as
``payment_cycle``).
"""
import graphene
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from core.gql_queries import (
    ModulePermissionGQLType,
    ModulePermissionsListGQLType,
    PermissionOpenImisGQLType,
)
from core.utils import collect_all_gql_permissions


class Query(graphene.ObjectType):
    my_modules_permissions = graphene.Field(
        ModulePermissionsListGQLType,
        description="Same shape as modulesPermissions, restricted to the rights the "
        "caller actually holds. Requires authentication only.",
    )

    def resolve_my_modules_permissions(self, info, **kwargs):
        user = info.context.user
        if not user or user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))

        granted = {str(right) for right in (getattr(user, "rights", None) or [])}

        config = []
        for app, app_perms in collect_all_gql_permissions().items():
            permissions = [
                PermissionOpenImisGQLType(perms_name=perm_name, perms_value=perm_id)
                for perm_name, perm_ids in app_perms.items()
                for perm_id in perm_ids
                if perm_id in granted
            ]
            if permissions:
                config.append(
                    ModulePermissionGQLType(module_name=app, permissions=permissions)
                )

        return ModulePermissionsListGQLType(module_perms_list=config)
