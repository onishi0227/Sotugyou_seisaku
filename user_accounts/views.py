from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AccountCreationForm, IngredientForm, MenuItemForm
from .models import (
    EmployeeProfile,
    Ingredient,
    MenuItem,
    Recipe,
    Stocktake,
    TheoreticalStock,
)


LOGIN_PORTAL_SESSION_KEY = "login_portal"

STORE_PORTAL = "store"
HEADQUARTERS_PORTAL = "headquarters"


def _format_quantity(value):
    """数量を小数第2位までに丸め、不要な末尾の0を取り除く。"""
    quantity = Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if quantity == 0:
        return "0"

    formatted = format(quantity, "f")

    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")

    return formatted


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

    return HttpResponseForbidden(
        "有効な権限が設定されていません。"
    )


def _check_headquarters_access(request):
    """本社管理者としてマスタ管理機能を利用できるか確認する。"""
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
            "本社管理者だけがマスタ管理機能を利用できます。"
        )

    return None


def _check_store_access(request, manager_only=False):
    """店舗側のログイン状態と権限を確認する。"""
    if not request.user.is_authenticated:
        return None, redirect("entry")

    profile = _get_employee_profile(request.user)

    if manager_only:
        allowed_roles = (EmployeeProfile.Role.STORE_MANAGER,)
    else:
        allowed_roles = (
            EmployeeProfile.Role.STORE_MANAGER,
            EmployeeProfile.Role.STAFF,
        )

    if (
        profile is None
        or profile.role not in allowed_roles
        or request.session.get(LOGIN_PORTAL_SESSION_KEY) != STORE_PORTAL
    ):
        return None, HttpResponseForbidden(
            "この画面を利用する権限がありません。"
        )

    if not profile.store_code.strip():
        return None, HttpResponseForbidden(
            "所属店舗が設定されていません。管理者に確認してください。"
        )

    return profile, None


def _build_recipe_groups(menus):
    """登録済みレシピをメニュー単位にまとめ、画面表示用データを作る。"""
    groups = []

    recipes = (
        Recipe.objects.filter(menu_item__in=menus)
        .select_related("menu_item", "ingredient")
        .order_by("menu_item_id", "ingredient__name")
    )

    grouped = {}

    for recipe in recipes:
        grouped.setdefault(recipe.menu_item_id, []).append(
            {
                "ingredient_id": recipe.ingredient_id,
                "name": recipe.ingredient.name,
                "amount": str(recipe.quantity),
                "unit": recipe.ingredient.unit,
            }
        )

    for menu in menus:
        rows = grouped.get(menu.pk, [])

        if rows:
            groups.append(
                {
                    "menu_id": menu.pk,
                    "menu_name": menu.name,
                    "store_id": menu.store_id,
                    "ingredients": rows,
                }
            )

    return groups


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

                target_role_label = (
                    "店長" if can_choose_store else "店員"
                )

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
            if (
                profile.role
                != EmployeeProfile.Role.HEADQUARTERS_ADMIN
            ):
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

    return render(
        request,
        "store.html",
        {
            "is_store_manager": (
                profile.role == EmployeeProfile.Role.STORE_MANAGER
            ),
        },
    )


@never_cache
@require_GET
def inventory_list(request):
    """S-11 自店舗の最終棚卸結果を表示する。"""
    profile, access_response = _check_store_access(request)

    if access_response is not None:
        return access_response

    store_code = profile.store_code.strip()
    latest_by_ingredient = {}

    latest_records = (
        Stocktake.objects.filter(store_code=store_code)
        .select_related("ingredient")
        .order_by(
            "ingredient_id",
            "-stocktake_date",
            "-updated_at",
        )
    )

    for record in latest_records:
        latest_by_ingredient.setdefault(
            record.ingredient_id,
            record,
        )

    inventory_rows = [
        {
            "ingredient": ingredient,
            "stocktake": latest_by_ingredient.get(ingredient.pk),
        }
        for ingredient in Ingredient.objects.order_by("name")
    ]

    return render(
        request,
        "stock_list.html",
        {
            "inventory_rows": inventory_rows,
            "store_code": store_code,
        },
    )


