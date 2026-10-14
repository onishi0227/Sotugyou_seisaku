from django.conf import settings
from django.db import models


class EmployeeProfile(models.Model):
    """社員の氏名・権限・所属店舗を管理するモデル。"""

    class Role(models.TextChoices):
        HEADQUARTERS_ADMIN = "hq_admin", "本社管理者"
        STORE_MANAGER = "store_manager", "店長"
        STAFF = "staff", "店員"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name="ユーザー",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name="権限",
    )

    full_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="氏名",
    )

    store_code = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="所属店舗コード",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時",
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"