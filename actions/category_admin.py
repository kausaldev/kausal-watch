from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.edit_handlers import (
    FieldPanel, FieldRowPanel, MultiFieldPanel, ObjectList,
)
from wagtail.admin.edit_handlers import InlinePanel
from wagtail.admin.forms.models import WagtailAdminModelForm
from wagtail.contrib.modeladmin.helpers import ButtonHelper, PermissionHelper
from wagtail.contrib.modeladmin.menus import ModelAdminMenuItem
from wagtail.contrib.modeladmin.options import modeladmin_register
from wagtail.contrib.modeladmin.views import DeleteView
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtailorderable.modeladmin.mixins import OrderableMixin
from wagtailsvg.edit_handlers import SvgChooserPanel

from .admin import CategoryTypeFilter, CommonCategoryTypeFilter
from .attribute_type_admin import get_attribute_fields
from .models import AttributeType, Category, CategoryType, CommonCategory, CommonCategoryType
from admin_site.wagtail import (
    AplansCreateView, AplansEditView, AplansModelAdmin, CondensedInlinePanel, PlanFilteredFieldPanel,
    AplansTabbedInterface, get_translation_tabs
)


def _append_query_parameter(request, url, parameter):
    value = request.GET.get(parameter)
    if value:
        assert '?' not in url
        return f'{url}?{parameter}={value}'
    return url


class CategoryTypeDeleteView(DeleteView):
    def delete_instance(self):
        # When deleting a category type which is an instantiation of a common category type, remove link from plan
        plan = self.instance.plan
        cct = self.instance.common
        plan.common_category_types.remove(cct)
        return super().delete_instance()


@modeladmin_register
class CategoryTypeAdmin(AplansModelAdmin):
    model = CategoryType
    menu_icon = 'fa-briefcase'
    menu_label = _('Category types')
    menu_order = 1100
    list_display = ('name',)
    search_fields = ('name',)
    add_to_settings_menu = True
    delete_view_class = CategoryTypeDeleteView

    panels = [
        FieldPanel('name'),
        FieldPanel('identifier'),
        FieldPanel('lead_paragraph'),
        FieldPanel('help_text'),
        FieldPanel('hide_category_identifiers'),
        FieldPanel('select_widget'),
        MultiFieldPanel([
            FieldRowPanel([
                FieldPanel('usable_for_actions'),
                FieldPanel('editable_for_actions'),
            ]),
            FieldRowPanel([
                FieldPanel('usable_for_indicators'),
                FieldPanel('editable_for_indicators'),
            ]),
        ], heading=_('Action and indicator categorization'), classname='collapsible'),
        CondensedInlinePanel('levels', panels=[
            FieldPanel('name',),
            FieldPanel('name_plural',)
        ]),
        FieldPanel('synchronize_with_pages'),
    ]

    def get_form_fields_exclude(self, request):
        exclude = super().get_form_fields_exclude(request)
        exclude += ['plan']
        return exclude

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        plan = user.get_active_admin_plan()
        return qs.filter(plan=plan)

    def get_edit_handler(self, instance, request):
        panels = list(self.panels)
        if instance and instance.common:
            panels.insert(1, FieldPanel('common'))
        tabs = [ObjectList(panels, heading=_('Basic information'))]

        i18n_tabs = get_translation_tabs(instance, request)
        tabs += i18n_tabs

        return CategoryTypeEditHandler(tabs)


def get_category_attribute_fields(category_type, category, **kwargs):
    category_ct = ContentType.objects.get_for_model(Category)
    category_type_ct = ContentType.objects.get_for_model(category_type)
    attribute_types = AttributeType.objects.filter(
        object_content_type=category_ct,
        scope_content_type=category_type_ct,
        scope_id=category_type.id,
    )
    return get_attribute_fields(attribute_types, category, **kwargs)


class AttributeFieldPanel(FieldPanel):
    def on_form_bound(self):
        super().on_form_bound()
        attribute_fields_list = get_category_attribute_fields(self.instance.type, self.instance, with_initial=True)
        attribute_fields = {form_field_name: field
                            for _, fields in attribute_fields_list
                            for form_field_name, (field, _) in fields.items()}
        self.form.fields[self.field_name].initial = attribute_fields[self.field_name].initial


