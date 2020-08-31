import json

from django.contrib.admin.utils import quote
from django.db.models import Q
from django.urls import re_path, reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from generic_chooser.views import ModelChooserViewSet
from generic_chooser.widgets import AdminChooser
from wagtail.admin.edit_handlers import FieldPanel, RichTextFieldPanel
from wagtail.contrib.modeladmin.helpers import PermissionHelper
from wagtail.contrib.modeladmin.options import ModelAdminGroup, modeladmin_register
from wagtail.contrib.modeladmin.views import InstanceSpecificView
from wagtail.core import hooks

from admin_site.wagtail import (
    AdminOnlyPanel, AplansButtonHelper, AplansModelAdmin, AplansTabbedInterface, CondensedInlinePanel
)

from .admin import DisconnectedIndicatorFilter
from .api import IndicatorValueSerializer
from .models import Dataset, Dimension, Indicator, Quantity


class IndicatorPermissionHelper(PermissionHelper):
    def user_can_inspect_obj(self, user, obj) -> bool:
        if not super().user_can_inspect_obj(user, obj):
            return False

        # The user has view permission to all actions if he is either
        # a general admin for actions or a contact person for any
        # actions.
        if user.is_superuser:
            return True

        adminable_plans = user.get_adminable_plans()
        obj_plans = obj.plans.all()
        for plan in adminable_plans:
            if plan in obj_plans:
                return True

        return False

    def user_can_edit_obj(self, user, obj):
        if not super().user_can_edit_obj(user, obj):
            return False

        obj_plans = obj.plans.all()
        for plan in obj_plans:
            if user.is_general_admin_for_plan(plan):
                return True

        # FIXME: Indicator contact persons
        return False

    def user_can_delete_obj(self, user, obj):
        if not super().user_can_delete_obj(user, obj):
            return False

        return self.user_can_edit_obj(user, obj)

    def user_can_create(self, user):
        if not super().user_can_create(user):
            return False

        plan = user.get_active_admin_plan()
        if user.is_general_admin_for_plan(plan):
            return True
        return False


class QuantityChooserViewSet(ModelChooserViewSet):
    icon = 'user'
    model = Quantity
    page_title = _("Choose a quantity")
    per_page = 10
    order_by = 'name'
    fields = ['name']


class QuantityChooser(AdminChooser):
    choose_one_text = _('Choose a quantity')
    choose_another_text = _('Choose another quantity')
    link_to_chosen_text = _('Edit this quantity')
    model = Quantity
    choose_modal_url_name = 'quantity_chooser:choose'


@hooks.register('register_admin_viewset')
def register_quantity_chooser_viewset():
    return QuantityChooserViewSet('quantity_chooser', url_prefix='quantity-chooser')


class EditValuesView(InstanceSpecificView):
    template_name = 'indicators/edit_values.html'

    @cached_property
    def edit_values_url(self):
        return self.url_helper.get_action_url('edit_values', self.pk_quoted)

    def check_action_permitted(self, user):
        return self.permission_helper.user_can_edit_obj(user, self.instance)

    def make_categories(self, cats):
        return [dict(id=cat.id, name=cat.name) for cat in cats]

    def get_dimensions(self, obj):
        dims = [
            d.dimension for d in obj.dimensions.select_related('dimension').prefetch_related('dimension__categories')
        ]
        for idx, dim in enumerate(dims):
            dim.order = idx
        return dims

    def get_context_data(self, **kwargs):
        obj = self.instance
        context = super().get_context_data(**kwargs)
        dims = self.get_dimensions(obj)

        dims_out = [{
            'id': dim.id,
            'name': dim.name,
            'order': dim.order,
            'categories': self.make_categories(dim.categories.all())
        } for dim in dims]
        context['dimensions'] = json.dumps(dims_out)

        value_qs = obj.values.order_by('date').prefetch_related('categories')
        data = IndicatorValueSerializer(value_qs, many=True).data

        context['values'] = json.dumps(data)
        context['post_values_uri'] = reverse('indicator-values', kwargs=dict(pk=self.pk_quoted))

        return context


class DimensionAdmin(AplansModelAdmin):
    model = Dimension
    menu_order = 4
    menu_label = _('Indicator dimensions')
    list_display = ('name',)

    panels = [
        FieldPanel('name'),
        CondensedInlinePanel('categories', panels=[FieldPanel('name')]),
    ]


class IndicatorButtonHelper(AplansButtonHelper):
    def edit_values_button(self, pk, obj, classnames_add=None, classnames_exclude=None):
        classnames_add = classnames_add or []
        return {
            'url': self.url_helper.get_action_url('edit_values', quote(pk)),
            'label': _('Edit data'),
            'classname': self.finalise_classname(
                classnames_add=classnames_add + ['icon', 'icon-table'],
                classnames_exclude=classnames_exclude
            ),
            'title': _('Edit indicator data'),
        }

    def get_buttons_for_obj(self, obj, exclude=None, classnames_add=None,
                            classnames_exclude=None):
        buttons = super().get_buttons_for_obj(obj, exclude, classnames_add, classnames_exclude)
        ph = self.permission_helper
        pk = getattr(obj, self.opts.pk.attname)
        if exclude is None:
            exclude = []
        if ('edit_values' not in exclude and obj is not None and ph.user_can_edit_obj(self.request.user, obj)):
            edit_values_button = self.edit_values_button(
                pk, obj, classnames_add=classnames_add, classnames_exclude=classnames_exclude
            )
            if edit_values_button:
                buttons.insert(1, edit_values_button)

        return buttons


class IndicatorAdmin(AplansModelAdmin):
    model = Indicator
    menu_icon = 'fa-bar-chart'
    menu_order = 3
    menu_label = _('Indicators')
    list_display = ('name', 'unit', 'quantity', 'has_data',)
    list_filter = (DisconnectedIndicatorFilter,)
    search_fields = ('name',)
    permission_helper_class = IndicatorPermissionHelper
    button_helper_class = IndicatorButtonHelper

    panels = [
        FieldPanel('name'),
        FieldPanel('quantity'),
        FieldPanel('unit'),
        FieldPanel('time_resolution'),
        RichTextFieldPanel('description'),
        FieldPanel('datasets'),
        CondensedInlinePanel('dimensions'),
    ]

    def edit_values_view(self, request, instance_pk):
        kwargs = {'model_admin': self, 'instance_pk': instance_pk}
        view_class = EditValuesView
        return view_class.as_view(**kwargs)(request)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        plan = request.user.get_active_admin_plan()
        return qs.filter(Q(plans=plan) | Q(plans__isnull=True)).distinct().select_related('unit', 'quantity')

    def get_admin_urls_for_registration(self):
        urls = super().get_admin_urls_for_registration()
        urls += (
            re_path(
                self.url_helper.get_action_url_pattern('edit_values'),
                self.edit_values_view,
                name=self.url_helper.get_action_url_name('edit_values')
            ),
        )
        return urls


class IndicatorGroup(ModelAdminGroup):
    menu_label = _('Indicators')
    menu_icon = 'fa-bar-chart'
    menu_order = 3
    items = (IndicatorAdmin, DimensionAdmin,)


modeladmin_register(IndicatorGroup)
