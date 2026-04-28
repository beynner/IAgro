from django.apps import AppConfig

class SankhyaIntegrationConfig(AppConfig):
    name = 'sankhya_integration'

    def ready(self):
        import sankhya_integration.signals  # noqa: F401 — conecta os receivers de audit log
