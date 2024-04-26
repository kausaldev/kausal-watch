import logging
import typing

from dal import autocomplete
from datetime import timedelta
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.utils import display_for_value, quote
from django.contrib.admin.widgets import AdminFileWidget
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction, models
from django.db.models import F, Q, ManyToManyField, OneToOneRel, Prefetch
from django.forms import BooleanField, ModelMultipleChoiceField, ChoiceField
from django.urls import re_path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail_modeladmin.options import modeladmin_register
from wagtail_modeladmin.helpers import ButtonHelper
from wagtail_modeladmin.views import DeleteView

from actions.models import ActionContactPerson, Plan, PlanPublicSiteViewer
from admin_site.wagtail import (
    AplansIndexView, AplansModelAdmin, AplansAdminModelForm, AplansCreateView, AplansEditView,
    InitializeFormWithPlanMixin, InitializeFormWithUserMixin, PlanContextPermissionHelper,
    ActivatePermissionHelperPlanContextMixin,
    get_translation_tabs
)
from aplans.context_vars import ctx_instance, ctx_request
from aplans.types import WatchAdminRequest
from aplans.utils import naturaltime

from .models import Person
from .views import ResetPasswordView
from orgs.models import Organization, OrganizationPlanAdmin
from actions.models import Plan

if typing.TYPE_CHECKING:
    from users.models import User


logger = logging.getLogger(__name__)


class IsContactPersonFilter(SimpleListFilter):
    title = _('Is contact person')
    parameter_name = 'contact_person'

    def lookups(self, request, model_admin):
        plan = request.user.get_active_admin_plan()
        related_plans = Plan.objects.filter(pk=plan.pk) | plan.get_all_related_plans().all()
        # If there are related plans that have action contact persons, show a filter for each of these plans
        related_plans_contact_persons = ActionContactPerson.objects.filter(action__plan__in=related_plans)
        filter_plans = related_plans.filter(pk__in=related_plans_contact_persons.values_list('action__plan'))
        if filter_plans.exists():
            action_filters = [(f'action_in_plan__{plan.pk}', _('For an action in %(plan)s') % {'plan': plan.name_i18n})
                              for plan in filter_plans]
        else:
            action_filters = [('action', _('For an action'))]
        choices = [
            *action_filters,
            ('peer_contact_persons', _('For same actions or indicators as me')),
            ('indicator', _('For an indicator')),
            ('none', _('Not a contact person')),
        ]
        return choices

    def queryset(self, request, queryset):
        user = request.user
        plan = user.get_active_admin_plan()
        queryset = queryset.prefetch_related(
            Prefetch('contact_for_actions', queryset=plan.actions.all(), to_attr='plan_contact_for_actions')
        )
        queryset = queryset.prefetch_related(
            Prefetch('contact_for_indicators', queryset=plan.indicators.all(), to_attr='plan_contact_for_indicators')
        )
        if self.value() is None:
            return queryset
        if self.value() == 'action':
            queryset = queryset.filter(contact_for_actions__in=plan.actions.all())
        elif self.value().startswith('action_in_plan__'):
            plan_pk = int(self.value()[16:])
            queryset = queryset.filter(contact_for_actions__plan=plan_pk)
        elif self.value() == 'indicator':
            queryset = queryset.filter(contact_for_indicators__in=plan.indicators.all())
        elif self.value() == 'peer_contact_persons':
            person = user.person
            my_actions = plan.actions.filter(contact_persons__person=person)
            my_indicators = plan.indicators.filter(contact_persons__person=person)
            queryset = queryset.filter(
                Q(contact_for_actions__pk__in=my_actions) |
                Q(contact_for_indicators__pk__in=my_indicators)
            )
        else:
            queryset = queryset.exclude(contact_for_actions__in=plan.actions.all())\
                .exclude(contact_for_indicators__in=plan.indicators.all())
        return queryset.distinct()


def smart_truncate(content, length=100, suffix='...'):
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix


class AvatarWidget(AdminFileWidget):
    template_name = 'people/avatar_widget.html'


class PersonForm(AplansAdminModelForm):
    def __init__(self, *args, **kwargs):
        self.plan = kwargs.pop('plan')
        self.user = kwargs.pop('user')
        instance = kwargs['instance']  # should be a model instance (perhaps with pk None) due to ModelFormView
        initial = kwargs.setdefault('initial', {})
        if instance.pk is None:
            initial.setdefault('organization', self.plan.organization)
        else:
            initial['is_admin_for_active_plan'] = self.plan in instance.general_admin_plans.all()
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.instance.created_by = self.user

    def save(self, commit=True):
        if 'image' in self.files:
            self.instance.image_cropping = None
        return super().save(commit)

