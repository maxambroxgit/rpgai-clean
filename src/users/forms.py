from django_registration.forms import RegistrationForm
from django import forms
from users.models import customUser

class customUserRegistrationForm(RegistrationForm):
    usable_password = None

    privacy = forms.BooleanField(
        required=True,
        label="Accetto l'informativa sulla privacy",
        error_messages={"required": "Devi accettare l'informativa sulla privacy per registrarti."},
        widget=forms.CheckboxInput(attrs={
            "class": "mt-1 mr-2 text-green-600 focus:ring-green-500 border-gray-300 rounded"
        }),
    )

    class Meta(RegistrationForm.Meta):
        model = customUser  # corretto
        fields = ['username', 'email', 'password1', 'password2']  # se vuoi puoi specificare i campi

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aggiungi classi Tailwind a tutti i campi di input, tranne checkbox
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ != 'CheckboxInput':
                existing_classes = field.widget.attrs.get('class', '')
                classes = f'{existing_classes} w-full px-4 py-2 rounded bg-gray-800 text-white border border-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500'
                field.widget.attrs['class'] = classes.strip()
