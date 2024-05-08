from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.forms import ValidationError
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, ObjectList
from wagtail_modeladmin.helpers import ButtonHelper
from wagtail_modeladmin.menus import ModelAdminMenuItem
from wagtail_modeladmin.options import modeladmin_register
from wagtail_modeladmin.views import IndexView, DeleteView
from wagtailorderable.modeladmin.mixins import OrderableMixin

from aplans.utils import OrderedModelChildFormSet

from .attributes import AttributeType as AttributeTypeWrapper
from .models import Action, AttributeType, AttributeTypeChoiceOption, Category
from actions.chooser import CategoryTypeChooser
from admin_site.wagtail import (
    ActionListPageBlockFormMixin, AplansAdminModelForm, AplansCreateView, AplansEditView, AplansModelAdmin,
    AplansTabbedInterface, CondensedInlinePanel, InitializeFormWithPlanMixin, insert_model_translation_panels
)
from aplans.context_vars import ctx_instance, ctx_request


class AttributeTypeFilter(SimpleListFilter):
    title = _('Object type')
    parameter_name = 'content_type'

    def lookups(self, request, model_admin):
        action_ct_id = ContentType.objects.get(app_label='actions', model='action').id
        category_ct_id = ContentType.objects.get(app_label='actions', model='category').id
        return (
            (action_ct_id, Action._meta.verbose_name),
            (category_ct_id, Category._meta.verbose_name),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(object_content_type_id=self.value())
        return queryset


def _append_content_type_query_parameter(request, url):
    content_type = request.GET.get('content_type')
    if content_type:
        assert '?' not in url
        return f'{url}?content_type={content_type}'
    return url


class ContentTypeQueryParameterMixin:
    @property
    def index_url(self):
        return _append_content_type_query_parameter(self.request, super().index_url)

    @property
    def create_url(self):
        return _append_content_type_query_parameter(self.request, super().create_url)

    @property
    def edit_url(self):
        return _append_content_type_query_parameter(self.request, super().edit_url)

    @property
    def delete_url(self):
        return _append_content_type_query_parameter(self.request, super().delete_url)


class AttributeTypeIndexView(IndexView):
    page_title = _("Fields")


class AttributeTypeCreateView(ContentTypeQueryParameterMixin, InitializeFormWithPlanMixin, AplansCreateView):
    def get_object_content_type(self):
        object_ct_id = self.request.GET.get('content_type')
        if not object_ct_id:
            return None
        return ContentType.objects.get(pk=int(object_ct_id))

    def get_page_subtitle(self):
        content_type = self.get_object_content_type()
        model_name = content_type.model_class()._meta.verbose_name_plural
        return _("Field for %s") % model_name

    def get_instance(self):
        """Create an attribute type instance and set its object content type to the one given in GET or POST data."""
        instance = super().get_instance()
        object_ct = self.get_object_content_type()
        if object_ct is not None and not instance.pk:
            assert not hasattr(instance, 'object_content_type')
            assert not hasattr(instance, 'scope_content_type')
            instance.object_content_type = object_ct
            if (object_ct.app_label, object_ct.model) == ('actions', 'action'):
                scope_ct_model = 'plan'
            elif (object_ct.app_label, object_ct.model) == ('actions', 'category'):
                scope_ct_model = 'categorytype'
            else:
                raise Exception(f"Invalid content type {object_ct.app_label}.{object_ct.model}")
            instance.scope_content_type = ContentType.objects.get(app_label='actions', model=scope_ct_model)

        # If the instance is plan-specific, set plan to the active one just like we do in AplansCreateView for
        # PlanRelatedModel instances. AttributeType cannot be a PlanRelatedModel because not all attribute types are
        # plan-related.
        if instance.scope_content_type.model == 'plan' and not instance.pk:
            instance.scope_id = self.request.user.get_active_admin_plan().pk

        return instance


class AttributeTypeEditView(ContentTypeQueryParameterMixin, InitializeFormWithPlanMixin, AplansEditView):
    pass


class AttributeTypeDeleteView(ContentTypeQueryParameterMixin, DeleteView):
    pass


class AttributeTypeAdminButtonHelper(ButtonHelper):
    # TODO: duplicated as CategoryAdminButtonHelper
    def add_button(self, *args, **kwargs):
        """
        Only show "add" button if the request contains a content type.

        Set GET parameter content_type to the type for the URL when clicking the button.
        """
        if 'content_type' in self.request.GET:
            data = super().add_button(*args, **kwargs)
            data['url'] = _append_content_type_query_parameter(self.request, data['url'])
            return data
        return None

    def inspect_button(self, *args, **kwargs):
        data = super().inspect_button(*args, **kwargs)
        data['url'] = _append_content_type_query_parameter(self.request, data['url'])
        return data

    def edit_button(self, *args, **kwargs):
        data = super().edit_button(*args, **kwargs)
        data['url'] = _append_content_type_query_parameter(self.request, data['url'])
        return data

    def delete_button(self, *args, **kwargs):
        data = super().delete_button(*args, **kwargs)
        data['url'] = _append_content_type_query_parameter(self.request, data['url'])
        return data


class AttributeTypeAdminMenuItem(ModelAdminMenuItem):
    def is_shown(self, request):
        # Hide it because we will have menu items for listing attribute types of specific content types.
        # Note that we need to register AttributeTypeAdmin nonetheless, otherwise the URLs wouldn't be set up.
        return False


class AttributeTypeMenuItem(MenuItem):
    def __init__(self, content_type, **kwargs):
        self.content_type = content_type
        self.base_url = reverse('actions_attributetype_modeladmin_index')
        url = f'{self.base_url}?content_type={content_type.id}'
        model_name = capfirst(content_type.model_class()._meta.verbose_name)
        label = _("Fields (%(model)s)") % {'model': model_name}
        super().__init__(label, url, **kwargs)

    def is_active(self, request):
        path, _ = self.url.split('?', maxsplit=1)
        content_type = request.GET.get('content_type')
        return request.path.startswith(self.base_url) and content_type == str(self.content_type.pk)


@hooks.register('construct_settings_menu')
def add_attribute_types_to_settings_menu(request, items: list):
    user = request.user
    plan = user.get_active_admin_plan()
    if user.is_general_admin_for_plan(plan):
        action_ct = ContentType.objects.get(app_label='actions', model='action')
        category_ct = ContentType.objects.get(app_label='actions', model='category')
        items.append(AttributeTypeMenuItem(action_ct, icon_name='kausal-attribute'))
        items.append(AttributeTypeMenuItem(category_ct, icon_name='kausal-attribute'))


class AttributeTypeForm(AplansAdminModelForm):
    def __init__(self, *args, **kwargs):
        self.plan = kwargs.pop('plan')
        super().__init__(*args, **kwargs)

    def clean_attribute_category_type(self):
        attribute_category_type = self.cleaned_data['attribute_category_type']
        format = self.cleaned_data.get('format')  # avoid blowing up if None (will fail validation elsewhere)
        if format == AttributeType.AttributeFormat.CATEGORY_CHOICE and attribute_category_type is None:
            raise ValidationError(_("If format is 'Category', a category type must be set"))
        return attribute_category_type

    def clean_unit(self):
        unit = self.cleaned_data['unit']
        format = self.cleaned_data.get('format')  # avoid blowing up if None (will fail validation elsewhere)
        if format == AttributeType.AttributeFormat.NUMERIC and unit is None:
            raise ValidationError(_("If format is 'Numeric', a unit must be set"))
        return unit


class ActionAttributeTypeForm(ActionListPageBlockFormMixin, AttributeTypeForm):
    pass


class AttributeTypeEditHandler(AplansTabbedInterface):
    def get_form_options(self):
        options = super().get_form_options()
        options['formsets']['choice_options']['formset'] = OrderedModelChildFormSet
        return options


@modeladmin_register
class AttributeTypeAdmin(OrderableMixin, AplansModelAdmin):
    model = AttributeType
    menu_icon = 'kausal-attribute'
    menu_label = _("Fields")
    menu_order = 510
    list_display = ('name', 'format')
    list_filter = (AttributeTypeFilter,)

    choice_option_panels = [
        FieldPanel('name'),
    ]

    index_view_class = AttributeTypeIndexView
    create_view_class = AttributeTypeCreateView
    edit_view_class = AttributeTypeEditView
    delete_view_class = AttributeTypeDeleteView
    button_helper_class = AttributeTypeAdminButtonHelper

    # Fix index_order method added by OrderableMixinMetaClass because the way Wagtail handles icons has changed and
    # wagtailorderable hasn't accounted for this.
    def index_order(self, obj):
        return mark_safe(
            '<div class="w-orderable__item__handle button button-small button--icon handle text-replace">'
            '<svg class="icon icon-grip default" style="padding: 0px;" aria-hidden="true">'
            '<use href="#icon-grip"></use>'
            '</svg>'
            '</div>'
        )
    index_order.admin_order_field = 'order'
    index_order.short_description = _('Order')

    def get_edit_handler(self):
        request = ctx_request.get()
        instance = ctx_instance.get()
        choice_option_panels = insert_model_translation_panels(
            AttributeTypeChoiceOption, self.choice_option_panels, request, instance
        )

        creating = instance.pk is None
        if not creating and instance and AttributeTypeWrapper.from_model_instance(instance).attributes.exists():
            format_field_panel = FieldPanel(
                'format',
                read_only=True,
                help_text=_(
                    "This field already has values. If you want to change the format, you need to delete the existing "
                    "values first."
                )
            )
        else:
            format_field_panel = FieldPanel('format')

        panels = [
            FieldPanel('name'),
            FieldPanel('help_text'),
            format_field_panel,
            FieldPanel('unit'),
            FieldPanel('attribute_category_type', widget=CategoryTypeChooser),
            CondensedInlinePanel('choice_options', heading=_("Choice options"), panels=choice_option_panels),
            FieldPanel('show_choice_names'),
            FieldPanel('has_zero_option'),
            FieldPanel('max_length'),
            FieldPanel('instances_visible_for'),
            FieldPanel('instances_editable_by'),
            FieldPanel('show_in_reporting_tab'),
        ]
        panels = insert_model_translation_panels(AttributeType, panels, request, instance)
        if instance is None or instance.object_content_type_id is None:
            content_type_id = request.GET['content_type']
        else:
            content_type_id = instance.object_content_type_id
        content_type = ContentType.objects.get(pk=content_type_id)

        base_form_class = AttributeTypeForm  # For action attribute types, we use a special subclass
        if (content_type.app_label, content_type.model) == ('actions', 'action'):
            # This attribute types has scope 'plan' and we automatically set the scope in AttributeTypeCreateView, so we
            # don't add a panel for choosing a plan.
            base_form_class = ActionAttributeTypeForm
            panels.append(FieldPanel('action_list_filter_section'))
            panels.append(FieldPanel('action_detail_content_section'))
        elif (content_type.app_label, content_type.model) == ('actions', 'category'):
            panels.insert(0, FieldPanel('scope_id', widget=CategoryTypeChooser, heading=_("Category type")))
        else:
            raise Exception(f"Invalid content type {content_type.app_label}.{content_type.model}")

        tabs = [ObjectList(panels, heading=_('General'))]

        handler = AttributeTypeEditHandler(tabs, base_form_class=base_form_class)
        return handler

    def get_menu_item(self, order=None):
        return AttributeTypeAdminMenuItem(self, order or self.get_menu_order())

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        plan = user.get_active_admin_plan()
        action_ct = ContentType.objects.get(app_label='actions', model='action')
        category_ct = ContentType.objects.get(app_label='actions', model='category')
        plan_ct = ContentType.objects.get(app_label='actions', model='plan')
        category_type_ct = ContentType.objects.get(app_label='actions', model='categorytype')
        category_types_in_plan = plan.category_types.all()
        return qs.filter(
            # Attribute types for actions of the active plan
            (Q(object_content_type=action_ct) & Q(scope_content_type=plan_ct) & Q(scope_id=plan.id))
            # Attribute types for categories whose category type is the active plan
            | (Q(object_content_type=category_ct) & Q(scope_content_type=category_type_ct)
               & Q(scope_id__in=category_types_in_plan))
        )
