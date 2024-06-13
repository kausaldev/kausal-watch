from datetime import timedelta

from celery import shared_task
from django.db.models import Max, Q
from django.utils import timezone
from yaml import safe_dump

from actions.models.plan import PlanDomain
from actions.models.plan_deploy import PlanDomainDeployInfo

DEPLOY_INFO_REFRESH_HOURS = 1
DEPLOY_INFO_CHECK_BATCH_SIZE = 20


@shared_task
def refresh_deployment_info(plan_domain_pk: str):
    pd = PlanDomain.objects.get(id=plan_domain_pk)

    try:
        previous = pd.deploy_infos.latest()
    except PlanDomainDeployInfo.DoesNotExist:
        previous = None

    info = PlanDomainDeployInfo(domain=pd)
    info.check_all()

    now = timezone.now()

    if previous:
        if info.statuses_changed(previous):
            for field in PlanDomainDeployInfo.STATUS_FIELDS:
                setattr(previous, field, getattr(info, field))
        previous.checked_at = now
        previous.save()
    else:
        info.checked_at = info.created_at = now
        info.save()


@shared_task
def refresh_deployment_info_batch():
    now = timezone.now()
    domains = (
        PlanDomain.objects.all().annotate(last_check=Max('deploy_infos__checked_at'))
        .filter(Q(last_check__isnull=True) | Q(last_check__lte=now - timedelta(hours=DEPLOY_INFO_REFRESH_HOURS)))
    )
    for idx, pd in enumerate(domains[0:DEPLOY_INFO_CHECK_BATCH_SIZE]):
        delay_secs = idx * 5
        refresh_deployment_info.apply_async(  # type: ignore
            (pd.pk,),
            countdown=now + timedelta(seconds=delay_secs),
            expires=now + timedelta(seconds=delay_secs + 120),
        )


@shared_task
def update_deployment_hostnames():
    # FIXME: Do this based on deployment type
    domains = PlanDomain.objects.exclude(hostname__icontains='kausal.tech')
    infos = PlanDomainDeployInfo.objects.filter(domain__in=domains).order_by('domain', '-created_at').distinct('domain').select_related('domain')
    out = []
    for info in infos:
        use_tls = info.dns_status == PlanDomainDeployInfo.DNSStatus.OK
        out.append(dict(hostname=info.get_hostname(), tls=use_tls, path=info.get_path_prefix()))

    s = safe_dump(dict(externalHosts=out))
