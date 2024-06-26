from functools import lru_cache

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from wagtail.models import GroupPagePermission, PAGE_PERMISSION_TYPES

from content.models import SiteGeneralContent
from indicators.models import (
    ActionIndicator, Dataset, DatasetLicense, Dimension, DimensionCategory, Indicator, IndicatorContactPerson,
    IndicatorDimension, IndicatorGoal, IndicatorGraph, IndicatorLevel, IndicatorValue, Quantity, RelatedIndicator, Unit
)
from notifications.models import BaseTemplate, ContentBlock, AutomaticNotificationTemplate
from orgs.models import Organization
from people.models import Person
from reports.models import Report, ReportType

from .models import (
    Action, AttributeRichText, AttributeType, AttributeChoice, AttributeTypeChoiceOption,
    ActionContactPerson, ActionImpact, ActionResponsibleParty, ActionSchedule, ActionStatus, ActionStatusUpdate,
    ActionTask, Category, CategoryType, ImpactGroup, ImpactGroupAction, MonitoringQualityPoint, Plan,
)

User = get_user_model()


ACTIONS_APP = 'actions'

ALL_PERMS = ('view', 'change', 'publish', 'delete', 'add')


def _get_perm_objs(model, perms):
    content_type = ContentType.objects.get_for_model(model)
    perms = ['%s_%s' % (x, model._meta.model_name) for x in perms]
    perm_objs = Permission.objects.filter(content_type=content_type, codename__in=perms)
    return list(perm_objs)


@lru_cache
def get_wagtail_contact_person_perms():
    perms = []
    perms += list(Permission.objects.filter(
        content_type__app_label='wagtaildocs',
        codename__in=('add_document', 'change_document', 'delete_document')
    ))
    perms += list(Permission.objects.filter(
        content_type__app_label='wagtailimages',
        codename__in=('add_image', 'change_image', 'delete_image')
    ))
    perms += list(Permission.objects.filter(
        content_type__app_label='wagtailcore',
        codename__in=['add_collection', 'view_collection']
    ))
    return perms


@lru_cache
def get_wagtail_plan_admin_perms():
    perms = []
    perms += list(Permission.objects.filter(
        content_type__app_label='wagtailcore',
        codename__in=[
            'change_collection', 'delete_collection',
        ]
    ))
    return perms


