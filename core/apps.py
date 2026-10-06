from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from . import file_cleanup, signals
        file_cleanup.connect()
        signals.connect()  # security log: sign-ins, sign-ups, role changes
