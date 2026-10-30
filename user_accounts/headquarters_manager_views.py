
from django.contrib import messages
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import EmployeeProfile
from .views import _check_headquarters_access

User = get_user_model()


def _get_store_manager(employee_id):
    """
    社員IDを指定して、店長アカウントを取得する。
    店員アカウントは取得対象にしない。
    """
    return get_object_or_404(
        EmployeeProfile.objects.select_related("user"),
        user__username=employee_id,
        role=EmployeeProfile.Role.STORE_MANAGER,
    )


@never_cache
@require_GET
def manager_menu(request):
    """
    本社管理者向けの社員アカウント管理メニューを表示する。
    """
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    return render(request, "staff_menu.html")


@never_cache
@require_GET
def manager_list(request):
    """
    全店舗の店長アカウントを一覧表示する。
    """
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    managers = (
        EmployeeProfile.objects
        .filter(role=EmployeeProfile.Role.STORE_MANAGER)
        .select_related("user")
        .order_by("store_code", "user__username")
    )

    return render(
        request,
        "staff_manager_list.html",
        {
            "managers": managers,
            "is_headquarters_manager": True,
        },
    )


@never_cache
@require_http_methods(["GET", "POST"])
def manager_edit(request, employee_id):
    """
    店長アカウントの情報を変更する。

    変更可能な項目：
    ・社員ID
    ・氏名
    ・所属店舗コード
    ・パスワード（入力された場合のみ変更）
    """
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    manager = _get_store_manager(employee_id)

    errors = []

    staff_id = manager.user.username
    staff_name = manager.full_name
    store_code = manager.store_code or ""

    if request.method == "POST":
        new_employee_id = request.POST.get("employee_id", "").strip()
        new_staff_name = request.POST.get("staff_name", "").strip()
        new_store_code = request.POST.get("store_code", "").strip()
        new_password = request.POST.get("password", "")

        # 入力チェック
        if not new_employee_id:
            errors.append("社員IDを入力してください。")

        if not new_staff_name:
            errors.append("氏名を入力してください。")

        if not new_store_code:
            errors.append("所属店舗コードを入力してください。")

        # 社員IDの重複チェック
        if new_employee_id:
            if User.objects.filter(username=new_employee_id).exclude(
                pk=manager.user.pk
            ).exists():
                errors.append("この社員IDはすでに使用されています。")

        # パスワードが入力された場合のみチェックする
        if new_password:
            try:
                password_validation.validate_password(
                    new_password,
                    manager.user,
                )
            except ValidationError as error:
                errors.extend(error.messages)

        # エラーがなければ更新
        if not errors:
            try:
                with transaction.atomic():
                    manager.user.username = new_employee_id

                    if new_password:
                        manager.user.set_password(new_password)

                    manager.user.save()

                    manager.full_name = new_staff_name
                    manager.store_code = new_store_code
                    manager.save()

                messages.success(
                    request,
                    "店長アカウントを変更しました。",
                )

                # 更新成功後、変更完了画面を表示する
                return render(
                    request,
                    "staff_update_complete.html",
                )

            except Exception:
                errors.append(
                    "アカウントの変更に失敗しました。入力内容を確認してください。"
                )

        # 入力エラーがある場合は、入力内容を保持する
        staff_id = new_employee_id
        staff_name = new_staff_name
        store_code = new_store_code

    return render(
        request,
        "staff_update.html",
        {
            "staff": manager,
            "staff_id": staff_id,
            "staff_name": staff_name,
            "store_code": store_code,
            "errors": errors,
            "is_headquarters_manager": True,
        },
    )


@never_cache
@require_POST
def manager_delete(request, employee_id):
    """
    店長アカウントを削除する。
    """
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    manager = _get_store_manager(employee_id)

    manager.user.delete()

    messages.success(
        request,
        f"社員ID「{employee_id}」の店長アカウントを削除しました。",
    )

    return redirect("manager_list")
