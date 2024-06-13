from __future__ import annotations

from typing import TYPE_CHECKING

from unittest import mock
import pytest

import dns.resolver

if TYPE_CHECKING:
    from actions.models.plan import Plan
    from actions.models.plan_deploy import PlanDomainDeployInfo

pytestmark = pytest.mark.django_db


@pytest.fixture
def deploy_allowed_cnames():
    with mock.patch('django.conf.settings.DEPLOY_ALLOWED_CNAMES', new=['example.com']):
        yield


def test_deployinfo_dns(plan: Plan, deploy_allowed_cnames):
    domain = plan.domains.create(name='example.com')
    deploy_info = PlanDomainDeployInfo(domain=domain)

    # Test case 1: DNS check succeeds
    with mock.patch('dns.resolver.resolve') as mock_resolve:
        mock_resolve.return_value.chaining_result.cnames = [['example.com']]
        deploy_info.check_dns()
        assert deploy_info.dns_status == deploy_info.DNSStatus.OK
        assert deploy_info.dns_status_msg is not None

    # Test case 2: DNS check fails with NXDOMAIN
    with mock.patch('dns.resolver.resolve') as mock_resolve:
        mock_resolve.side_effect = dns.resolver.NXDOMAIN()
        deploy_info.check_dns()
        assert deploy_info.dns_status == deploy_info.DNSStatus.DOES_NOT_EXIST
        assert deploy_info.dns_status_msg is not None

    # Test case 3: DNS check fails with no CNAME records
    with mock.patch('dns.resolver.resolve') as mock_resolve:
        mock_resolve.return_value.chaining_result.cnames = []
        deploy_info.check_dns()
        assert deploy_info.dns_status == deploy_info.DNSStatus.NOT_CNAME
        assert deploy_info.dns_status_msg is not None

    # Test case 4: DNS check fails with invalid CNAME target
    with mock.patch('dns.resolver.resolve') as mock_resolve:
        mock_resolve.return_value.chaining_result.cnames = [['invalid.com']]
        deploy_info.check_dns()
        assert deploy_info.dns_status == deploy_info.DNSStatus.INVALID_TARGET
        assert deploy_info.dns_status_msg is not None