class CategoryAdminForm(WagtailAdminModelForm):
    def clean_identifier(self):
        # Since we hide the category type in the form, `validate_unique()` will be called with `exclude` containing
        # `type`, in which case the unique_together constraints of Category will not be checked. We do it manually here.
        # Similarly, the unique_together containing `external_identifier` will not be checked, but `external_identifier`
        # is not part of the form, so no need to check.
        identifier = self.cleaned_data['identifier']
        type = self.instance.type
        if Category.objects.filter(type=type, identifier=identifier).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("There is already a category with this identifier."))
        return identifier

    def save(self, commit=True):
        obj = super().save(commit)

        # Update categories
        # TODO: Refactor duplicated code (action_admin.py)
        for attribute_type, fields in get_category_attribute_fields(obj.type, obj):
            vals = {}
            for form_field_name, (field, model_field_name) in fields.items():
                val = self.cleaned_data.get(form_field_name)
                vals[model_field_name] = val
            attribute_type.set_value(obj, vals)
        return obj


class CategoryEditHandler(AplansTabbedInterface):
    def get_form_class(self, request=None, instance: Category | None = None):
        # TODO: Refactor duplicated code (action_admin.py)
        if instance is not None:
            attribute_fields_list = get_category_attribute_fields(instance.type, instance, with_initial=True)
            attribute_fields = {form_field_name: field
                                for _, fields in attribute_fields_list
                                for form_field_name, (field, _) in fields.items()}
        else:
            attribute_fields = {}

        self.base_form_class = type(
            'CategoryAdminForm',
            (CategoryAdminForm,),
            attribute_fields
        )
        form_class = super().get_form_class()
        if instance and instance.common:
            if 'identifier' in form_class.base_fields:
                form_class.base_fields['identifier'].disabled = True
                form_class.base_fields['identifier'].required = False
            if 'parent' in form_class.base_fields:
                # TODO: Hide "parent" field instead of disabling?
                form_class.base_fields['parent'].disabled = True
                form_class.base_fields['parent'].required = False
        return form_class


class CategoryTypeEditHandler(AplansTabbedInterface):
    def get_form_class(self, request=None):
        form_class = super().get_form_class()
        common_field = form_class.base_fields.get('common')
        # The field should be displayed if and only if editing an instance that has a common category type. If it is,
        # make it read-only.
        if common_field:
            common_field.disabled = True
            common_field.required = False
        return form_class


class CategoryTypeQueryParameterMixin:
    @property
    def index_url(self):
        return _append_query_parameter(self.request, super().index_url, 'category_type')

    @property
    def create_url(self):
        return _append_query_parameter(self.request, super().create_url, 'category_type')

    @property
    def edit_url(self):
        return _append_query_parameter(self.request, super().edit_url, 'category_type')

    @property
    def delete_url(self):
        return _append_query_parameter(self.request, super().delete_url, 'category_type')


class CategoryCreateView(CategoryTypeQueryParameterMixin, AplansCreateView):
    def get_instance(self):
        """Create a category instance and set its category type to the one given in the GET or POST data."""
        instance = super().get_instance()
        category_type = self.request.GET.get('category_type')
        if category_type and not instance.pk:
            assert not hasattr(instance, 'type')
            instance.type = CategoryType.objects.get(pk=int(category_type))
            if not instance.identifier and instance.type.hide_category_identifiers:
                instance.generate_identifier()
        return instance


class CategoryEditView(CategoryTypeQueryParameterMixin, AplansEditView):
    pass


class CategoryDeleteView(CategoryTypeQueryParameterMixin, DeleteView):
    pass


class CategoryAdminButtonHelper(ButtonHelper):
    # TODO: duplicated as AttributeTypeAdminButtonHelper
    def add_button(self, *args, **kwargs):
        """
        Only show "add" button if the request contains a category type.

        Set GET parameter category_type to the type for the URL when clicking the button.
        """
        if 'category_type' in self.request.GET:
            data = super().add_button(*args, **kwargs)
            data['url'] = _append_query_parameter(self.request, data['url'], 'category_type')
            return data
        return None

    def inspect_button(self, *args, **kwargs):
        data = super().inspect_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'category_type')
        return data

    def edit_button(self, *args, **kwargs):
        data = super().edit_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'category_type')
        return data

    def delete_button(self, *args, **kwargs):
        data = super().delete_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'category_type')
        return data


class CategoryOfSameTypePanel(PlanFilteredFieldPanel):
    """Only show categories of the same category type as the current category instance."""

    def on_form_bound(self):
        super().on_form_bound()
        field = self.bound_field.field
        field.queryset = field.queryset.filter(type=self.instance.type)


