
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

    # 現在有効なログインセッション
    active_session_key = models.CharField(
        max_length=40,
        blank=True,
        default="",
        verbose_name="有効なログインセッション",
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


class MenuItem(models.Model):
    """店舗ごとのメニュー商品を管理するモデル。"""

    store_id = models.PositiveIntegerField(
        db_index=True,
        verbose_name="店舗ID",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="商品名",
    )

    description = models.TextField(
        blank=True,
        verbose_name="商品説明",
    )

    price = models.PositiveIntegerField(
        verbose_name="価格（円）",
    )

    is_available = models.BooleanField(
        default=True,
        verbose_name="販売中",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="表示順",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="登録日時",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時",
    )

    class Meta:
        verbose_name = "メニュー商品"
        verbose_name_plural = "メニュー商品"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name}（店舗ID：{self.store_id}）"
