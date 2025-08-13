from django.apps import AppConfig


class SapyConfig(AppConfig):
    name = 'sapy'

    def ready(self):
        # Registrar templatetags package
        try:
            import sapy.templatetags.ui_extras  # noqa
        except Exception:
            pass