class PersonFormForGeneralAdmin(PersonForm):
    class AccessLevel(models.TextChoices):
        PUBLIC_SITE_ONLY = "public_site_only", _('Access to public site only')
        FULL_ACCESS = "full_access", _('Access to admin site and public site')

    is_admin_for_active_plan = BooleanField(required=False, label=_('Is plan admin'))
    access_level = ChoiceField(choices=AccessLevel.choices, required=True, label=_('Site access'))
    organization_plan_admin_orgs = ModelMultipleChoiceField(
        queryset=None, required=False, widget=autocomplete.ModelSelect2Multiple(url='organization-autocomplete'),
        label=_('Plan admin organizations'),
    )

    def __init__(self, *args, **kwargs):
        plan = kwargs['plan']
        instance = kwargs['instance']  # should be a model instance (perhaps with pk None) due to ModelFormView
        initial = kwargs.setdefault('initial', {})
        initial['access_level'] = self.AccessLevel.FULL_ACCESS
        if instance.pk is not None:
            initial['organization_plan_admin_orgs'] = (
                instance.organization_plan_admins.filter(plan=plan).values_list('organization', flat=True)
            )
            is_public_site_viewer = instance.plans_with_public_site_access.filter(plan=plan).exists()
            initial['access_level'] = self.AccessLevel.PUBLIC_SITE_ONLY if is_public_site_viewer else self.AccessLevel.FULL_ACCESS

        super().__init__(*args, **kwargs)
        assert self.user.is_general_admin_for_plan(self.plan)
        if plan.features.allow_public_site_login:
            if initial.get('access_level') == self.AccessLevel.PUBLIC_SITE_ONLY:
                del self.fields['organization_plan_admin_orgs']
                del self.fields['is_admin_for_active_plan']
                del self.fields['contact_for_actions_unordered']
                del self.fields['participated_in_training']
        else:
            # Allow removing lingering public site restriction if public site login was recently removed
            if initial.get('access_level') != self.AccessLevel.PUBLIC_SITE_ONLY:
                del self.fields['access_level']
        if 'organization_plan_admin_orgs' in self.fields:
            self.fields['organization_plan_admin_orgs'].queryset = (
                Organization.objects.available_for_plan(self.plan).filter(dissolution_date=None)
            )

    def clean(self):
        cleaned_data = super().clean()
        access_level = cleaned_data.get('access_level')
        is_plan_admin = cleaned_data.get('is_admin_for_active_plan')
        organization_plan_admin_orgs = cleaned_data.get('organization_plan_admin_orgs')
        contact_for_actions = cleaned_data.get('contact_for_actions_unordered')
        if access_level == self.AccessLevel.PUBLIC_SITE_ONLY:
            if is_plan_admin or organization_plan_admin_orgs or contact_for_actions:
                raise ValidationError(
                    'Person cannot have admin responsibilities while also being restricted to only public site access.'
                )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit)
        is_admin_for_active_plan = self.cleaned_data.get('is_admin_for_active_plan')
        access_level = self.cleaned_data.get('access_level')
        if access_level == self.AccessLevel.PUBLIC_SITE_ONLY:
            PlanPublicSiteViewer.objects.get_or_create(plan=self.plan, person=instance)
        elif access_level == self.AccessLevel.FULL_ACCESS:
            PlanPublicSiteViewer.objects.filter(plan=self.plan, person=instance).delete()
        if is_admin_for_active_plan is True:
            instance.general_admin_plans.add(self.plan)
        elif is_admin_for_active_plan is False:
            instance.general_admin_plans.remove(self.plan)

        organization_plan_admin_orgs = self.cleaned_data.get('organization_plan_admin_orgs')
        if organization_plan_admin_orgs is not None:
            with transaction.atomic():
                OrganizationPlanAdmin.objects.filter(plan=self.plan, person=instance).delete()
                for org in organization_plan_admin_orgs:
                    OrganizationPlanAdmin.objects.create(organization=org, plan=self.plan, person=instance)
        return instance


class PersonCreateView(
        ActivatePermissionHelperPlanContextMixin, InitializeFormWithPlanMixin, InitializeFormWithUserMixin, AplansCreateView
):
    def form_valid(self, form, *args, **kwargs):
        # Make sure form only contains is_admin_for_active_plan
        # TODO: Also do this for organization_plan_admin_orgs?
        plan = self.request.user.get_active_admin_plan()
        is_general_admin = self.request.user.is_general_admin_for_plan(plan)
        contains_admin_flag = form.cleaned_data.get('is_admin_for_active_plan') is not None

        def iff(a, b):
            return (a and b) or (not a and not b)

        assert iff(contains_admin_flag, is_general_admin)
        return super().form_valid(form, *args, **kwargs)


