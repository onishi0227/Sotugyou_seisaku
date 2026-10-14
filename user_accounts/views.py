from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AccountCreationForm
from .models import EmployeeProfile


@require_http_methods(["GET", "POST"])
def account_register(request):
    """権限に応じて社員アカウントを作成する。"""

    # 未ログインの人は登録画面を利用できない
    if not request.user.is_authenticated:
        return redirect("login")

    # 社員の権限情報を取得する
    try:
        profile = request.user.employee_profile
    except EmployeeProfile.DoesNotExist:
        return HttpResponseForbidden(
            "アカウント作成の権限が設定されていません。"
        )

    # 本社管理者は店長を、店長は店員を作成できる
    if profile.role == EmployeeProfile.Role.HEADQUARTERS_ADMIN:
        target_role = EmployeeProfile.Role.STORE_MANAGER
        can_choose_store = True

    elif profile.role == EmployeeProfile.Role.STORE_MANAGER:
        target_role = EmployeeProfile.Role.STAFF
        can_choose_store = False

        if not profile.store_code:
            return HttpResponseForbidden(
                "所属店舗が設定されていないため、店員を作成できません。"
            )

    else:
        return HttpResponseForbidden(
            "アカウントを作成する権限がありません。"
        )

    if request.method == "POST":
        form = AccountCreationForm(request.POST)

        if form.is_valid():
            if can_choose_store:
                # 本社管理者が作る店長には所属店舗を指定する
                store_code = form.cleaned_data["store_code"].strip()

                if not store_code:
                    form.add_error(
                        "store_code",
                        "所属店舗コードを入力してください。",
                    )
            else:
                # 店長が作る店員は、自分と同じ店舗に所属させる
                store_code = profile.store_code

            if not form.errors:
                new_user = form.save()

                EmployeeProfile.objects.create(
                    user=new_user,
                    role=target_role,
                    full_name=form.cleaned_data["full_name"].strip(),
                    store_code=store_code,
                )

                # 作成したアカウントの情報を残さず、フォームを初期化する
                return render(
                    request,
                    "account_register.html",
                    {
                        "form": AccountCreationForm(),
                        "can_choose_store": can_choose_store,
                        "target_role_label": (
                            "店長"
                            if can_choose_store
                            else "店員"
                        ),
                        "success_message": (
                            f"{'店長' if can_choose_store else '店員'}"
                            "アカウントを登録しました。"
                        ),
                    },
                )
    else:
        form = AccountCreationForm()

    return render(
        request,
        "account_register.html",
        {
            "form": form,
            "can_choose_store": can_choose_store,
            "target_role_label": (
                "店長" if can_choose_store else "店員"
            ),
        },
    )


@require_http_methods(["GET", "POST"])
def login_view(request):
    """社員IDとパスワードでログインする。"""

    if request.method == "POST":
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