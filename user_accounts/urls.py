
from django.urls import path

from . import views
from . import staff_views
from . import headquarters_manager_views


urlpatterns = [
    # 入口
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

    # 本社管理者：社員アカウント管理
    path(
        "headquarters/staff-menu",
        headquarters_manager_views.manager_menu,
        name="staff_menu",
    ),
    path(
        "headquarters/managers",
        headquarters_manager_views.manager_list,
        name="manager_list",
    ),
    path(
        "headquarters/managers/<str:employee_id>/edit",
        headquarters_manager_views.manager_edit,
        name="manager_edit",
    ),
    path(
        "headquarters/managers/<str:employee_id>/delete",
        headquarters_manager_views.manager_delete,
        name="manager_delete",
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

    # 店員専用：ログイン・注文管理・ログアウト
    path(
        "staff-login/",
        staff_views.staff_login,
        name="staff_login",
    ),
    path(
        "staff-order/",
        staff_views.staff_order,
        name="staff_order",
    ),
    path(
        "staff-order-detail/",
        staff_views.staff_order_detail,
        name="staff_order_detail",
    ),
    path(
        "staff-order-detail/<int:detail_id>/decrease/",
        staff_views.staff_order_decrease,
        name="staff_order_decrease",
    ),
    path(
        "staff-order-complete/",
        staff_views.staff_order_complete,
        name="staff_order_complete",
    ),
    path(
        "staff-logout-confirm/",
        staff_views.staff_logout_confirm,
        name="staff_logout_confirm",
    ),
    path(
        "staff-logout/",
        staff_views.staff_logout,
        name="staff_logout",
    ),

    # 店舗トップ・店員アカウント管理・店員一覧・在庫一覧・棚卸
    path(
        "store/top",
        views.store_top,
        name="store_top",
    ),
    path(
        "store/inventory-management",
        views.inventory_management,
        name="inventory_management",
    ),
    path(
        "store/staff-management",
        views.staff_management,
        name="staff_management",
    ),
    path(
        "store/staff-list",
        staff_views.staff_list,
        name="staff_list",
    ),
    path(
        "store/inventory",
        views.inventory_list,
        name="inventory_list",
    ),
    path(
        "store/inventory",
        views.inventory_list,
        name="stock_list",
    ),
    path(
        "store/stocktake",
        views.stocktake_register,
        name="stocktake_register",
    ),
    path(
        "store/stocktake",
        views.stocktake_register,
        name="stock_change",
    ),
    path(
        "store/stocktake/complete",
        views.stocktake_complete,
        name="stocktake_complete",
    ),

    # 店員アカウントの変更・削除
    path(
        "store/staff/<str:employee_id>/edit",
        staff_views.staff_edit,
        name="staff_edit",
    ),
    path(
        "store/staff/<str:employee_id>/delete",
        staff_views.staff_delete,
        name="staff_delete",
    ),

    # 在庫切れ予測・発注登録
    path(
        "store/stockout-prediction",
        views.stockout_prediction,
        name="stockout_prediction",
    ),
    path(
        "store/stockout-prediction/order-registration",
        views.stockout_order_registration,
        name="stockout_order_registration",
    ),
    path(
        "store/purchase-management",
        views.purchase_management,
        name="purchase_management",
    ),
    path(
        "store/order-registration",
        views.stockout_order_registration_page,
        name="stockout_order_registration_page",
    ),
    path(
        "store/order-registration/submit",
        views.stockout_order_submit,
        name="stockout_order_submit",
    ),
    path(
        "store/order-registration/complete",
        views.stockout_order_complete,
        name="stockout_order_complete",
    ),

    # 店長用・発注履歴／修正／取消
    path(
        "store/order-history",
        views.order_history,
        name="order_history",
    ),
    path(
        "store/order-history/<int:request_id>/edit",
        views.purchase_request_edit,
        name="purchase_request_edit",
    ),
    path(
        "store/order-history/<int:request_id>/cancel",
        views.purchase_request_cancel,
        name="purchase_request_cancel",
    ),

    # 店長用・差し戻し発注の確認／再発注
    path(
        "store/order-return/<int:request_id>",
        views.order_return_edit,
        name="order_return_edit",
    ),
    path(
        "store/order-return/complete",
        views.order_resubmit_complete,
        name="order_resubmit_complete",
    ),

    # 本社管理者
    path(
        "headquarters/top",
        views.headquarters_top,
        name="headquarters_top",
    ),
    path(
        "headquarters/master",
        views.headquarters_master,
        name="headquarters_master",
    ),
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

    # 本社管理者用・在庫メニュー
    path(
        "headquarters/stock",
        views.headquarters_stock,
        name="headquarters_stock",
    ),

    # 本社側・発注管理
    path(
        "headquarters/orders",
        views.order,
        name="order",
    ),
    path(
        "headquarters/orders/<int:request_id>",
        views.order_detail,
        name="order_detail",
    ),
    path(
        "headquarters/orders/complete",
        views.order_complete,
        name="order_complete",
    ),
    path(
        "headquarters/orders/history",
        views.order_history2,
        name="order_history2",
    ),

    # 店長・本社管理者共通：注文データ
    path(
        "order-data",
        views.order_data,
        name="order_data",
    ),

    # QRコードから開くお客様用画面
    path(
        "order/<int:store_id>/<int:table_no>",
        views.customer_order,
        name="customer_order",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/menu",
        views.customer_menu,
        name="customer_menu",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/confirm",
        views.customer_order_confirm,
        name="customer_order_confirm",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/submit",
        views.customer_order_submit,
        name="customer_order_submit",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/complete/<int:order_id>",
        views.customer_order_complete,
        name="customer_order_complete",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/history",
        views.customer_order_history,
        name="customer_order_history",
    ),

    # お客様用・会計内容画面
    path(
        "order/<int:store_id>/<int:table_no>/checkout",
        views.customer_checkout_page,
        name="customer_checkout_page",
    ),

    # お客様用・会計確定処理
    path(
        "order/<int:store_id>/<int:table_no>/checkout",
        views.customer_checkout_page,
        name="customer_checkout_page",
    ),
    path(
        "order/<int:store_id>/<int:table_no>/checkout/complete",
        views.customer_checkout,
        name="customer_checkout",
    ),
]
