"""Заглушка под реальный корпоративный OIDC/SSO — реализуется в Phase 5,
когда будет известен конкретный IdP (issuer/client_id/JWKS из настроек).
Встаёт за тем же AuthProvider, поэтому подключение не требует правок в routers/services.
"""

from app.auth.interface import AuthenticatedIdentity, AuthProvider
from app.core.exceptions import ForbiddenError


class OIDCAuthProvider(AuthProvider):
    def resolve_identity(self, authorization_header: str | None) -> AuthenticatedIdentity:
        raise ForbiddenError("OIDC-провайдер ещё не настроен (Phase 5)")
