from django.conf import settings
from reversion.revisions import add_to_revision, create_revision, set_comment, set_user
from modeltrans.translator import get_i18n_field
from wagtail.contrib.modeladmin.views import CreateView, EditView, InspectView
from wagtail.admin.edit_handlers import (
    FieldPanel, InlinePanel, RichTextFieldPanel, TabbedInterface, ObjectList
)
from wagtail.contrib.modeladmin.options import ModelAdmin
from wagtail.admin.edit_handlers import (
    ObjectList
)
from wagtail.admin.forms.models import WagtailAdminModelForm


class AdminOnlyPanel(ObjectList):
    pass


class AplansAdminModelForm(WagtailAdminModelForm):
    pass


class AplansTabbedInterface(TabbedInterface):
    def on_request_bound(self):
        user = self.request.user
        plan = user.get_active_admin_plan()

        if not user.is_general_admin_for_plan(plan):
            for child in list(self.children):
                if isinstance(child, AdminOnlyPanel):
                    self.children.remove(child)

        super().on_request_bound()


class FormClassMixin:
    def get_form_class(self):
        handler = self.get_edit_handler()
        if isinstance(handler, AplansTabbedInterface):
            return handler.get_form_class(self.request)
        else:
            return handler.get_form_class()


class AplansEditView(FormClassMixin, EditView):
    def form_valid(self, form, *args, **kwargs):
        form_valid_return = super().form_valid(form, *args, **kwargs)

        with create_revision():
            set_comment(self.get_success_message(self.instance))
            add_to_revision(self.instance)
            set_user(self.request.user)

        return form_valid_return


class AplansCreateView(CreateView):
    def form_valid(self, form, *args, **kwargs):
        ret = super().form_valid(form, *args, **kwargs)
        return ret

        """
        # Call form.save() explicitly to get access to the instance
        instance = form.save()

        with create_revision():
            set_comment(self.get_success_message(instance))
            add_to_revision(instance)
            set_user(self.request.user)

        return ret
        """


class AplansModelAdmin(ModelAdmin):
    edit_view_class = AplansEditView
    create_view_class = AplansCreateView

    def get_translation_tabs(self, instance, request):
        i18n_field = get_i18n_field(type(instance))
        if not i18n_field:
            return []
        tabs = []

        user = request.user
        plan = user.get_active_admin_plan()

        languages_by_code = {x[0]: x[1] for x in settings.LANGUAGES}

        for lang_code in plan.other_languages:
            fields = []
            for field in i18n_field.get_translated_fields():
                if field.language != lang_code:
                    continue
                fields.append(FieldPanel(field.name))
            tabs.append(ObjectList(fields, heading=languages_by_code[lang_code]))
        return tabs

    def insert_model_translation_tabs(self, model, panels, request, plan=None):
        i18n_field = get_i18n_field(model)
        if not i18n_field:
            return

        out = []
        if plan is None:
            plan = request.user.get_active_admin_plan()

        # languages_by_code = {x[0]: x[1] for x in settings.LANGUAGES}

        field_map = {}
        for f in i18n_field.get_translated_fields():
            field_map.setdefault(f.original_name, {})[f.language] = f

        for p in panels:
            out.append(p)
            if not isinstance(p, FieldPanel):
                continue
            t_fields = field_map.get(p.field_name)
            if not t_fields:
                continue

            for lang_code in plan.other_languages:
                tf = t_fields.get(lang_code)
                if not tf:
                    continue
                out.append(type(p)(tf.name))
        return out

    def _get_category_fields(self, plan, obj, with_initial=False):
        fields = {}
        if self.model == Action:
            filter_name = 'editable_for_actions'
        elif self.model == Indicator:
            filter_name = 'editable_for_indicators'
        else:
            raise Exception()

        for cat_type in plan.category_types.filter(**{filter_name: True}):
            qs = cat_type.categories.all()
            if obj and with_initial:
                initial = obj.categories.filter(type=cat_type)
            else:
                initial = None
            field = forms.ModelMultipleChoiceField(
                qs, label=cat_type.name, initial=initial, required=False,
            )
            field.category_type = cat_type
            fields['categories_%s' % cat_type.identifier] = field
        return fields
