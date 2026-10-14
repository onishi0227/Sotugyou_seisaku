
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AccountCreationForm


@require_http_methods(["GET", "POST"])
def account_register(request):
    """アカウントを新規登録する。"""

    if request.method == "POST":
        form = AccountCreationForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("login")

        return render(
            request,
            "account_register.html",
            {
                "form": form,
                "error_message": "入力内容を確認してください。",
            },
        )

    form = AccountCreationForm()

    return render(
        request,
        "account_register.html",
        {"form": form},
    )


@require_http_methods(["GET", "POST"])
def login_view(request):
    """社員IDとパスワードでログインする。"""

    if request.method == "POST":
        # 社員IDを受け取る。
        # 古いHTMLとの互換性のため、旧入力名にも対応する。
        employee_id = (
            request.POST.get("employee_id")
            or request.POST.get("username")
            or request.POST.get("store_code")
            or ""
        ).strip()

        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=employee_id,
            password=password,
        )

        if user is not None:
            auth_login(request, user)
            return redirect("login_success")

        return render(
            request,
            "login.html",
            {
                "error_message": (
                    "社員IDまたはパスワードが正しくありません。"
                ),
            },
        )

    return render(request, "login.html")


def login_success(request):
    """ログイン成功後の一時的な確認先。"""

    if not request.user.is_authenticated:
        return redirect("login")

    return HttpResponse(
        "ログインに成功しました。"
        "画面担当のHTMLとの接続後に、適切な画面へ遷移させます。"
    )


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """ログアウト確認画面を表示し、POSTでログアウトする。"""

    if request.method == "POST":
        auth_logout(request)
        return redirect("login")

    return render(request, "logout.html")
