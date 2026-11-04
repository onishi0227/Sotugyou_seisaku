
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from user_accounts.models import EmployeeProfile


User = get_user_model()

TEST_PASSWORD = "V8!qL3@rN6#xP5zK"


class AccountRegistrationTests(TestCase):
    """アカウント作成と権限制御のテスト。"""

    def setUp(self):
        self.hq_user = User.objects.create_user(
            username="hq_admin_test",
            password=TEST_PASSWORD,
        )

        EmployeeProfile.objects.create(
            user=self.hq_user,
            role=EmployeeProfile.Role.HEADQUARTERS_ADMIN,
        )

        self.client.force_login(self.hq_user)

    def test_headquarters_admin_can_create_manager(self):
        """本社管理者は店長アカウントを作成できる。"""

        response = self.client.post(
            reverse("account_register"),
            {
                "employee_id": "manager_001",
                "full_name": "テスト店長",
                "store_code": "STORE001",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "店長アカウントを登録しました。")

        user = User.objects.get(username="manager_001")
        profile = user.employee_profile

        self.assertEqual(
            profile.role,
            EmployeeProfile.Role.STORE_MANAGER,
        )
        self.assertEqual(profile.full_name, "テスト店長")
        self.assertEqual(profile.store_code, "STORE001")
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_password_mismatch_does_not_create_account(self):
        """パスワードが一致しない場合は登録しない。"""

        response = self.client.post(
            reverse("account_register"),
            {
                "employee_id": "manager_002",
                "full_name": "テスト店長2",
                "store_code": "STORE002",
                "password1": TEST_PASSWORD,
                "password2": "DifferentPassword_789!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="manager_002").exists()
        )

    def test_anonymous_user_cannot_create_account(self):
        """未ログインの利用者はアカウントを作成できない。"""

        self.client.logout()

        response = self.client.post(
            reverse("account_register"),
            {
                "employee_id": "manager_003",
                "full_name": "テスト店長3",
                "store_code": "STORE003",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("login"))
        self.assertFalse(
            User.objects.filter(username="manager_003").exists()
        )

    def test_staff_cannot_create_accounts(self):
        """店員はアカウントを作成できない。"""

        staff_user = User.objects.create_user(
            username="staff_test",
            password=TEST_PASSWORD,
        )

        EmployeeProfile.objects.create(
            user=staff_user,
            role=EmployeeProfile.Role.STAFF,
            full_name="テスト店員",
            store_code="STORE001",
        )

        self.client.force_login(staff_user)

        response = self.client.post(
            reverse("account_register"),
            {
                "employee_id": "unauthorized_001",
                "full_name": "権限なし",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            User.objects.filter(username="unauthorized_001").exists()
        )

    def test_manager_creates_staff_in_own_store(self):
        """店長が作成した店員は、店長と同じ店舗に所属する。"""

        manager_user = User.objects.create_user(
            username="manager_test",
            password=TEST_PASSWORD,
        )

        EmployeeProfile.objects.create(
            user=manager_user,
            role=EmployeeProfile.Role.STORE_MANAGER,
            full_name="テスト店長",
            store_code="STORE001",
        )

        self.client.force_login(manager_user)

        response = self.client.post(
            reverse("account_register"),
            {
                "employee_id": "staff_001",
                "full_name": "テスト店員",
                # 送信されても、所属店舗はサーバー側の設定を使う
                "store_code": "STORE999",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "店員アカウントを登録しました。")

        staff_user = User.objects.get(username="staff_001")
        profile = staff_user.employee_profile

        self.assertEqual(profile.role, EmployeeProfile.Role.STAFF)
        self.assertEqual(profile.store_code, "STORE001")



class LoginTests(TestCase):
    """ログイン処理のテスト。"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="employee_login",
            password=TEST_PASSWORD,
        )

        EmployeeProfile.objects.create(
            user=self.user,
            role=EmployeeProfile.Role.STAFF,
            full_name="ログインテスト社員",
            store_code="STORE001",
        )

    def test_login_success(self):
        """正しい社員IDとパスワードでログインできる。"""

        # 実際の画面と同じように、先に店舗ログインを選択する
        self.client.get(reverse("select_store_portal"))

        response = self.client.post(
            reverse("login"),
            {
                "employee_id": "employee_login",
                "password": TEST_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("store_top"))

        # ログイン後、店舗トップ画面を表示できることを確認する
        response = self.client.get(reverse("store_top"))

        self.assertEqual(response.status_code, 200)

    def test_login_failure(self):
        """間違ったパスワードではログインできない。"""

        self.client.get(reverse("select_store_portal"))

        response = self.client.post(
            reverse("login"),
            {
                "employee_id": "employee_login",
                "password": "WrongPassword_123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "社員IDまたはパスワードが正しくありません。",
        )


    def test_login_failure(self):
        """間違ったパスワードではログインできない。"""

        response = self.client.post(
            reverse("login"),
            {
                "employee_id": "employee_login",
                "password": "WrongPassword_123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "社員IDまたはパスワードが正しくありません。",
        )


class LogoutTests(TestCase):
    """ログアウト処理のテスト。"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="employee_logout",
            password=TEST_PASSWORD,
        )
        self.client.force_login(self.user)

    def test_logout_success(self):
        """ログアウト後はログイン状態が解除される。"""

        # ログアウト後はログイン画面へ遷移する
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("entry"))

        # ログイン成功画面へ再アクセスすると、入口画面へ戻る
        response = self.client.get(reverse("login_success"))
        self.assertRedirects(response, reverse("entry"))