
from django.urls import path
from . import views


urlpatterns = [
    path(
        "account-register",
        views.account_register,
        name="account_register",
    ),
    path(
        "login",
        views.login_view,
        name="login",
    ),
    path(
        "login-success",
        views.login_success,
        name="login_success",
    ),
    path(
        "logout",
        views.logout_view,
        name="logout",
    ),
]