@lru_cache
def get_action_contact_person_perms():
    new_perms = []

    # Add general permissions
    new_perms += _get_perm_objs(Action, ('view', 'change', 'publish'))
    new_perms += _get_perm_objs(ActionTask, ('view', 'change', 'delete', 'add'))
    new_perms += _get_perm_objs(Person, ('view', 'change', 'add'))
    new_perms += _get_perm_objs(ActionContactPerson, ALL_PERMS)
    new_perms += _get_perm_objs(ActionStatusUpdate, ALL_PERMS)
    new_perms += _get_perm_objs(ActionIndicator, ('view',))
    new_perms += _get_perm_objs(Indicator, ('view',))

    new_perms += [Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')]
    new_perms += get_wagtail_contact_person_perms()

    for model in (
        ActionResponsibleParty,
    ):
        new_perms += _get_perm_objs(model, ALL_PERMS)
    new_perms += _get_perm_objs(Organization, ('view',))

    return new_perms


@lru_cache
def get_indicator_contact_person_perms():
    new_perms = []

    new_perms += _get_perm_objs(Action, ('view',))
    new_perms += _get_perm_objs(Person, ('view', 'change', 'add'))
    new_perms += _get_perm_objs(ActionIndicator, ('view',))
    new_perms += _get_perm_objs(Indicator, ('view', 'change'))
    new_perms += _get_perm_objs(IndicatorGoal, ('view', 'change'))
    new_perms += _get_perm_objs(IndicatorValue, ('view', 'change', 'add'))
    new_perms += _get_perm_objs(IndicatorContactPerson, ALL_PERMS)

    new_perms += [Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')]
    new_perms += get_wagtail_contact_person_perms()

    return new_perms


def _get_or_create_group(name, perms=None):
    group, _ = Group.objects.get_or_create(name=name)

    if perms is None:
        return group

    existing_perms = set(list(group.permissions.all()))
    new_perms = set(perms)
    if existing_perms != new_perms:
        group.permissions.clear()
        group.permissions.add(*new_perms)

    return group


def get_or_create_action_contact_person_group():
    perms = get_action_contact_person_perms()
    group = _get_or_create_group('Action contact persons', perms)
    return group


@lru_cache
def get_or_create_indicator_contact_person_group():
    perms = get_indicator_contact_person_perms()
    group = _get_or_create_group('Indicator contact persons', perms)
    return group


def _sync_group_collection_perms(root_collection, group, perms):
    current_perms = set([obj.permission for obj in group.collection_permissions.filter(collection=root_collection)])
    for perm in perms:
        if perm not in current_perms:
            group.collection_permissions.create(collection=root_collection, permission=perm)
    for perm in current_perms:
        if perm not in perms:
            group.collection_permissions.get(collection=root_collection, permission=perm).delete()


def _sync_group_page_perms(root_pages, group):
    # Delete all page permissions connected to another root page. (Root pages can be either plan root pages or
    # documentation root pages, and their respective translations are also root pages.)
    qs = GroupPagePermission.objects.filter(group=group)
    for page in root_pages:
        qs = qs.exclude(page=page)
    qs.delete()

    current_perms = GroupPagePermission.objects.filter(group=group)
    perm_set = {gpp.permission.codename for gpp in current_perms}
    new_perm_set = {x[0] for x in PAGE_PERMISSION_TYPES}
    page_set = {gpp.page for gpp in current_perms}
    new_page_set = set(root_pages)
    if perm_set != new_perm_set or page_set != new_page_set:
        current_perms.delete()
        for codename in new_perm_set:
            for page in new_page_set:
                permission = Permission.objects.get(content_type__app_label='wagtailcore', codename=codename)
                GroupPagePermission.objects.create(page=page, group=group, permission=permission)


def _sync_contact_person_groups(user):
    plans = user.get_adminable_plans()
    groups = user.groups.filter(contact_person_for_plan__isnull=False).exclude(contact_person_for_plan__in=plans)

    for group in groups:
        user.groups.remove(group)

    wagtail_perms = get_wagtail_contact_person_perms()

    for plan in plans:
        if plan.contact_person_group is None:
            continue
        group = plan.contact_person_group
        user.groups.add(group)
        if plan.root_collection is None:
            continue
        _sync_group_collection_perms(plan.root_collection, group, wagtail_perms)


def add_contact_person_perms(user, model):
    if model == Action:
        group = get_or_create_action_contact_person_group()
    else:
        group = get_or_create_indicator_contact_person_group()
    user.groups.add(group)

    # Make sure user is able to access the admin UI
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
    _sync_contact_person_groups(user)


def remove_contact_person_perms(user, model):
    if model == Action:
        group = get_or_create_action_contact_person_group()
    else:
        group = get_or_create_indicator_contact_person_group()
    user.groups.remove(group)
    _sync_contact_person_groups(user)


PLAN_ADMIN_PERMS = (
    (Plan, ('view', 'change')),
    (Action, ALL_PERMS),
    (ActionStatus, ALL_PERMS),
    (ActionSchedule, ALL_PERMS),
    (ActionImpact, ALL_PERMS),
    (AttributeType, ALL_PERMS),
    (AttributeTypeChoiceOption, ALL_PERMS),
    (AttributeChoice, ALL_PERMS),
    (AttributeRichText, ALL_PERMS),
    (CategoryType, ALL_PERMS),
    (Category, ALL_PERMS),
    (ImpactGroup, ALL_PERMS),
    (ImpactGroupAction, ALL_PERMS),
    (MonitoringQualityPoint, ALL_PERMS),

    (IndicatorLevel, ALL_PERMS),
    (ActionIndicator, ALL_PERMS),
    (Indicator, ALL_PERMS),
    (IndicatorGraph, ALL_PERMS),
    (IndicatorGoal, ALL_PERMS),
    (IndicatorValue, ALL_PERMS),
    (IndicatorContactPerson, ALL_PERMS),
    (RelatedIndicator, ALL_PERMS),
    (Unit, ALL_PERMS),
    (Quantity, ALL_PERMS),
    (Dataset, ALL_PERMS),
    (DatasetLicense, ALL_PERMS),
    (Dimension, ALL_PERMS),
    (DimensionCategory, ALL_PERMS),
    (IndicatorDimension, ALL_PERMS),
    (Organization, ALL_PERMS),

    (Person, ALL_PERMS),  # also delete perm for plan admin

    (ReportType, ALL_PERMS),
    (Report, ALL_PERMS),

    (SiteGeneralContent, ('add', 'view', 'change')),

    (BaseTemplate, ('add', 'view', 'change')),
    (AutomaticNotificationTemplate, ALL_PERMS),
    (ContentBlock, ALL_PERMS),

    (User, ('view',))
)


def get_plan_admin_perms():
    all_perms = list(get_action_contact_person_perms())
    all_perms += get_indicator_contact_person_perms()
    for model, perms in PLAN_ADMIN_PERMS:
        all_perms += _get_perm_objs(model, perms)

    all_perms += get_wagtail_plan_admin_perms()

    return all_perms


def get_or_create_plan_admin_group():
    perms = get_plan_admin_perms()
    group = _get_or_create_group('Plan admins', perms)
    return group


def _sync_plan_admin_groups(user):
    plans = user.get_adminable_plans()
    groups_to_remove = user.groups.filter(admin_for_plan__isnull=False).exclude(admin_for_plan__in=plans)
    for group in groups_to_remove:
        user.groups.remove(group)
    wagtail_perms = get_wagtail_plan_admin_perms()

    for plan in plans:
        group = plan.admin_group
        if group is None:
            continue

        user.groups.add(group)
        if plan.root_collection is not None:
            _sync_group_collection_perms(plan.root_collection, group, wagtail_perms)
        root_pages = set()
        if plan.root_page is not None:
            root_pages |= set(plan.root_page.get_translations(inclusive=True))
        root_pages |= set(plan.documentation_root_pages.all())
        _sync_group_page_perms(root_pages, group)


def remove_plan_admin_perms(user):
    group = get_or_create_plan_admin_group()
    user.groups.remove(group)


def add_plan_admin_perms(user):
    group = get_or_create_plan_admin_group()
    user.groups.add(group)

    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])

    _sync_plan_admin_groups(user)


class ActionRelatedAdminPermMixin:
    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if not isinstance(obj, Action):
            obj = None
        return request.user.can_modify_action(obj)

    def has_add_permission(self, request, obj=None):
        if not super().has_add_permission(request, obj):
            return False
        if not isinstance(obj, Action):
            obj = None
        return request.user.can_modify_action(obj)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if not isinstance(obj, Action):
            obj = None
        return request.user.can_modify_action(obj)
