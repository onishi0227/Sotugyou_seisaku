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
]