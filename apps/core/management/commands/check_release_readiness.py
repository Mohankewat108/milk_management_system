from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = "Fail unless critical production migration and database prerequisites are present."

    required_apps = (
        "accounts",
        "organizations",
        "parties",
        "pricing",
        "collections",
        "finance",
        "inventory",
        "audit",
        "platform_admin",
    )

    def handle(self, *args, **options):
        problems = []
        if connection.vendor != "postgresql":
            problems.append("Release database must be PostgreSQL.")
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        if loader.unmigrated_apps:
            problems.append(
                "Apps without committed migrations: " + ", ".join(sorted(loader.unmigrated_apps))
            )
        for app_label in self.required_apps:
            if app_label not in loader.migrated_apps:
                problems.append(f"{app_label} has no committed migration.")
        if problems:
            self.stderr.write(self.style.ERROR("RELEASE BLOCKED"))
            for problem in problems:
                self.stderr.write(f" - {problem}")
            raise CommandError("Resolve every release blocker before deployment.")
        pending = loader.graph.leaf_nodes()
        if not pending:
            raise CommandError("No migration graph exists.")
        self.stdout.write(
            self.style.SUCCESS(
                "Migration packages exist. Run migrate --check and the deployment security checks."
            )
        )