class PersonEditView(InitializeFormWithPlanMixin, InitializeFormWithUserMixin, AplansEditView):
    pass


class PersonIndexView(AplansIndexView):
    def get_ordering(self, request, queryset):
        ret = super().get_ordering(request, queryset)
        out = []
        for order in ret:
            field = order
            if order[0] == '-':
                field = field[1:]
                desc = True
            else:
                desc = False
            if field != 'user__last_login':
                out.append(order)
                continue
            order = F('user__last_login')
            if desc:
                order = order.desc(nulls_last=True)
            else:
                order = order.asc(nulls_first=True)
            out.append(order)
        return out


class PersonPermissionHelper(PlanContextPermissionHelper):
    _org_map: dict[int, Organization] | None

    def __init__(self, model, inspect_view_enabled=False):
        self._org_map = None
        super().__init__(model, inspect_view_enabled)

    def prefetch_cache(self):
        if self.plan is None:
            return
        org_qs = Organization.objects.available_for_plan(self.plan)
        self._org_map = {org.id: org for org in org_qs}

    def clean_cache(self):
        self._org_map = None

    def user_can_edit_obj(self, user: 'User', obj: Person):
        if not super().user_can_edit_obj(user, obj):
            return False
        # Users can always edit themselves
        if obj.user == user:
            return True
        return user.can_edit_or_delete_person_within_plan(
            obj, plan=self.plan, orgs=self._org_map
        )

    def user_can_delete_obj(self, user, obj: Person):
        if not super().user_can_delete_obj(user, obj):
            return False
        return user.can_edit_or_delete_person_within_plan(
            obj, plan=self.plan, orgs=self._org_map
        )

    def user_can_create(self, user: 'User'):
        if user.is_general_admin_for_plan(self.plan):
            return True
        person = user.get_corresponding_person()
        # FIXME: there is some hardcoding of assumptions about contact person roles here.  These should be moved to a role-based system.
        if not ActionContactPerson.objects\
                                  .filter(action__plan=self.plan).filter(person=person).exclude(role=ActionContactPerson.Role.EDITOR):
            # Only persons with role other than editor can add persons
            return False
        return super().user_can_create(user)

class PersonButtonHelper(ButtonHelper):
    def delete_button(self, *args, **kwargs):
        button = super().delete_button(*args, **kwargs)
        button['label'] = _('Deactivate')
        return button

    def reset_password_button(self, pk, **kwargs):
        """Button for sending password reset emails and displaying reset tokens."""
        return {
            'label': _("Reset password"),
            'title': _("Create a password reset link"),
            'url': self.url_helper.get_action_url('reset_password', quote(pk)),
            'classname': self.finalise_classname(['button-secondary', 'button-small']),
        }

    def get_buttons_for_obj(self, obj, *args, **kwargs):
        buttons = super().get_buttons_for_obj(obj, *args, **kwargs)
        user = self.request.user
        plan = user.get_active_admin_plan()
        assert isinstance(obj, Person)
        # Only display a password reset button if the user has a usable password. This prevents showing the button for
        # users from a customer that uses SSO because such users normally don't have a usable password.
        target_has_password = obj.user and obj.user.has_usable_password()
        target_is_admin_of_any_plan = obj.user and obj.user.is_general_admin_for_plan()
        # TODO: Should be harmonized with ResetPasswordView.check_action_permitted()
        if user.is_general_admin_for_plan(plan) and target_has_password and not target_is_admin_of_any_plan:
            reset_password_button = self.reset_password_button(
                pk=getattr(obj, self.opts.pk.attname),
                **kwargs
            )
            buttons.append(reset_password_button)

        return buttons


