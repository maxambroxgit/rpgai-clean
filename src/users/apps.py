from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Questo metodo viene chiamato quando Django è pronto.
        # È il posto giusto per importare i segnali.
        import users.signals