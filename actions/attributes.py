from dal import autocomplete, forward as dal_forward
from dataclasses import dataclass
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from typing import Any, Dict, List
from wagtail.admin.edit_handlers import FieldPanel

import actions.models.attributes as models


class AttributeFieldPanel(FieldPanel):
    def on_form_bound(self):
        super().on_form_bound()
        user = self.request.user
        attribute_types = self.instance.get_editable_attribute_types(user)
        for attribute_type in attribute_types:
            for field in attribute_type.get_form_fields(self.instance):
                if field.name == self.field_name:
                    self.form.fields[self.field_name].initial = field.django_field.initial
                    return
        raise Exception(f"Unknown field {self.field_name}")


@dataclass
class FormField:
    attribute_type: 'AttributeType'
    django_field: forms.Field
    name: str
    label: str = ''
    # If the field refers to a modeltrans field and `language` is not empty, use localized virtual field for `language`.
    language: str = ''

    def get_panel(self):
        if self.label:
            heading = self.label
        else:
            heading = self.attribute_type.instance.name_i18n
        if self.language:
            heading += f' ({self.language})'
        return AttributeFieldPanel(self.name, heading=heading)


class AttributeType:
    # In subclasses, define ATTRIBUTE_MODEL to be the model of the attributes of that type. It needs to have a foreign
    # key to actions.models.attributes.AttributeType called `type` with a defined `related_name`.

    @classmethod
    def from_model_instance(cls, instance: models.AttributeType):
        if instance.format == models.AttributeType.AttributeFormat.ORDERED_CHOICE:
            return OrderedChoice(instance)
        elif instance.format == models.AttributeType.AttributeFormat.CATEGORY_CHOICE:
            return CategoryChoice(instance)
        elif instance.format == models.AttributeType.AttributeFormat.OPTIONAL_CHOICE_WITH_TEXT:
            return OptionalChoiceWithText(instance)
        elif instance.format == models.AttributeType.AttributeFormat.TEXT:
            return Text(instance)
        elif instance.format == models.AttributeType.AttributeFormat.RICH_TEXT:
            return RichText(instance)
        elif instance.format == models.AttributeType.AttributeFormat.NUMERIC:
            return Numeric(instance)
        raise ValueError('Unsupported attribute type format: %s' % instance.format)

    def __init__(self, instance: models.AttributeType):
        self.instance = instance

    @property
    def attributes(self):
        related_name = self.ATTRIBUTE_MODEL._meta.get_field('type').remote_field.related_name
        return getattr(self.instance, related_name)

    def get_attributes(self, obj: models.ModelWithAttributes):
        """Get the attributes of this type for the given object."""
        content_type = ContentType.objects.get_for_model(obj)
        assert content_type.app_label == 'actions'
        if content_type.model == 'action':
            assert self.instance.scope == obj.plan
        elif content_type.model == 'category':
            assert self.instance.scope == obj.type
        else:
            raise ValueError(f"Invalid content type {content_type.app_label}.{content_type.model} of object {obj}")
        return self.attributes.filter(content_type=content_type, object_id=obj.id)

    def create_attribute(self, obj: models.ModelWithAttributes, **args):
        return self.ATTRIBUTE_MODEL.objects.create(type=self.instance, content_object=obj, **args)

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        # Implement in subclass
        raise NotImplementedError()

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        """Set the attribute(s) of this type for the given object using cleaned data from a form.

        This may create new attribute model instances as well as change or delete existing ones.
        """
        # Implement in subclass
        raise NotImplementedError()


class OrderedChoice(AttributeType):
    ATTRIBUTE_MODEL = models.AttributeChoice

    @property
    def form_field_name(self):
        return f'attribute_type_{self.instance.identifier}'

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        initial_choice = None
        if obj:
            c = self.get_attributes(obj).first()
            if c:
                initial_choice = c.choice

        choice_options = self.instance.choice_options.all()
        field = forms.ModelChoiceField(
            choice_options, initial=initial_choice, required=False, help_text=self.instance.help_text_i18n
        )
        return [FormField(attribute_type=self, django_field=field, name=self.form_field_name)]

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        existing = self.get_attributes(obj)
        if existing:
            existing.delete()
        val = cleaned_data.get(self.form_field_name)
        if val is not None:
            self.create_attribute(obj, choice=val)


class CategoryChoice(AttributeType):
    ATTRIBUTE_MODEL = models.AttributeCategoryChoice

    @property
    def form_field_name(self):
        return f'attribute_type_{self.instance.identifier}'

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        from actions.models.category import Category
        initial_categories = None
        if obj:
            c = self.get_attributes(obj).first()
            if c:
                initial_categories = c.categories.all()

        categories = Category.objects.filter(type=self.instance.attribute_category_type)
        field = forms.ModelMultipleChoiceField(
            categories,
            initial=initial_categories,
            required=False,
            help_text=self.instance.help_text_i18n,
            widget=autocomplete.ModelSelect2Multiple(
                url='category-autocomplete',
                forward=(
                    dal_forward.Const(self.instance.attribute_category_type.id, 'type'),
                )
            ),
        )
        return [FormField(attribute_type=self, django_field=field, name=self.form_field_name)]

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        existing = self.get_attributes(obj)
        if existing:
            existing.delete()
        val = cleaned_data.get(self.form_field_name)
        if val is not None:
            attribute = self.create_attribute(obj)
            attribute.categories.set(val)


