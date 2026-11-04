
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class EmployeeProfile(models.Model):
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
    CATEGORY_CHOICES = [
        ("主食", "主食"),
        ("主菜", "主菜"),
        ("副菜", "副菜"),
        ("デザート", "デザート"),
        ("ドリンク", "ドリンク"),
    ]

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
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="主食",
        verbose_name="カテゴリ",
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


class Ingredient(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="食材名",
    )
    unit = models.CharField(
        max_length=30,
        verbose_name="単位",
    )
    delivery_days = models.PositiveIntegerField(
        verbose_name="納品日数",
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
        verbose_name = "食材"
        verbose_name_plural = "食材"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}（{self.unit}）"


class Recipe(models.Model):
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="メニュー",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipes",
        verbose_name="食材",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        verbose_name="使用量",
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
        verbose_name = "レシピ"
        verbose_name_plural = "レシピ"
        ordering = ["menu_item", "ingredient"]
        constraints = [
            models.UniqueConstraint(
                fields=["menu_item", "ingredient"],
                name="unique_recipe_menu_ingredient",
            ),
        ]

    def __str__(self):
        return (
            f"{self.menu_item.name}："
            f"{self.ingredient.name} "
            f"{self.quantity}{self.ingredient.unit}"
        )


class Stocktake(models.Model):
    """店舗ごとの棚卸結果を保存する。"""

    store_code = models.CharField(
        max_length=30,
        db_index=True,
        verbose_name="店舗コード",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="stocktakes",
        verbose_name="食材",
    )
    stocktake_date = models.DateField(
        verbose_name="棚卸日",
    )
    actual_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name="実在庫",
    )
    recorded_by = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="stocktake_records",
        verbose_name="棚卸担当者",
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
        verbose_name = "棚卸結果"
        verbose_name_plural = "棚卸結果"
        ordering = ["-stocktake_date", "ingredient__name"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "store_code",
                    "ingredient",
                    "stocktake_date",
                ],
                name="uniq_stocktake_store_ing_date",
            ),
        ]

    def __str__(self):
        return (
            f"{self.store_code}：{self.ingredient.name} "
            f"{self.actual_quantity}{self.ingredient.unit} "
            f"（{self.stocktake_date}）"
        )


class TheoreticalStock(models.Model):
    """店舗・食材ごとの理論在庫を保存する。"""

    store_code = models.CharField(
        max_length=30,
        db_index=True,
        verbose_name="店舗コード",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="theoretical_stocks",
        verbose_name="食材",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name="理論在庫",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時",
    )

    class Meta:
        verbose_name = "理論在庫"
        verbose_name_plural = "理論在庫"
        ordering = ["store_code", "ingredient__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["store_code", "ingredient"],
                name="uniq_store_ingredient_theory",
            ),
        ]

    def __str__(self):
        return (
            f"{self.store_code}：{self.ingredient.name} "
            f"{self.quantity}{self.ingredient.unit}"
        )


class CustomerOrder(models.Model):
    """お客様の注文情報を保存する。"""

    store_id = models.PositiveIntegerField(
        db_index=True,
        verbose_name="店舗ID",
    )
    table_no = models.PositiveIntegerField(
        verbose_name="テーブル番号",
    )
    ordered_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="注文日時",
    )

    class Meta:
        verbose_name = "注文"
        verbose_name_plural = "注文"
        ordering = ["-ordered_at", "-id"]

    def __str__(self):
        return (
            f"注文ID：{self.pk} "
            f"（店舗ID：{self.store_id}、"
            f"テーブル：{self.table_no}）"
        )


class OrderDetail(models.Model):
    """注文に含まれるメニューと注文数量を保存する。"""

    order = models.ForeignKey(
        CustomerOrder,
        on_delete=models.CASCADE,
        related_name="details",
        verbose_name="注文",
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name="order_details",
        verbose_name="メニュー",
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="注文数量",
    )

    class Meta:
        verbose_name = "注文明細"
        verbose_name_plural = "注文明細"
        ordering = ["order_id", "id"]

    def __str__(self):
        return f"{self.menu_item.name} "


class PurchaseRequest(models.Model):
    """店舗から本社への発注申請を保存する。"""

    class Status(models.TextChoices):
        PENDING = "pending", "未確認"
        REJECTED = "rejected", "差し戻し"
        APPROVED = "approved", "確定"
        CANCELLED = "cancelled", "取消"

    store_code = models.CharField(
        max_length=30,
        db_index=True,
        verbose_name="店舗コード",
    )
    requested_by = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
        verbose_name="申請者",
    )
    requested_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="申請日時",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="申請状態",
    )
    note = models.TextField(
        blank=True,
        verbose_name="本社へのメモ",
    )
    headquarters_comment = models.TextField(
        blank=True,
        verbose_name="本社コメント",
    )
    return_handled = models.BooleanField(
        default=False,
        verbose_name="差し戻し対応済み",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時",
    )

    class Meta:
        verbose_name = "発注申請"
        verbose_name_plural = "発注申請"
        ordering = ["-requested_at", "-id"]

    def __str__(self):
        return f"発注申請 #{self.pk} - {self.store_code}"


class PurchaseRequestDetail(models.Model):
    """発注申請に含まれる食材と申請数量を保存する。"""

    class Status(models.TextChoices):
        PENDING = "pending", "未処理"
        REJECTED = "rejected", "差し戻し"
        APPROVED = "approved", "確定"

    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="details",
        verbose_name="発注申請",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="purchase_request_details",
        verbose_name="食材",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="申請数量",
    )
    recommended_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        verbose_name="申請時推奨数量",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="明細状態",
    )

    class Meta:
        verbose_name = "発注申請明細"
        verbose_name_plural = "発注申請明細"
        ordering = ["purchase_request_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_request", "ingredient"],
                name="unique_purchase_request_ingredient",
            ),
        ]

    def __str__(self):
        return (
            f"{self.ingredient.name} "
            f"{self.quantity}{self.ingredient.unit}"
        )
