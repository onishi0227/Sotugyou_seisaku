
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from .models import Ingredient, MenuItem, Recipe


User = get_user_model()


class AccountCreationForm(forms.Form):
    """社員アカウント作成時の入力内容を検証する。"""

    employee_id = forms.CharField(
        label="社員ID",
        max_length=150,
        required=True,
    )

    full_name = forms.CharField(
        label="氏名",
        max_length=150,
        required=True,
    )

    store_code = forms.CharField(
        label="所属店舗コード",
        max_length=30,
        required=False,
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

        if User.objects.filter(username=employee_id).exists():
            raise ValidationError(
                "この社員IDはすでに登録されています。"
            )

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
        """検証済みの社員アカウントを作成する。"""

        return User.objects.create_user(
            username=self.cleaned_data["employee_id"],
            password=self.cleaned_data["password1"],
        )


class IngredientForm(forms.ModelForm):
    """食材の登録・入力検証を行う。"""

    class Meta:
        model = Ingredient
        fields = ["name", "unit", "delivery_days"]
        labels = {
            "name": "食材名",
            "unit": "単位",
            "delivery_days": "納品日数",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "食材名を入力してください"}
            ),
            "unit": forms.TextInput(
                attrs={"placeholder": "例：kg、g、個"}
            ),
            "delivery_days": forms.NumberInput(
                attrs={"min": 0, "placeholder": "納品までの日数"}
            ),
        }


class MenuItemForm(forms.ModelForm):
    """メニュー商品の登録・入力検証を行う。"""

    store_id = forms.IntegerField(
        label="店舗ID",
        min_value=1,
        required=True,
        widget=forms.NumberInput(
            attrs={"min": 1, "placeholder": "例：1"}
        ),
    )

    class Meta:
        model = MenuItem
        fields = [
            "store_id",
            "name",
            "price",
            "category",
            "description",
        ]
        labels = {
            "name": "メニュー名",
            "price": "価格（円）",
            "category": "カテゴリ",
            "description": "商品説明",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "メニュー名を入力してください"}
            ),
            "price": forms.NumberInput(
                attrs={"min": 0, "placeholder": "価格を入力してください"}
            ),
            "category": forms.Select(),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "商品説明（任意）",
                }
            ),
        }


class RecipeForm(forms.ModelForm):
    """メニューに使用する食材と使用量を検証する。"""

    class Meta:
        model = Recipe
        fields = ["menu_item", "ingredient", "quantity"]
        labels = {
            "menu_item": "メニュー",
            "ingredient": "食材",
            "quantity": "使用量",
        }
        widgets = {
            "menu_item": forms.Select(),
            "ingredient": forms.Select(),
            "quantity": forms.NumberInput(
                attrs={
                    "min": "0.001",
                    "step": "0.001",
                    "placeholder": "使用量を入力してください",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["menu_item"].queryset = MenuItem.objects.order_by(
            "store_id", "sort_order", "name"
        )
        self.fields["ingredient"].queryset = Ingredient.objects.order_by(
            "name"
        )
