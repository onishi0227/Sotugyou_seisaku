
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError


User = get_user_model()


class AccountCreationForm(forms.Form):
    """社員IDとパスワードを検証する登録フォーム。"""

    employee_id = forms.CharField(
        label="社員ID",
        max_length=150,
        required=True,
    )

    password1 = forms.CharField(
        label="パスワード",
        widget=forms.PasswordInput,
        strip=False,
        required=True,
    )

    password2 = forms.CharField(
        label="パスワード（確認）",
        widget=forms.PasswordInput,
        strip=False,
        required=True,
    )

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"].strip()

        if not employee_id:
            raise ValidationError("社員IDを入力してください。")

        if User.objects.filter(username=employee_id).exists():
            raise ValidationError("この社員IDはすでに登録されています。")

        return employee_id

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        employee_id = self.cleaned_data.get("employee_id", "")

        user = User(username=employee_id)

        password_validation.validate_password(password, user=user)

        return password

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "password2",
                "パスワードが一致しません。",
            )

        return cleaned_data

    def save(self):
        """検証済みの社員アカウントを登録する。"""

        return User.objects.create_user(
            username=self.cleaned_data["employee_id"],
            password=self.cleaned_data["password1"],
        )