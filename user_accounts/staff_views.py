
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
    password_validation,
)
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import CustomerOrder, EmployeeProfile, OrderDetail
from .views import (
    LOGIN_PORTAL_SESSION_KEY,
    STORE_PORTAL,
    _check_store_access,
    _get_employee_profile,
    _get_store_id_from_code,
    _record_active_session,
)


User = get_user_model()


def _get_store_staff(profile, employee_id):
    """店長と同じ店舗に所属する店員だけを取得する。"""

    return get_object_or_404(
        EmployeeProfile.objects.select_related("user"),
        user__username=employee_id,
        role=EmployeeProfile.Role.STAFF,
        store_code=profile.store_code.strip(),
    )


def _check_staff_access(request):
    """店員としてログインしていることと所属店舗を確認する。"""

    if not request.user.is_authenticated:
        return None, None, redirect("staff_login")

    profile = _get_employee_profile(request.user)

    if (
        profile is None
        or profile.role != EmployeeProfile.Role.STAFF
        or request.session.get(LOGIN_PORTAL_SESSION_KEY) != STORE_PORTAL
    ):
        return None, None, HttpResponseForbidden(
            "店員だけがこの機能を利用できます。"
        )

    store_code = profile.store_code.strip()

    if not store_code:
        return None, None, HttpResponseForbidden(
            "所属店舗が設定されていません。管理者に確認してください。"
        )

    store_id = _get_store_id_from_code(store_code)

    if store_id is None:
        return None, None, HttpResponseForbidden(
            "所属店舗の店舗IDを確認できません。管理者に確認してください。"
        )

    return profile, store_id, None


@never_cache
@require_http_methods(["GET", "POST"])
def staff_login(request):
    """店員が社員IDとパスワードでログインする。"""

    if request.user.is_authenticated:
        profile = _get_employee_profile(request.user)

        if (
            profile is not None
            and profile.role == EmployeeProfile.Role.STAFF
            and request.session.get(LOGIN_PORTAL_SESSION_KEY) == STORE_PORTAL
        ):
            return redirect("staff_order")

        auth_logout(request)

    error = None

    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=employee_id,
            password=password,
        )

        profile = (
            _get_employee_profile(user)
            if user is not None
            else None
        )

        if (
            user is None
            or profile is None
            or profile.role != EmployeeProfile.Role.STAFF
            or not profile.store_code.strip()
        ):
            error = "社員IDまたはパスワードが正しくありません。"
        elif _get_store_id_from_code(profile.store_code) is None:
            error = "所属店舗の設定を確認できません。管理者に連絡してください。"
        else:
            auth_login(request, user)

            request.session[LOGIN_PORTAL_SESSION_KEY] = STORE_PORTAL

            _record_active_session(request, profile)

            return redirect("staff_order")

    return render(
        request,
        "customer/staff_login.html",
        {
            "error": error,
        },
    )


@never_cache
@require_GET
def staff_order(request):
    """店員が自店舗の未会計注文があるテーブルを確認する。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    tables = (
        CustomerOrder.objects
        .filter(
            store_id=store_id,
            is_checked_out=False,
        )
        .values("table_no")
        .annotate(order_count=Count("id"))
        .order_by("table_no")
    )

    return render(
        request,
        "customer/staff_order.html",
        {
            "tables": tables,
            "store_code": profile.store_code.strip(),
        },
    )


@never_cache
@require_GET
def staff_order_detail(request):
    """指定テーブルの未会計注文の明細を表示する。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    raw_table_no = request.GET.get("table", "")

    try:
        table_no = int(raw_table_no)

        if table_no < 1:
            raise ValueError

    except (TypeError, ValueError):
        messages.error(request, "テーブル番号が正しくありません。")
        return redirect("staff_order")

    order_details = (
        OrderDetail.objects
        .filter(
            order__store_id=store_id,
            order__table_no=table_no,
            order__is_checked_out=False,
        )
        .select_related(
            "order",
            "menu_item",
        )
        .order_by(
            "order__ordered_at",
            "order_id",
            "id",
        )
    )

    return render(
        request,
        "customer/staff_order_detail.html",
        {
            "table_no": table_no,
            "order_details": order_details,
            "store_code": profile.store_code.strip(),
        },
    )


