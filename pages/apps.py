import typing
from django.apps import AppConfig
from django.conf import settings

if typing.TYPE_CHECKING:
    from wagtail.core.models import Page


def get_pages_with_direct_explore_permission(user):
    from wagtail.core.models import Page
    return Page.objects.filter(depth=1)


def get_site_for_user(user):
    plan = user.get_active_admin_plan()
    if not plan:
        return None

    root_page = plan.root_page
    if root_page:
        root_site = root_page.get_site()
    else:
        root_site = None

    real_site_name = None
    if root_site:
        real_site_name = root_site.site_name if root_site.site_name else root_site.hostname
    return {
        'root_page': root_page,
        'root_site': root_site,
        'site_name': real_site_name if real_site_name else settings.WAGTAIL_SITE_NAME,
    }


def patch_wagtail_page_hierarchy():
    """Monkeypatch filtering pages by the currently active action plan."""
    from wagtail.admin import navigation
    navigation.get_pages_with_direct_explore_permission = get_pages_with_direct_explore_permission
    # The original get_site_for_user function determines site by explorable root page. Since here the explorable root
    # page is always the global root this doesn't make much sense.
    navigation.get_site_for_user = get_site_for_user


def resolve_page_url_path(self, info):
    # Strip the trailing '/'
    return self.url_path.rstrip('/')


def resolve_parent(self: 'Page', info, **kwargs):
    from pages.models import PlanRootPage
    if isinstance(self.specific, PlanRootPage):
        return None
    parent = self.get_parent()
    if parent is None or parent.depth == 1:
        return None
    return parent


def resolve_siblings(self, info, **kwargs):
    return []


def resolve_ancestors(self, info, **kwargs):
    from grapple.utils import resolve_queryset

    qs = self.get_ancestors().live().public().specific()
    qs = qs.filter(depth__gt=2)
    return resolve_queryset(qs, info, **kwargs)


def patch_grapple_url_resolvers():
    from grapple.types.pages import PageInterface

    PageInterface.resolve_url_path = resolve_page_url_path
    PageInterface.resolve_parent = resolve_parent
    PageInterface.resolve_siblings = resolve_siblings
    PageInterface.resolve_next_siblings = resolve_siblings
    PageInterface.resolve_previous_siblings = resolve_siblings
    PageInterface.resolve_ancestors = resolve_ancestors


class PagesConfig(AppConfig):
    name = 'pages'

    def ready(self):
        patch_wagtail_page_hierarchy()
        patch_grapple_url_resolvers()