class PersonDeleteView(ActivatePermissionHelperPlanContextMixin, DeleteView):
    instance: Person
    model: typing.Type[Person]

    def get(self, request, *args, **kwargs):
        linked_objects = []
        fields = self.model._meta.fields_map.values()
        fields = (obj for obj in fields if not isinstance(
            obj.field, ManyToManyField))
        for rel in fields:
            obj = None
            if isinstance(rel, OneToOneRel):
                key = rel.get_accessor_name()
                try:
                    if key:
                        obj = getattr(self.instance, key)
                except ObjectDoesNotExist:
                    pass
                else:
                    if obj:
                        linked_objects.append(obj)
            else:
                key = rel.get_accessor_name()
                if key:
                    qs = getattr(self.instance, key)
                    for obj in qs.all():
                        linked_objects.append(obj)
        context = self.get_context_data(
            protected_error=True,
            linked_objects=linked_objects
        )
        return self.render_to_response(context)

    def confirmation_message(self):
        return _('Are you sure you want to deactivate this person?')

    def delete_instance(self):
        # FIXME: Duplicated in actions.api.PersonViewSet.perform_destroy()
        acting_admin_user = self.request.user
        self.instance.delete_and_deactivate_corresponding_user(acting_admin_user)


class PersonAdmin(AplansModelAdmin):
    model = Person
    create_view_class = PersonCreateView
    edit_view_class = PersonEditView
    index_view_class = PersonIndexView
    delete_view_class = PersonDeleteView
    delete_template_name = "people/delete.html"
    permission_helper_class = PersonPermissionHelper
    menu_icon = 'user'
    menu_label = _('People')
    menu_order = 210
    exclude_from_explorer = False
    search_fields = ('first_name', 'last_name', 'title', 'organization__name', 'organization__abbreviation')
    list_filter = (IsContactPersonFilter,)
    button_helper_class = PersonButtonHelper
    index_view_extra_css = ['css/modeladmin-index.css']
    permission_helper: PersonPermissionHelper

    def get_permission_helper_class(self):
        return super().get_permission_helper_class()

    def get_queryset(self, request: WatchAdminRequest):
        plan = request.user.get_active_admin_plan()
        qs = super().get_queryset(request).available_for_plan(plan).select_related('user')
        return qs

    def get_empty_value_display(self, field=None):
        if getattr(field, '_name', field) == 'last_logged_in':
            return display_for_value(False, None, boolean=True)
        return super().get_empty_value_display(field)

    def get_list_display(self, request: WatchAdminRequest):
        # get_list_display() gets called a lot, so we cache the results
        if hasattr(request, '_person_list_display'):
            return request._person_list_display

        plan = request.get_active_admin_plan()

        # We use a cached and path-indexed version of all organizations to reduce
        # SQL queries.
        all_orgs = list(Organization.objects.available_for_plan(plan))
        orgs_by_path = Organization.make_orgs_by_path(all_orgs)
        orgs_by_id = {org.id: org for org in all_orgs}

        def edit_url(obj):
            if self.permission_helper.user_can_edit_obj(request.user, obj):
                return self.url_helper.get_action_url('edit', obj.pk)
            else:
                return None

        def avatar(obj):
            avatar_url = obj.get_avatar_url(request, size='50x50')
            if not avatar_url:
                return ''
            img = format_html('<span class="avatar"><img src="{}" /></span>', avatar_url)
            url = edit_url(obj)
            if url:
                return format_html('<a href="{}">{}</a>', url, img)
            else:
                return img
        avatar.short_description = ''

        def cannot_access_admin_warning(obj):
            if obj.user and not obj.user.can_access_admin():
                tooltip = _(
                    "This person has no access to the admin interface. This is commonly because no actions or "
                    "indicators are assigned to them."
                )
                return format_html(
                    '<div class="tooltip-wrapper">'
                    f'<div aria-describedby="access-warning-tooltip-{obj.id}">'
                    '<svg class="icon icon-warning" style="height: 1.5em; width: 1.5em;" aria-hidden="true">'
                    '<use href="#icon-warning"></use>'
                    '</svg>'
                    '</div>'
                    f'<div id="access-warning-tooltip-{obj.id}" role="tooltip">'
                    '{}'
                    '</div>'
                    '</div>',
                    tooltip
                )
            return ''
        cannot_access_admin_warning.short_description = ''

        def first_name(obj):
            url = edit_url(obj)
            if url:
                return format_html('<a href="{}">{}</a>', url, obj.first_name)
            else:
                return obj.first_name
        first_name.short_description = _('first name')
        first_name.admin_order_field = 'first_name'

        def last_name(obj):
            url = edit_url(obj)
            if url:
                return format_html('<a href="{}">{}</a>', url, obj.last_name)
            else:
                return obj.last_name
        last_name.short_description = _('last name')
        last_name.admin_order_field = 'last_name'

        def organization(obj: Person) -> str:
            org_id = obj.organization_id
            if org_id in orgs_by_id:
                org = orgs_by_id[org_id]
            else:
                org = obj.organization
            return org.get_fully_qualified_name(orgs_by_path=orgs_by_path)
        organization.short_description = _('organization')
        organization.admin_order_field = 'organization__name'

        fields = [avatar, cannot_access_admin_warning, first_name, last_name, 'title', organization]

        def last_logged_in(obj):
            user = obj.user
            if not user or not user.last_login:
                return None
            now = timezone.now()
            delta = now - user.last_login
            if delta > timedelta(days=30):
                return user.last_login.date()
            return naturaltime(delta)
        last_logged_in.short_description = _('last login')
        last_logged_in.admin_order_field = 'user__last_login'
        last_logged_in._name = 'last_logged_in'

        user = request.user
        if user.is_general_admin_for_plan(plan):
            plan_admins = set(plan.general_admins.values_list('id', flat=True))

            def is_plan_admin(obj: Person):
                return obj.id in plan_admins
            is_plan_admin.short_description = _('Is plan admin')
            is_plan_admin._name = 'is_plan_admin'
            is_plan_admin.boolean = True
            fields.append(is_plan_admin)

            fields.append(last_logged_in)
            fields.append('participated_in_training')

        def contact_for_actions(obj):
            return '; '.join([smart_truncate(str(act), 40) for act in obj.plan_contact_for_actions])
        contact_for_actions.short_description = _('contact for actions')

        def contact_for_indicators(obj):
            return '; '.join([smart_truncate(str(ind), 40) for ind in obj.plan_contact_for_indicators])
        contact_for_indicators.short_description = _('contact for indicators')

        contact_person_filter = request.GET.get('contact_person', '')
        if contact_person_filter == 'action':
            fields.append(contact_for_actions)
        elif contact_person_filter == 'indicator':
            fields.append(contact_for_indicators)

        request._person_list_display = fields
        return fields

    basic_panels = [
        FieldPanel('first_name'),
        FieldPanel('last_name'),
        FieldPanel('email'),
        FieldPanel('title'),
        FieldPanel(
            'organization',
            widget=autocomplete.ModelSelect2(url='organization-autocomplete'),
        ),
        FieldPanel('image', widget=AvatarWidget),
    ]

    def get_edit_handler(self):
        request = ctx_request.get()
        instance = ctx_instance.get()
        basic_panels = list(self.basic_panels)
        user = request.user
        plan = user.get_active_admin_plan()
        if user.is_general_admin_for_plan(plan):
            form_class = PersonFormForGeneralAdmin
            basic_panels.append(FieldPanel('access_level'))
            basic_panels.append(FieldPanel('participated_in_training'))
            basic_panels.append(FieldPanel('is_admin_for_active_plan'))
            basic_panels.append(FieldPanel(
                'organization_plan_admin_orgs',
                widget=autocomplete.ModelSelect2Multiple(url='organization-autocomplete'),
            ))
            # FIXME: This saves ActionContactPerson instances without specifying `order`, which leads to duplicates of
            # the default value.
            # TODO: No way to specify `primary_contact`.
            # Recall that we tried using inline panels (changing the other ForeignKey in the model to a ParentalKey and
            # adding some workarounds) for `actioncontactperson_set`, but came across the problem that it screws up the
            # ordering because the order as displayed in the person admin view is not what we want -- the order we want
            # should rather be the one as specified in the action edit view.
            basic_panels.append(FieldPanel(
                'contact_for_actions_unordered',
                widget=autocomplete.ModelSelect2Multiple(url='action-autocomplete'),
            ))
        else:
            form_class = PersonForm

        tabs = [ObjectList(basic_panels, heading=_('General'))]

        i18n_tabs = get_translation_tabs(instance, request)
        tabs += i18n_tabs

        return TabbedInterface(tabs, base_form_class=form_class)

    def get_extra_attrs_for_row(self, obj, context):
        assert isinstance(obj, Person)
        if obj.user and not obj.user.can_access_admin():
            # Add CSS class to highlight rows of users without admin access
            return {
                'class': 'user-without-admin-access',
            }
        return {}

    def reset_password_view(self, request, instance_pk):
        """Generate a class-based view to provide 'reset password' functionality."""
        return ResetPasswordView.as_view(model_admin=self, target_person_pk=instance_pk)(request)

    def get_admin_urls_for_registration(self):
        """Add the new url for reset password page to the registered URLs."""
        urls = super().get_admin_urls_for_registration()
        reset_password_url = re_path(
            self.url_helper.get_action_url_pattern('reset_password'),
            self.reset_password_view,
            name=self.url_helper.get_action_url_name('reset_password')
        )
        return urls + (
            reset_password_url,
        )


modeladmin_register(PersonAdmin)
