from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = "Fail unless critical production release prerequisites are present."

    def handle(self, *args, **options):
        problems = []
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        leaf_nodes = loader.graph.leaf_nodes()
        if not leaf_nodes:
            problems.append("No migration graph exists.")
        unmigrated = sorted(loader.unmigrated_apps)
        if unmigrated:
            problems.append(
                "Apps without committed migration packages: " + ", ".join(unmigrated)
            )
        migration_dir = Path.cwd()
        for app_label in ("accounts", "organizations", "parties", "pricing",
                          "collections", "finance", "inventory", "audit", "platform_admin"):
            app_config = next(
                (app for app in loader.migrated_apps if app == app_label), None
            )
            if app_config is None:
                problems.append(f"{app_label} has no committed migration.")
        if connection.vendor != "postgresql":
            problems.append("Release database must be PostgreSQL.")
        if problems:
            self.stderr.write(self.style.ERROR("RELEASE BLOCKED"))
            for problem in problems:
                self.stderr.write(f" - {problem}")
            raise CommandError("Resolve every release blocker before deployment.")
        self.stdout.write(self.style.SUCCESS("Migration and database release gates passed."))
