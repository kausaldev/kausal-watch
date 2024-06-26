from io import BytesIO

from django.utils import translation
from django.utils.translation import gettext as _
import pytest
import polars
import polars.selectors as cs

from .fixtures import *  # noqa

polars.Config.set_ascii_tables(True)
polars.Config.set_tbl_rows(20)
polars.Config.set_tbl_cols(20)

pytestmark = pytest.mark.django_db


@pytest.fixture
def excel_file_from_report_factory(actions_having_attributes, report_with_all_attributes):
    def _excel_factory():
        assert report_with_all_attributes.type.plan.features.output_report_action_print_layout is True
        assert report_with_all_attributes.fields == report_with_all_attributes.type.fields
        exporter = report_with_all_attributes.get_xlsx_exporter()
        output_excel = exporter.generate_xlsx()
        return output_excel
    return _excel_factory


def assert_report_dimensions(excel_file, report, actions):
    df_actions = polars.read_excel(BytesIO(excel_file), sheet_name=_('Actions'))
    non_report_fields = ['action', 'identifier']
    has_complete_actions = False
    if report.is_complete:
        has_complete_actions = True
    else:
        for a in actions:
            if a.is_complete_for_report(report):
                has_complete_actions = True
                break
    if has_complete_actions:
        non_report_fields.extend(['marked_as_complete_by', 'marked_as_complete_at'])

    # optional choice attribute results in two columns, hence + 1
    assert df_actions.width == len(report.fields) + len(non_report_fields) + 1
    assert df_actions.height == len(actions)
    return df_actions


def test_excel_export(
        actions_having_attributes,
        report_with_all_attributes,
        excel_file_from_report_factory,
        user,
        django_assert_max_num_queries
):
    with django_assert_max_num_queries(272):
        # report.get_live_action_versions hack still causes some extra queries
        # because of implementation details wrt. reversion
        excel_file_incomplete = excel_file_from_report_factory()

    df_incomplete = assert_report_dimensions(excel_file_incomplete, report_with_all_attributes, actions_having_attributes)
    report_with_all_attributes.mark_as_complete(user)

    with django_assert_max_num_queries(33):
        excel_file_complete = excel_file_from_report_factory()

    df_complete = assert_report_dimensions(excel_file_complete, report_with_all_attributes, actions_having_attributes)

    df_complete_minus_completion = None
    with translation.override(report_with_all_attributes.xlsx_exporter.language):
        df_complete_minus_completion = df_complete.select(
            cs.all() - cs.by_name(_('Marked as complete by'), _('Marked as complete at')))
    assert df_incomplete.frame_equal(df_complete_minus_completion)


def test_partly_completed_report_excel_export(
        actions_having_attributes,
        report_with_all_attributes,
        excel_file_from_report_factory,
        user):
    actions_having_attributes[0].mark_as_complete_for_report(
        report_with_all_attributes,
        user
    )
    excel = excel_file_from_report_factory()
    assert_report_dimensions(excel, report_with_all_attributes, actions_having_attributes)
