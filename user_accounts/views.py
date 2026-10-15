
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AccountCreationForm
from .models import EmployeeProfile, MenuItem


# ログイン前に選択した入口をセッションに保存する
LOGIN_PORTAL_SESSION_KEY = "login_portal"

STORE_PORTAL = "store"
HEADQUARTERS_PORTAL = "headquarters"


def _get_employee_profile(user):
    """ユーザーに紐づく社員プロフィールを取得する。"""
    try:
        return user.employee_profile
    except EmployeeProfile.DoesNotExist:
        return None


def _record_active_session(request, profile):
    """現在のログインセッションを社員プロフィールに記録する。"""
    if request.session.session_key is None:
        request.session.save()

    profile.active_session_key = request.session.session_key
    profile.save(update_fields=["active_session_key"])


def _redirect_to_role_home(user):
    """ログイン済みユーザーを権限に応じたトップ画面へ移動する。"""
    profile = _get_employee_profile(user)

    if profile is None:
        return HttpResponseForbidden(
            "アカウントの権限が設定されていません。管理者に確認してください。"
        )

    if profile.role == EmployeeProfile.Role.HEADQUARTERS_ADMIN:
        return redirect("headquarters_top")

    if profile.role in (
        EmployeeProfile.Role.STORE_MANAGER,
        EmployeeProfile.Role.STAFF,
    ):
        return redirect("store_top")

    return HttpResponseForbidden("有効な権限が設定されていません。")


@never_cache
def entry_view(request):
    """S-00 入口画面を表示する。"""
    if request.user.is_authenticated:
        return _redirect_to_role_home(request.user)

    return render(request, "top.html")


def _select_login_portal(request, portal):
    """ログイン先をセッションに保存して共通ログイン画面へ移動する。"""
    if request.user.is_authenticated:
        return _redirect_to_role_home(request.user)

    request.session[LOGIN_PORTAL_SESSION_KEY] = portal
    return redirect("login")


@never_cache
@require_GET
def select_store_portal(request):
    """店舗側ログインを選択する。"""
    return _select_login_portal(request, STORE_PORTAL)


@never_cache
@require_GET
def select_headquarters_portal(request):
    """本社側ログインを選択する。"""
    return _select_login_portal(request, HEADQUARTERS_PORTAL)


