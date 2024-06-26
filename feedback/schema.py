from django import forms

from actions.models import Plan
from aplans.graphql_types import DjangoObjectType
from graphene_django.forms.mutation import DjangoModelFormMutation

from aplans.utils import public_fields

from .models import UserFeedback


class UserFeedbackForm(forms.ModelForm):
    plan = forms.ModelChoiceField(queryset=Plan.objects.all(), to_field_name='identifier')

    class Meta:
        model = UserFeedback
        fields = ('plan', 'type', 'action', 'name', 'email', 'comment', 'url')


class UserFeedbackNode(DjangoObjectType):
    class Meta:
        model = UserFeedback
        fields = public_fields(UserFeedback)


class UserFeedbackMutation(DjangoModelFormMutation):
    class Meta:
        form_class = UserFeedbackForm
        input_field_name = 'data'
        return_field_name = 'feedback'
