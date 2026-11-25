
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from user_accounts.models import (
    EmployeeProfile,
    PurchaseRequest,
    PurchaseRequestDetail,
    Stocktake,
)
from user_accounts.views import (
    _build_stockout_prediction_rows,
    _get_store_id_from_code,
)


class Command(BaseCommand):
    help = "在庫切れ予測に基づいて発注申請を自動作成します。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="申請を作成せず、作成予定の内容だけを表示します。",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        managers = (
            EmployeeProfile.objects
            .filter(
                role=EmployeeProfile.Role.STORE_MANAGER,
                user__is_active=True,
            )
            .exclude(store_code="")
            .select_related("user")
            .order_by("store_code", "id")
        )

        # 店舗コードごとに最初の店長プロフィールを使用する
        store_managers = {}
        for manager in managers:
            store_managers.setdefault(manager.store_code, manager)

        created_count = 0
        skipped_count = 0

        for store_code, manager in store_managers.items():
            store_id = _get_store_id_from_code(store_code)

            if store_id is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"{store_code}: 店舗IDを取得できないためスキップしました。"
                    )
                )
                continue

            rows = _build_stockout_prediction_rows(
                store_code,
                store_id,
            )

            targets = []

            for row in rows:
                if not row.get("urgent", False):
                    continue

                if row.get("missing_stock", False):
                    continue

                if not row.get("needs_order", False):
                    continue

                ingredient = row["ingredient"]
                quantity = Decimal(
                    row["recommended_quantity_raw"]
                )

                if quantity <= 0:
                    continue

                targets.append((ingredient, quantity))

            if not targets:
                self.stdout.write(
                    f"{store_code}: 自動発注の対象はありません。"
                )
                continue

            with transaction.atomic():
                # 同じ店舗の同時実行による重複をできるだけ防ぐ
                EmployeeProfile.objects.select_for_update().get(
                    pk=manager.pk
                )

                request_items = []

                for ingredient, quantity in targets:
                    existing_details = (
                        PurchaseRequestDetail.objects
                        .filter(
                            ingredient=ingredient,
                            purchase_request__store_code=store_code,
                        )
                        .select_related("purchase_request")
                        .order_by("-purchase_request__requested_at")
                    )

                    should_skip = False

                    for detail in existing_details:
                        purchase_request = detail.purchase_request

                        if purchase_request.status == PurchaseRequest.Status.PENDING:
                            should_skip = True
                            break

                        if purchase_request.status == PurchaseRequest.Status.REJECTED:
                            if not purchase_request.return_handled:
                                should_skip = True
                                break

                        if purchase_request.status == PurchaseRequest.Status.APPROVED:
                            latest_stocktake = (
                                Stocktake.objects
                                .filter(
                                    store_code=store_code,
                                    ingredient=ingredient,
                                )
                                .order_by(
                                    "-stocktake_date",
                                    "-id",
                                )
                                .first()
                            )

                            # 確定後に新しい棚卸記録がなければ再申請しない
                            if (
                                latest_stocktake is None
                                or latest_stocktake.stocktake_date
                                <= purchase_request.requested_at.date()
                            ):
                                should_skip = True
                                break

                    if should_skip:
                        skipped_count += 1
                        continue

                    request_items.append((ingredient, quantity))

                if not request_items:
                    self.stdout.write(
                        f"{store_code}: 既存申請があるため作成しませんでした。"
                    )
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[確認のみ] {store_code}: "
                            f"{len(request_items)}件の申請を作成予定"
                        )
                    )
                    for ingredient, quantity in request_items:
                        self.stdout.write(
                            f"  - {ingredient.name}: {quantity} {ingredient.unit}"
                        )
                    continue

                purchase_request = PurchaseRequest.objects.create(
                    store_code=store_code,
                    requested_by=manager,
                    status=PurchaseRequest.Status.PENDING,
                    note="在庫切れ予測に基づく自動発注申請",
                )

                PurchaseRequestDetail.objects.bulk_create(
                    [
                        PurchaseRequestDetail(
                            purchase_request=purchase_request,
                            ingredient=ingredient,
                            quantity=quantity,
                            recommended_quantity=quantity,
                            status=PurchaseRequestDetail.Status.PENDING,
                        )
                        for ingredient, quantity in request_items
                    ]
                )

                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{store_code}: 発注申請を自動作成しました。"
                        f"（{len(request_items)}食材）"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "確認のみで終了しました。データベースへの登録はしていません。"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"処理完了：申請作成 {created_count}件、"
                    f"重複等によるスキップ {skipped_count}食材"
                )
            )