@never_cache
@require_http_methods(["GET", "POST"])
def account_register(request):
    """権限に応じて社員アカウントを作成する。"""

    if not request.user.is_authenticated:
        return redirect("login")

    profile = _get_employee_profile(request.user)

    if profile is None:
        return HttpResponseForbidden(
            "アカウント作成の権限が設定されていません。"
        )

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
                store_code = form.cleaned_data["store_code"].strip()

                if not store_code:
                    form.add_error(
                        "store_code",
                        "所属店舗コードを入力してください。",
                    )
            else:
                store_code = profile.store_code

            if not form.errors:
                new_user = form.save()

                EmployeeProfile.objects.create(
                    user=new_user,
                    role=target_role,
                    full_name=form.cleaned_data["full_name"].strip(),
                    store_code=store_code,
                )

                target_role_label = "店長" if can_choose_store else "店員"

                return render(
                    request,
                    "account_register.html",
                    {
                        "form": AccountCreationForm(),
                        "can_choose_store": can_choose_store,
                        "target_role_label": target_role_label,
                        "success_message": (
                            f"{target_role_label}アカウントを登録しました。"
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


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    """共通ログイン画面。入口とアカウント権限を照合する。"""

    portal = request.session.get(LOGIN_PORTAL_SESSION_KEY)

    if portal not in (STORE_PORTAL, HEADQUARTERS_PORTAL):
        return redirect("entry")

    portal_label = (
        "店舗ログイン"
        if portal == STORE_PORTAL
        else "本社ログイン"
    )

    if request.user.is_authenticated:
        return _redirect_to_role_home(request.user)

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

        if user is None:
            return render(
                request,
                "login.html",
                {
                    "portal": portal,
                    "portal_label": portal_label,
                    "error_message": (
                        "社員IDまたはパスワードが正しくありません。"
                    ),
                },
            )

        profile = _get_employee_profile(user)

        if profile is None:
            return render(
                request,
                "login.html",
                {
                    "portal": portal,
                    "portal_label": portal_label,
                    "error_message": (
                        "アカウントの権限が設定されていません。"
                        "管理者に確認してください。"
                    ),
                },
            )

        if portal == STORE_PORTAL:
            allowed_roles = (
                EmployeeProfile.Role.STORE_MANAGER,
                EmployeeProfile.Role.STAFF,
            )

            if profile.role not in allowed_roles:
                return render(
                    request,
                    "login.html",
                    {
                        "portal": portal,
                        "portal_label": portal_label,
                        "error_message": (
                            "このアカウントは本社用です。"
                            "店舗用の入口からはログインできません。"
                        ),
                    },
                )

            auth_login(request, user)
            _record_active_session(request, profile)
            return redirect("store_top")

        if portal == HEADQUARTERS_PORTAL:
            if profile.role != EmployeeProfile.Role.HEADQUARTERS_ADMIN:
                return render(
                    request,
                    "login.html",
                    {
                        "portal": portal,
                        "portal_label": portal_label,
                        "error_message": (
                            "このアカウントは店舗用です。"
                            "本社用の入口からはログインできません。"
                        ),
                    },
                )

            auth_login(request, user)
            _record_active_session(request, profile)
            return redirect("headquarters_top")

    return render(
        request,
        "login.html",
        {
            "portal": portal,
            "portal_label": portal_label,
        },
    )


@never_cache
def login_success(request):
    """旧ログイン成功URLから来た場合も権限に応じて振り分ける。"""
    if not request.user.is_authenticated:
        return redirect("entry")

    return _redirect_to_role_home(request.user)


@never_cache
@require_GET
def store_top(request):
    """S-08 店舗トップ画面を表示する。"""

    if not request.user.is_authenticated:
        return redirect("entry")

    profile = _get_employee_profile(request.user)

    if (
        profile is None
        or profile.role not in (
            EmployeeProfile.Role.STORE_MANAGER,
            EmployeeProfile.Role.STAFF,
        )
        or request.session.get(LOGIN_PORTAL_SESSION_KEY) != STORE_PORTAL
    ):
        return HttpResponseForbidden(
            "店舗トップ画面を表示する権限がありません。"
        )

    context = {
        "is_store_manager": (
            profile.role == EmployeeProfile.Role.STORE_MANAGER
        ),
    }

    return render(request, "store.html", context)


@never_cache
@require_GET
def headquarters_top(request):
    """S-16 本社管理者トップ画面を表示する。"""

    if not request.user.is_authenticated:
        return redirect("entry")

    profile = _get_employee_profile(request.user)

    if (
        profile is None
        or profile.role != EmployeeProfile.Role.HEADQUARTERS_ADMIN
        or request.session.get(LOGIN_PORTAL_SESSION_KEY)
        != HEADQUARTERS_PORTAL
    ):
        return HttpResponseForbidden(
            "本社トップ画面を表示する権限がありません。"
        )

    return render(request, "headquarters.html")


@never_cache
@require_GET
def headquarters_master(request):
    """S-21 本社管理者用マスタ管理画面を表示する。"""

    if not request.user.is_authenticated:
        return redirect("entry")

    profile = _get_employee_profile(request.user)

    if (
        profile is None
        or profile.role != EmployeeProfile.Role.HEADQUARTERS_ADMIN
        or request.session.get(LOGIN_PORTAL_SESSION_KEY)
        != HEADQUARTERS_PORTAL
    ):
        return HttpResponseForbidden(
            "マスタ管理画面を表示する権限がありません。"
        )

    return render(request, "master.html")


@require_GET
def customer_order(request, store_id, table_no):
    """QRコードから開くお客様用画面。ログインは不要。"""

    request.session["store_id"] = store_id
    request.session["table_no"] = table_no

    context = {
        "store_id": store_id,
        "table_no": table_no,
    }

    return render(request, "customer.html", context)


@require_GET
def customer_menu(request, store_id, table_no):
    """店舗・テーブルに対応したメニュー商品一覧を表示する。"""

    request.session["store_id"] = store_id
    request.session["table_no"] = table_no

    products = MenuItem.objects.filter(
        store_id=store_id,
        is_available=True,
    )

    context = {
        "store_id": store_id,
        "table_no": table_no,
        "products": products,
    }

    return render(request, "product_list.html", context)


@never_cache
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """ログアウト時に現在のセッション情報を解除する。"""

    if request.method == "POST":
        if request.user.is_authenticated:
            profile = _get_employee_profile(request.user)

            if (
                profile is not None
                and profile.active_session_key
                == request.session.session_key
            ):
                profile.active_session_key = ""
                profile.save(update_fields=["active_session_key"])

        auth_logout(request)
        return redirect("entry")

    return render(request, "logout.html")