@never_cache
@require_http_methods(["GET", "POST"])
def stocktake_register(request):
    """店長が実在庫を登録・修正する。0も登録できる。"""
    profile, access_response = _check_store_access(
        request,
        manager_only=True,
    )

    if access_response is not None:
        return access_response

    store_code = profile.store_code.strip()
    today = timezone.localdate()

    ingredients = list(Ingredient.objects.order_by("name"))

    today_records = {
        record.ingredient_id: record
        for record in Stocktake.objects.filter(
            store_code=store_code,
            stocktake_date=today,
        ).select_related("ingredient")
    }

    quantities = {
        ingredient.pk: (
            _format_quantity(
                today_records[ingredient.pk].actual_quantity
            )
            if ingredient.pk in today_records
            else ""
        )
        for ingredient in ingredients
    }

    errors = []

    if request.method == "POST":
        validated_rows = []
        quantities = {}

        for ingredient in ingredients:
            field_name = f"quantity_{ingredient.pk}"
            raw_quantity = request.POST.get(
                field_name,
                "",
            ).strip()

            quantities[ingredient.pk] = raw_quantity

            if raw_quantity == "":
                errors.append(
                    f"{ingredient.name}の実在庫数を入力してください。"
                )
                continue

            try:
                quantity = Decimal(raw_quantity)

                if (
                    not quantity.is_finite()
                    or quantity < Decimal("0")
                    or quantity >= Decimal("1000000000")
                    or quantity.as_tuple().exponent < -2
                ):
                    raise InvalidOperation

            except (InvalidOperation, ValueError):
                errors.append(
                    f"{ingredient.name}は0以上、小数第2位までの数値を入力してください。"
                )
                continue

            validated_rows.append((ingredient, quantity))

        if not ingredients:
            errors.append(
                "登録されている食材がないため、棚卸を登録できません。"
            )

        if not errors:
            with transaction.atomic():
                for ingredient, quantity in validated_rows:
                    Stocktake.objects.update_or_create(
                        store_code=store_code,
                        ingredient=ingredient,
                        stocktake_date=today,
                        defaults={
                            "actual_quantity": quantity,
                            "recorded_by": profile,
                        },
                    )

                    TheoreticalStock.objects.get_or_create(
                        store_code=store_code,
                        ingredient=ingredient,
                        defaults={
                            "quantity": quantity,
                        },
                    )

            return redirect(
                f"{reverse('stocktake_complete')}?saved=1"
            )

    for ingredient in ingredients:
        ingredient.input_quantity = quantities.get(
            ingredient.pk,
            "",
        )

    context = {
        "store_code": store_code,
        "today": today,
        "manager_name": (
            profile.full_name.strip()
            or profile.user.get_username()
        ),
        "ingredients": ingredients,
        "errors": errors,
        "has_ingredients": bool(ingredients),
        "is_editing": bool(today_records),
    }

    return render(
        request,
        "stock_change.html",
        context,
    )


@never_cache
@require_GET
def stocktake_complete(request):
    """棚卸登録完了画面を表示する。"""
    profile, access_response = _check_store_access(
        request,
        manager_only=True,
    )

    if access_response is not None:
        return access_response

    if request.GET.get("saved") != "1":
        return redirect("stocktake_register")

    return render(
        request,
        "stock_change_complete.html",
        {
            "manager_name": (
                profile.full_name.strip()
                or profile.user.get_username()
            ),
            "today": timezone.localdate(),
        },
    )


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
    """本社管理者用マスタ管理画面を表示する。"""
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    return render(request, "master.html")


@never_cache
@require_http_methods(["GET", "POST"])
def ingredient_register(request):
    """本社管理者が食材を登録する。"""
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    if request.method == "POST":
        form = IngredientForm(request.POST)

        if form.is_valid():
            form.save()

            return render(
                request,
                "ingredient_register.html",
                {
                    "form": IngredientForm(),
                    "success_message": "食材を登録しました。",
                },
            )
    else:
        form = IngredientForm()

    return render(
        request,
        "ingredient_register.html",
        {"form": form},
    )


