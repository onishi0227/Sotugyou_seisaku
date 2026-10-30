
from django.contrib import messages
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import EmployeeProfile
from .views import _check_store_access


User = get_user_model()


def _get_store_staff(profile, employee_id):
    """店長と同じ店舗に所属する店員だけを取得する。"""

    return get_object_or_404(
        EmployeeProfile.objects.select_related("user"),
        user__username=employee_id,
        role=EmployeeProfile.Role.STAFF,
        store_code=profile.store_code.strip(),
    )


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

        # 社員IDの入力チェック
        if not new_employee_id:
            errors.append("社員IDを入力してください。")
        elif len(new_employee_id) > 150:
            errors.append("社員IDは150文字以内で入力してください。")
        elif User.objects.filter(
            username=new_employee_id
        ).exclude(pk=staff.user.pk).exists():
            errors.append("この社員IDは既に使用されています。")

        # 氏名の入力チェック
        if not full_name:
            errors.append("氏名を入力してください。")
        elif len(full_name) > 150:
            errors.append("氏名は150文字以内で入力してください。")

        # パスワードの入力チェック
        if new_password:
            try:
                password_validation.validate_password(
                    new_password,
                    user=staff.user,
                )
            except ValidationError as error:
                errors.extend(error.messages)

        if not errors:
            # 社員IDを変更
            staff.user.username = new_employee_id
            staff.user.save(update_fields=["username"])

            # 氏名を変更
            staff.full_name = full_name
            staff.save(update_fields=["full_name", "updated_at"])

            # パスワードが入力されている場合だけ変更
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

    # EmployeeProfileとUserはOneToOneField・CASCADEで連動して削除される。
    staff.user.delete()

    messages.success(
        request,
        f"社員ID：{employee_id}（{staff_name}）を削除しました。",
    )

    return redirect("staff_list")
