from django.db.models import Case, Value, When


_wagtail_get_context_data = None


def get_context_data(self):
    ret = _wagtail_get_context_data(self)

    plan = self.request.user.get_active_admin_plan()
    if plan.root_collection is not None:
        collections = plan.root_collection.get_descendants(inclusive=True)
    else:
        collections = []

    if len(collections) < 2:
        collections = None
    else:
        collections = collections.annotate(
            display_order=Case(
                When(depth=1, then=Value('')),
                default='name')
        ).order_by('display_order')

    ret['collections'] = collections
    return ret


def monkeypatch_chooser():
    from wagtail.images.views.chooser import ChooseView
    global _wagtail_get_context_data

    if _wagtail_get_context_data is not None:
        return

    _wagtail_get_context_data = ChooseView.get_context_data
    ChooseView.get_context_data = get_context_data
