from django_registration.forms import RegistrationForm
from django import forms
from users.models import customUser

class customUserRegistrationForm(RegistrationForm):
    usable_password = None

    privacy = forms.BooleanField(
        required=True,
        label="Accetto l'informativa sulla privacy",
        error_messages={"required": "Devi accettare l'informativa sulla privacy per registrarti."}
    )

    class Meta(RegistrationForm.Meta):
        model = customUser  # correggi: era scritto "models"