class OptionalChoiceWithText(AttributeType):
    ATTRIBUTE_MODEL = models.AttributeChoiceWithText

    @property
    def choice_form_field_name(self):
        return f'attribute_type_{self.instance.identifier}_choice'

    def get_text_form_field_name(self, language):
        name = f'attribute_type_{self.instance.identifier}_text'
        if language:
            name += f'_{language}'
        return name

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        fields = []
        attribute = None
        if obj:
            attribute = self.get_attributes(obj).first()

        # Choice
        initial_choice = None
        if attribute:
            initial_choice = attribute.choice

        choice_options = self.instance.choice_options.all()
        choice_field = forms.ModelChoiceField(
            choice_options, initial=initial_choice, required=False, help_text=self.instance.help_text_i18n
        )
        fields.append(FormField(
            attribute_type=self,
            django_field=choice_field,
            name=self.choice_form_field_name,
            label=_('%(attribute_type)s (choice)') % {'attribute_type': self.instance.name_i18n},
        ))

        # Text (one field for each language)
        for language in ('', *self.instance.other_languages):
            initial_text = None
            attribute_text_field_name = f'text_{language}' if language else 'text'
            if attribute:
                initial_text = getattr(attribute, attribute_text_field_name)
            text_field = self.ATTRIBUTE_MODEL._meta.get_field(attribute_text_field_name).formfield(
                initial=initial_text, required=False, help_text=self.instance.help_text_i18n
            )
            fields.append(FormField(
                attribute_type=self,
                django_field=text_field,
                name=self.get_text_form_field_name(language),
                language=language,
                label=_('%(attribute_type)s (text)') % {'attribute_type': self.instance.name_i18n},
            ))
        return fields

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        existing = self.get_attributes(obj)
        if existing:
            existing.delete()
        choice_val = cleaned_data.get(self.choice_form_field_name)
        text_vals = {}
        for language in ('', *self.instance.other_languages):
            attribute_text_field_name = f'text_{language}' if language else 'text'
            text_form_field_name = self.get_text_form_field_name(language)
            text_vals[attribute_text_field_name] = cleaned_data.get(text_form_field_name)
        has_text_in_some_language = any(v for v in text_vals.values())
        if choice_val is not None or has_text_in_some_language:
            self.create_attribute(obj, choice=choice_val, **text_vals)


class TextAttributeTypeMixin:
    def get_form_field_name(self, language):
        name = f'attribute_type_{self.instance.identifier}'
        if language:
            name += f'_{language}'
        return name

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        fields = []
        attribute = None
        if obj:
            attribute = self.get_attributes(obj).first()

        for language in ('', *self.instance.other_languages):
            initial_text = None
            attribute_text_field_name = f'text_{language}' if language else 'text'
            if attribute:
                initial_text = getattr(attribute, attribute_text_field_name)
            field = self.ATTRIBUTE_MODEL._meta.get_field(attribute_text_field_name).formfield(
                initial=initial_text, required=False, help_text=self.instance.help_text_i18n
            )
            fields.append(FormField(
                attribute_type=self,
                django_field=field,
                name=self.get_form_field_name(language),
                language=language,
            ))
        return fields

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        text_vals = {}
        for language in ('', *self.instance.other_languages):
            attribute_text_field_name = f'text_{language}' if language else 'text'
            text_form_field_name = self.get_form_field_name(language)
            text_vals[attribute_text_field_name] = cleaned_data.get(text_form_field_name)
        has_text_in_some_language = any(v for v in text_vals.values())
        try:
            attribute = self.get_attributes(obj).get()
        except self.ATTRIBUTE_MODEL.DoesNotExist:
            if has_text_in_some_language:
                self.create_attribute(obj, **text_vals)
        else:
            if not has_text_in_some_language:
                attribute.delete()
            else:
                for field_name, value in text_vals.items():
                    setattr(attribute, field_name, value)
                attribute.save()


class Text(TextAttributeTypeMixin, AttributeType):
    ATTRIBUTE_MODEL = models.AttributeText


class RichText(TextAttributeTypeMixin, AttributeType):
    ATTRIBUTE_MODEL = models.AttributeRichText


class Numeric(AttributeType):
    ATTRIBUTE_MODEL = models.AttributeNumericValue

    @property
    def form_field_name(self):
        return f'attribute_type_{self.instance.identifier}'

    def get_form_fields(self, obj: models.ModelWithAttributes = None) -> List[FormField]:
        attribute = None
        if obj:
            attribute = self.get_attributes(obj).first()
        initial_value = None
        if attribute:
            initial_value = attribute.value
        field = forms.FloatField(initial=initial_value, required=False, help_text=self.instance.help_text_i18n)
        return [FormField(attribute_type=self, django_field=field, name=self.form_field_name)]

    def set_attributes(self, obj: models.ModelWithAttributes, cleaned_data: Dict[str, Any]):
        val = cleaned_data.get(self.form_field_name)
        try:
            attribute = self.get_attributes(obj).get()
        except self.ATTRIBUTE_MODEL.DoesNotExist:
            if val is not None:
                self.create_attribute(obj, value=val)
        else:
            if val is None:
                attribute.delete()
            else:
                attribute.value = val
                attribute.save()