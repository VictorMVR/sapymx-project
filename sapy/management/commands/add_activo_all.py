from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Agrega la columna 'activo' (boolean not null default true) a todas las tablas físicas que no la tengan"

    def handle(self, *args, **options):
        vendor = connection.vendor  # 'postgresql', 'mysql', 'sqlite'
        if vendor == 'postgresql':
            column_sql = 'smallint NOT NULL DEFAULT 1'
        elif vendor == 'mysql':
            column_sql = 'tinyint(4) NOT NULL DEFAULT 1'
        else:
            column_sql = 'integer NOT NULL DEFAULT 1'

        system_schemas = ('pg_catalog', 'information_schema')
        ignore_prefixes = ('django_', 'app_generator_', 'auth_', 'sessions', 'sqlite_')

        with connection.cursor() as cur:
            # Enumerar tablas físicas existentes
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema NOT IN %s
                ORDER BY table_schema, table_name
                """,
                [system_schemas],
            )
            tables = [(s, t) for s, t in cur.fetchall() if not t.startswith(ignore_prefixes)]

            for schema, table in tables:
                # Verificar existencia de columna
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s AND column_name='activo'
                    """,
                    [schema, table],
                )
                if cur.fetchone():
                    self.stdout.write(self.style.SUCCESS(f"{schema}.{table}: ya tenía 'activo'"))
                    continue
                sql = f'ALTER TABLE "{schema}"."{table}" ADD COLUMN "activo" {column_sql}'
                cur.execute(sql)
                self.stdout.write(self.style.SUCCESS(f"{schema}.{table}: agregado 'activo'"))


