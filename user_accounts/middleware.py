
from django.contrib.auth import logout
from django.shortcuts import redirect


class SingleSessionMiddleware:
    """同じ社員アカウントで有効にするログインセッションを1つに制限する。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.employee_profile
            except Exception:
                profile = None

            if profile is not None:
                current_session_key = request.session.session_key

                if current_session_key:
                    # 導入前からログイン中のセッションにも対応する
                    if not profile.active_session_key:
                        profile.active_session_key = current_session_key
                        profile.save(
                            update_fields=["active_session_key"]
                        )

                    # 別のブラウザでログイン済みなら旧セッションを無効化
                    elif (
                        profile.active_session_key
                        != current_session_key
                    ):
                        logout(request)
                        return redirect("entry")

        return self.get_response(request)
