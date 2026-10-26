from django.urls import path

from . import views


urlpatterns = [
    # S-00 入口
    path("", views.entry_view, name="entry"),
    path("staff", views.entry_view, name="staff_entry"),

    # ログイン先の選択
    path(
        "entry/store",
        views.select_store_portal,
        name="select_store_portal",
    ),
    path(
        "entry/headquarters",
        views.select_headquarters_portal,
        name="select_headquarters_portal",
    ),

    # アカウント作成・ログイン・ログアウト
    path(
        "account-register",
        views.account_register,
        name="account_register",
    ),
    path("login", views.login_view, name="login"),
    path(
        "login-success",
        views.login_success,
        name="login_success",
    ),
    path("logout", views.logout_view, name="logout"),

    # S-08 店舗トップ画面
    path(
        "store/top",
        views.store_top,
        name="store_top",
    ),

    # S-11 在庫一覧画面
    path(
        "store/inventory",
        views.inventory_list,
        name="inventory_list",
    ),

    # S-12 棚卸登録画面
    path(
        "store/stocktake",
        views.stocktake_register,
        name="stocktake_register",
    ),

    # S-12 棚卸登録完了画面
    path(
        "store/stocktake/complete",
        views.stocktake_complete,
        name="stocktake_complete",
    ),

    # S-16 本社管理者トップ画面
    path(
        "headquarters/top",
        views.headquarters_top,
        name="headquarters_top",
    ),

    # S-21 本社マスタ管理画面
    path(
        "headquarters/master",
        views.headquarters_master,
        name="headquarters_master",
    ),

    # 本社マスタ登録画面
    path(
        "headquarters/master/ingredients",
        views.ingredient_register,
        name="ingredient_register",
    ),
    path(
        "headquarters/master/menus",
        views.menu_register,
        name="menu_register",
    ),
    path(
        "headquarters/master/recipes",
        views.recipe_register,
        name="recipe_register",
    ),

    # QRコードから開くお客様用画面
    path(
        "order/<int:store_id>/<int:table_no>",
        views.customer_order,
        name="customer_order",
    ),

    # お客様用の商品一覧画面
    path(
        "order/<int:store_id>/<int:table_no>/menu",
        views.customer_menu,
        name="customer_menu",
    ),
]