class CategoryAdminMenuItem(ModelAdminMenuItem):
    def is_shown(self, request):
        # Hide it because we will have menu items for listing categories of specific types.
        # Note that we need to register CategoryAdmin nonetheless, otherwise the URLs wouldn't be set up.
        return False


@modeladmin_register
class CategoryAdmin(OrderableMixin, AplansModelAdmin):
    menu_label = _('Categories')
    list_display = ('__str__', 'parent', 'type')
    list_filter = (CategoryTypeFilter,)
    model = Category
    add_to_settings_menu = True

    panels = [
        CategoryOfSameTypePanel('parent'),
        FieldPanel('name'),
        FieldPanel('identifier'),
        FieldPanel('lead_paragraph'),
        ImageChooserPanel('image'),
        FieldPanel('color'),
        FieldPanel('help_text'),
    ]

    create_view_class = CategoryCreateView
    edit_view_class = CategoryEditView
    # Do we need to create a view for inspect_view?
    delete_view_class = CategoryDeleteView
    button_helper_class = CategoryAdminButtonHelper

    def get_menu_item(self, order=None):
        return CategoryAdminMenuItem(self, order or self.get_menu_order())

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        plan = user.get_active_admin_plan()
        return qs.filter(type__plan=plan).distinct()

    def get_edit_handler(self, instance, request):
        panels = list(self.panels)
        # If the category type doesn't have semantic identifiers, we
        # hide the whole panel.
        if instance.type.hide_category_identifiers:
            for p in panels:
                if p.field_name == 'identifier':
                    panels.remove(p)
                    break

        # TODO: Refactor duplicated code (action_admin.py)
        if instance:
            attribute_fields = get_category_attribute_fields(instance.type, instance, with_initial=True)
        else:
            attribute_fields = []

        for attribute_type, fields in attribute_fields:
            for form_field_name, (field, model_field_name) in fields.items():
                if len(fields) > 1:
                    heading = f'{attribute_type.name} ({model_field_name})'
                else:
                    heading = attribute_type.name
                panels.append(AttributeFieldPanel(form_field_name, heading=heading))

        if request.user.is_superuser:
            # Didn't use CondensedInlinePanel for the following because there is a bug:
            # When editing a CommonCategory that already has an icon, clicking "save" will yield a validation error if
            # and only if the inline instance is collapsed.
            panels.append(InlinePanel('icons', heading=_("Icons"), panels=[
                FieldPanel('language'),
                ImageChooserPanel('image'),
                SvgChooserPanel('svg'),
            ]))

        tabs = [ObjectList(panels, heading=_('Basic information'))]

        i18n_tabs = get_translation_tabs(instance, request)
        tabs += i18n_tabs

        return CategoryEditHandler(tabs)


class CommonCategoryTypePermissionHelper(PermissionHelper):
    def user_can_list(self, user):
        return user.is_superuser

    def user_can_create(self, user):
        return user.is_superuser

    # def user_can_inspect_obj(self, user, obj):
    #     return user.is_superuser

    def user_can_delete_obj(self, user, obj):
        return user.is_superuser

    def user_can_edit_obj(self, user, obj):
        return user.is_superuser


@modeladmin_register
class CommonCategoryTypeAdmin(AplansModelAdmin):
    model = CommonCategoryType
    menu_icon = 'fa-briefcase'
    menu_label = _('Common category types')
    menu_order = 1101
    permission_helper_class = CommonCategoryTypePermissionHelper
    list_display = ('name',)
    search_fields = ('name',)
    add_to_settings_menu = True

    panels = [
        FieldPanel('name'),
        FieldPanel('identifier'),
        FieldPanel('hide_category_identifiers'),
        FieldPanel('lead_paragraph'),
        FieldPanel('help_text'),
        FieldPanel('primary_language'),
        FieldPanel('select_widget'),
        FieldPanel('has_collection'),
        MultiFieldPanel([
            FieldRowPanel([
                FieldPanel('usable_for_actions'),
                FieldPanel('editable_for_actions'),
            ]),
            FieldRowPanel([
                FieldPanel('usable_for_indicators'),
                FieldPanel('editable_for_indicators'),
            ]),
        ], heading=_('Action and indicator categorization'), classname='collapsible'),
    ]

    def get_edit_handler(self, instance, request):
        panels = list(self.panels)
        tabs = [ObjectList(panels, heading=_('Basic information'))]

        i18n_tabs = get_translation_tabs(instance, request)
        tabs += i18n_tabs

        return AplansTabbedInterface(tabs)


