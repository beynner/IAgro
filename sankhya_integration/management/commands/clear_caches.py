from django.core.management.base import BaseCommand

from sankhya_integration.services.oracle_conn import clear_caches


class Command(BaseCommand):
    help = "Clear in-memory caches used by Oracle integration (metadata, units, factors)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--kind',
            type=str,
            default=None,
            help=(
                "Optional cache kind to clear: cols, pk, fk, nn/notnull, trg/triggers, "
                "like/likecols, unit/base, factor. If omitted, clears all."
            ),
        )

    def handle(self, *args, **options):
        kind = options.get('kind')
        clear_caches(kind)
        if kind:
            self.stdout.write(self.style.SUCCESS(f"Cleared caches for kind='{kind}'."))
        else:
            self.stdout.write(self.style.SUCCESS("Cleared all caches."))
