from django.contrib.gis.db.backends.postgis.base import (
    DatabaseWrapper as PostGisPsycopg2DatabaseWrapper
)
from django.db import close_old_connections, connection as db_connection
from psycopg.errors import InterfaceError


class DatabaseWrapper(PostGisPsycopg2DatabaseWrapper):
    def create_cursor(self, name=None):
        try:
            return super().create_cursor(name=name)
        except InterfaceError:
            close_old_connections()
            db_connection.connect()
            return super().create_cursor(name=name)