@never_cache
@require_http_methods(["GET", "POST"])
def menu_register(request):
    """本社管理者がメニュー商品を登録する。"""
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    if request.method == "POST":
        form = MenuItemForm(request.POST)

        if form.is_valid():
            form.save()

            return render(
                request,
                "menu_register.html",
                {
                    "form": MenuItemForm(),
                    "success_message": "メニューを登録しました。",
                },
            )
    else:
        form = MenuItemForm()

    return render(
        request,
        "menu_register.html",
        {"form": form},
    )


@never_cache
@require_http_methods(["GET", "POST"])
def recipe_register(request):
    """本社管理者がレシピを登録・変更・削除する。"""
    access_response = _check_headquarters_access(request)

    if access_response is not None:
        return access_response

    menus = list(
        MenuItem.objects.order_by("store_id", "sort_order", "name")
    )
    ingredients = list(Ingredient.objects.order_by("name"))

    # 登録済みレシピの削除
    if (
        request.method == "POST"
        and request.POST.get("action") == "delete"
    ):
        raw_menu_id = request.POST.get(
            "menu_item_id",
            "",
        ).strip()

        try:
            menu_id = int(raw_menu_id)
        except (TypeError, ValueError):
            return redirect(
                f"{reverse('recipe_register')}?deleted=invalid"
            )

        menu_item = next(
            (menu for menu in menus if menu.pk == menu_id),
            None,
        )

        if menu_item is None:
            return redirect(
                f"{reverse('recipe_register')}?deleted=invalid"
            )

        with transaction.atomic():
            deleted_count, _ = Recipe.objects.filter(
                menu_item=menu_item
            ).delete()

        delete_status = "1" if deleted_count else "0"

        return redirect(
            f"{reverse('recipe_register')}?deleted={delete_status}"
        )

    selected_menu_id = ""
    initial_rows = []
    errors = []
    success_message = None
    is_editing = False

    if request.method == "POST":
        raw_menu_id = request.POST.get(
            "menu_item_id",
            "",
        ).strip()

        selected_menu_id = raw_menu_id
        menu_item = None

        if raw_menu_id:
            try:
                menu_id_number = int(raw_menu_id)
                menu_item = next(
                    (
                        menu
                        for menu in menus
                        if menu.pk == menu_id_number
                    ),
                    None,
                )
            except (TypeError, ValueError):
                menu_item = None

        if menu_item is None:
            errors.append("メニューを選択してください。")
        else:
            selected_menu_id = menu_item.pk
            is_editing = Recipe.objects.filter(
                menu_item=menu_item
            ).exists()

        ingredient_ids = request.POST.getlist("ingredient_id[]")
        quantities = request.POST.getlist("quantity[]")

        ingredient_by_id = {
            ingredient.pk: ingredient
            for ingredient in ingredients
        }

        cleaned_rows = []
        seen_ingredient_ids = set()

        if (
            not ingredient_ids
            or len(ingredient_ids) != len(quantities)
        ):
            errors.append("食材と使用量を入力してください。")

        for raw_ingredient_id, raw_quantity in zip(
            ingredient_ids,
            quantities,
        ):
            raw_ingredient_id = raw_ingredient_id.strip()
            raw_quantity = raw_quantity.strip()

            ingredient = None
            quantity = None

            if not raw_ingredient_id or not raw_quantity:
                errors.append("食材名と使用量を入力してください。")
            else:
                try:
                    ingredient_id = int(raw_ingredient_id)
                    ingredient = ingredient_by_id.get(ingredient_id)
                except (TypeError, ValueError):
                    ingredient = None

                if ingredient is None:
                    errors.append(
                        "登録済みの食材を選択してください。"
                    )
                elif ingredient.pk in seen_ingredient_ids:
                    errors.append(
                        "同じ食材は1つのレシピに重複して登録できません。"
                    )
                else:
                    seen_ingredient_ids.add(ingredient.pk)

                # 使用量は0.01以上、小数第2位までに制限する。
                try:
                    quantity = Decimal(raw_quantity)

                    if (
                        not quantity.is_finite()
                        or quantity < Decimal("0.01")
                        or quantity.as_tuple().exponent < -2
                        or quantity >= Decimal("1000000000")
                    ):
                        raise InvalidOperation

                except (InvalidOperation, ValueError):
                    quantity = None
                    errors.append(
                        "使用量は0.01以上、小数第2位までの数値を入力してください。"
                    )

            initial_rows.append(
                {
                    "ingredient_id": raw_ingredient_id,
                    "amount": raw_quantity,
                    "unit": ingredient.unit if ingredient else "",
                }
            )

            if ingredient is not None and quantity is not None:
                cleaned_rows.append((ingredient, quantity))

        if not initial_rows:
            errors.append("食材を1つ以上追加してください。")

        if menu_item is not None and not errors:
            was_existing = Recipe.objects.filter(
                menu_item=menu_item
            ).exists()

            ingredient_ids_to_keep = [
                ingredient.pk
                for ingredient, _ in cleaned_rows
            ]

            with transaction.atomic():
                Recipe.objects.filter(
                    menu_item=menu_item
                ).exclude(
                    ingredient_id__in=ingredient_ids_to_keep
                ).delete()

                for ingredient, quantity in cleaned_rows:
                    Recipe.objects.update_or_create(
                        menu_item=menu_item,
                        ingredient=ingredient,
                        defaults={"quantity": quantity},
                    )

            if not was_existing:
                return redirect(
                    f"{reverse('recipe_register')}?saved=created"
                )

            return redirect(
                f"{reverse('recipe_register')}?menu_item_id={menu_item.pk}"
                f"&saved=updated"
            )

    else:
        raw_selected_menu_id = request.GET.get(
            "menu_item_id",
            "",
        ).strip()

        if raw_selected_menu_id:
            try:
                menu_id_number = int(raw_selected_menu_id)
                selected_menu = next(
                    (
                        menu
                        for menu in menus
                        if menu.pk == menu_id_number
                    ),
                    None,
                )
            except (TypeError, ValueError):
                selected_menu = None

            if selected_menu is not None:
                selected_menu_id = selected_menu.pk

                saved_recipes = (
                    Recipe.objects.filter(menu_item=selected_menu)
                    .select_related("ingredient")
                    .order_by("ingredient__name")
                )

                initial_rows = [
                    {
                        "ingredient_id": recipe.ingredient_id,
                        "amount": str(recipe.quantity),
                        "unit": recipe.ingredient.unit,
                    }
                    for recipe in saved_recipes
                ]

                is_editing = bool(initial_rows)

        saved = request.GET.get("saved")

        if saved == "created":
            success_message = "レシピを登録しました。"
        elif saved == "updated":
            success_message = "レシピを変更しました。"

        deleted = request.GET.get("deleted")

        if deleted == "1":
            success_message = "レシピを削除しました。"
        elif deleted == "0":
            errors.append("削除対象のレシピが見つかりませんでした。")
        elif deleted == "invalid":
            errors.append("削除するメニューの指定が正しくありません。")

    recipe_groups = _build_recipe_groups(menus)

    context = {
        "menus": menus,
        "ingredients": ingredients,
        "recipe_groups": recipe_groups,
        "selected_menu_id": selected_menu_id,
        "initial_rows": initial_rows,
        "is_editing": is_editing,
        "errors": errors,
        "success_message": success_message,
    }

    return render(
        request,
        "recipe_register.html",
        context,
    )


@require_GET
def customer_order(request, store_id, table_no):
    """QRコードから開くお客様用画面。ログインは不要。"""
    request.session["store_id"] = store_id
    request.session["table_no"] = table_no

    return render(
        request,
        "customer.html",
        {
            "store_id": store_id,
            "table_no": table_no,
        },
    )


@require_GET
def customer_menu(request, store_id, table_no):
    """店舗・テーブルに対応したメニュー商品一覧を表示する。"""
    request.session["store_id"] = store_id
    request.session["table_no"] = table_no

    products = MenuItem.objects.filter(
        store_id=store_id,
        is_available=True,
    )

    return render(
        request,
        "product_list.html",
        {
            "store_id": store_id,
            "table_no": table_no,
            "products": products,
        },
    )


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