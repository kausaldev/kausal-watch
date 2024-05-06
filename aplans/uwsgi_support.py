from uwsgidecorators import postfork
from django.db import connections


@postfork
def close_conns_post_fork():
    for conn in connections.all():
        conn.close()