class CommonCategoryTypeQueryParameterMixin:
    @property
    def index_url(self):
        return _append_query_parameter(self.request, super().index_url, 'common_category_type')

    @property
    def create_url(self):
        return _append_query_parameter(self.request, super().create_url, 'common_category_type')

    @property
    def edit_url(self):
        return _append_query_parameter(self.request, super().edit_url, 'common_category_type')

    @property
    def delete_url(self):
        return _append_query_parameter(self.request, super().delete_url, 'common_category_type')


class CommonCategoryCreateView(CommonCategoryTypeQueryParameterMixin, AplansCreateView):
    def get_instance(self):
        """Create a common category instance and set its type to the one given in the GET or POST data."""
        instance = super().get_instance()
        common_category_type = self.request.GET.get('common_category_type')
        if common_category_type and not instance.pk:
            assert not hasattr(instance, 'type')
            instance.type = CommonCategoryType.objects.get(pk=int(common_category_type))
            # if not instance.identifier and instance.type.hide_category_identifiers:
            #     instance.generate_identifier()
        return instance


class CommonCategoryEditView(CommonCategoryTypeQueryParameterMixin, AplansEditView):
    pass


class CommonCategoryDeleteView(CommonCategoryTypeQueryParameterMixin, DeleteView):
    pass


class CommonCategoryAdminButtonHelper(ButtonHelper):
    def add_button(self, *args, **kwargs):
        """
        Only show "add" button if the request contains a common category type.

        Set GET parameter common_category_type to the type for the URL when clicking the button.
        """
        if 'common_category_type' in self.request.GET:
            data = super().add_button(*args, **kwargs)
            data['url'] = _append_query_parameter(self.request, data['url'], 'common_category_type')
            return data
        return None

    def inspect_button(self, *args, **kwargs):
        data = super().inspect_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'common_category_type')
        return data

    def edit_button(self, *args, **kwargs):
        data = super().edit_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'common_category_type')
        return data

    def delete_button(self, *args, **kwargs):
        data = super().delete_button(*args, **kwargs)
        data['url'] = _append_query_parameter(self.request, data['url'], 'common_category_type')
        return data


class CommonCategoryAdminMenuItem(ModelAdminMenuItem):
    def is_shown(self, request):
        # Hide it because we will have menu items for listing common categories of specific types.
        # Note that we need to register CommonCategoryAdmin nonetheless, otherwise the URLs wouldn't be set up.
        return False


class CommonCategoryEditHandler(AplansTabbedInterface):
    def get_form_class(self, request=None, instance: CommonCategory | None = None):
        form_class = super().get_form_class()
        if instance and instance.pk:
            form_class.base_fields['identifier'].disabled = True
            form_class.base_fields['identifier'].required = False
        return form_class


@modeladmin_register
class CommonCategoryAdmin(OrderableMixin, AplansModelAdmin):
    menu_label = _('Common categories')
    list_display = ('name', 'identifier', 'type')
    list_filter = (CommonCategoryTypeFilter,)
    model = CommonCategory
    add_to_settings_menu = True

    panels = [
        FieldPanel('name'),
        FieldPanel('identifier'),
        FieldPanel('lead_paragraph'),
        ImageChooserPanel('image'),
        FieldPanel('color'),
        FieldPanel('help_text'),
    ]

    create_view_class = CommonCategoryCreateView
    edit_view_class = CommonCategoryEditView
    # Do we need to create a view for inspect_view?
    delete_view_class = CommonCategoryDeleteView
    button_helper_class = CommonCategoryAdminButtonHelper

    def get_menu_item(self, order=None):
        return CommonCategoryAdminMenuItem(self, order or self.get_menu_order())

    def get_edit_handler(self, instance, request):
        panels = list(self.panels)

        if request.user.is_superuser:
            # Didn't use CondensedInlinePanel for the following because there is a bug:
            # When editing a CommonCategory that already has an icon, clicking "save" will yield a validation error if
            # and only if the inline instance is collapsed.
            panels.append(InlinePanel('icons', heading=_("Icons"), panels=[
                FieldPanel('language'),
                ImageChooserPanel('image'),
                SvgChooserPanel('svg'),
            ]))

        tabs = [ObjectList(panels, heading=_('Basic information'))]

        i18n_tabs = get_translation_tabs(
            instance,
            request,
            include_all_languages=True,
            default_language=instance.type.primary_language,
        )
        tabs += i18n_tabs

        return CommonCategoryEditHandler(tabs)