@never_cache
@require_POST
def staff_order_decrease(request, detail_id):
    """未会計注文の注文明細を1つ減らす。数量1なら明細だけを削除する。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    # 先に明細の所属注文IDを確認する。
    # 店舗IDも条件に含め、他店舗の明細を操作できないようにする。
    detail_info = get_object_or_404(
        OrderDetail.objects.filter(
            order__store_id=store_id,
        ).only(
            "id",
            "order_id",
        ),
        pk=detail_id,
    )

    table_no = None

    with transaction.atomic():
        # 会計処理と同じ親注文を先にロックする。
        # 会計処理が先に完了した場合は、ここで会計済みと判定する。
        order = get_object_or_404(
            CustomerOrder.objects.select_for_update(),
            pk=detail_info.order_id,
            store_id=store_id,
        )

        table_no = order.table_no

        if order.is_checked_out:
            messages.error(
                request,
                "会計済みの注文は変更できません。",
            )
        else:
            # 親注文を確認した後で、対象明細をロックして再取得する。
            detail = get_object_or_404(
                OrderDetail.objects.select_for_update(),
                pk=detail_id,
                order=order,
            )

            if detail.quantity <= 1:
                # 注文明細だけを削除する。親のCustomerOrderは削除しない。
                detail.delete()
                messages.success(
                    request,
                    "注文商品を削除しました。",
                )
            else:
                detail.quantity -= 1
                detail.save(
                    update_fields=["quantity"],
                )
                messages.success(
                    request,
                    "注文数量を1つ減らしました。",
                )

    return redirect(
        f"{reverse('staff_order_detail')}?table={table_no}"
    )


@never_cache
@require_GET
def staff_order_complete(request):
    """数量変更完了画面を表示する。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    raw_table_no = request.GET.get("table", "")

    try:
        table_no = int(raw_table_no)

        if table_no < 1:
            raise ValueError

    except (TypeError, ValueError):
        messages.error(request, "テーブル番号が正しくありません。")
        return redirect("staff_order")

    return render(
        request,
        "customer/staff_order_complete.html",
        {
            "table_no": table_no,
        },
    )


@never_cache
@require_GET
def staff_logout_confirm(request):
    """店員のログアウト確認画面を表示する。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    return render(
        request,
        "customer/staff_logout.html",
    )


@never_cache
@require_POST
def staff_logout(request):
    """店員をログアウトさせる。"""

    profile, store_id, access_response = _check_staff_access(request)

    if access_response is not None:
        return access_response

    auth_logout(request)

    return redirect("staff_login")


@never_cache
@require_GET
def staff_list(request):
    """店長が自店舗の店員アカウント一覧を表示する。"""

    profile, access_response = _check_store_access(
        request,
        manager_only=True,
    )

    if access_response is not None:
        return access_response

    staff_members = (
        EmployeeProfile.objects
        .filter(
            role=EmployeeProfile.Role.STAFF,
            store_code=profile.store_code.strip(),
        )
        .select_related("user")
        .order_by("user__username")
    )

    return render(
        request,
        "staff_list.html",
        {
            "staff_members": staff_members,
            "store_code": profile.store_code.strip(),
            "manager_name": (
                profile.full_name.strip()
                or profile.user.get_username()
            ),
        },
    )


@never_cache
@require_http_methods(["GET", "POST"])
def staff_edit(request, employee_id):
    """店長が自店舗の店員の社員ID・氏名・パスワードを変更する。"""

    profile, access_response = _check_store_access(
        request,
        manager_only=True,
    )

    if access_response is not None:
        return access_response

    staff = _get_store_staff(profile, employee_id)
    errors = []

    if request.method == "POST":
        new_employee_id = request.POST.get("employee_id", "").strip()
        full_name = request.POST.get("staff_name", "").strip()
        new_password = request.POST.get("password", "")

        if not new_employee_id:
            errors.append("社員IDを入力してください。")
        elif len(new_employee_id) > 150:
            errors.append("社員IDは150文字以内で入力してください。")
        elif User.objects.filter(
            username=new_employee_id
        ).exclude(pk=staff.user.pk).exists():
            errors.append("この社員IDは既に使用されています。")

        if not full_name:
            errors.append("氏名を入力してください。")
        elif len(full_name) > 150:
            errors.append("氏名は150文字以内で入力してください。")

        if new_password:
            try:
                password_validation.validate_password(
                    new_password,
                    user=staff.user,
                )
            except ValidationError as error:
                errors.extend(error.messages)

        if not errors:
            staff.user.username = new_employee_id
            staff.user.save(update_fields=["username"])

            staff.full_name = full_name
            staff.save(update_fields=["full_name", "updated_at"])

            if new_password:
                staff.user.set_password(new_password)
                staff.user.save(update_fields=["password"])

            messages.success(
                request,
                "店員情報を変更しました。",
            )
            return redirect("staff_list")

    return render(
        request,
        "staff_edit.html",
        {
            "staff": staff,
            "staff_id": (
                request.POST.get("employee_id", staff.user.username)
                if request.method == "POST"
                else staff.user.username
            ),
            "staff_name": (
                request.POST.get("staff_name", staff.full_name)
                if request.method == "POST"
                else staff.full_name
            ),
            "errors": errors,
        },
    )


@never_cache
@require_POST
def staff_delete(request, employee_id):
    """店長が自店舗の店員アカウントを削除する。"""

    profile, access_response = _check_store_access(
        request,
        manager_only=True,
    )

    if access_response is not None:
        return access_response

    staff = _get_store_staff(profile, employee_id)
    staff_name = staff.full_name or staff.user.username

    staff.user.delete()

    messages.success(
        request,
        f"社員ID：{employee_id}（{staff_name}）を削除しました。",
    )

    return redirect("staff_list")
