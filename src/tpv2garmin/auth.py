"""Garmin Connect authentication and file upload via garth."""

import logging
from pathlib import Path

import garth
from garth.exc import GarthHTTPError

from tpv2garmin.config import GARTH_TOKENS_DIR, get_config_manager

logger = logging.getLogger(__name__)


class AuthManager:
    """Manage Garmin Connect authentication using garth tokens."""

    def __init__(self) -> None:
        self._mfa_state: dict | None = None

    # ── Public API ───────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> str | None:
        """Authenticate with Garmin Connect.

        Returns:
            None on success, ``"needs_mfa"`` when an MFA code is required,
            or an error description string on failure.
        """
        self._mfa_state = None
        try:
            result = garth.client.login(email, password, return_on_mfa=True)
        except GarthHTTPError as exc:
            logger.error("Login HTTP error: %s", exc)
            return f"Login failed: {exc}"
        except Exception as exc:
            logger.exception("Unexpected error during login")
            return f"Login failed: {exc}"

        # garth returns ("needs_mfa", state_dict) when MFA is required
        if isinstance(result, tuple) and len(result) == 2 and result[0] == "needs_mfa":
            self._mfa_state = result[1]
            logger.info("MFA required for %s", email)
            return "needs_mfa"

        # Successful login without MFA
        self._save_tokens()
        logger.info("Logged in as %s", email)
        return None

    def handle_mfa(self, code: str) -> str | None:
        """Complete MFA login with the provided code.

        Returns:
            None on success, or an error description string on failure.
        """
        if self._mfa_state is None:
            return "No pending MFA challenge. Call login() first."

        try:
            garth.client.resume_login(self._mfa_state, code)
        except GarthHTTPError as exc:
            logger.error("MFA HTTP error: %s", exc)
            return f"MFA verification failed: {exc}"
        except Exception as exc:
            logger.exception("Unexpected error during MFA")
            return f"MFA verification failed: {exc}"
        finally:
            self._mfa_state = None

        self._save_tokens()
        logger.info("MFA verification successful")
        return None

    def is_authenticated(self) -> bool:
        """Check whether saved tokens exist and can be loaded."""
        try:
            self._load_tokens()
            return garth.client.oauth2_token is not None
        except Exception:
            logger.debug("No valid tokens found", exc_info=True)
            return False

    def get_username(self) -> str:
        """Return the Garmin username (email) from application config."""
        return get_config_manager().config.garmin_username

    def refresh_if_needed(self) -> None:
        """Ensure a valid session by loading and refreshing tokens.

        Raises:
            GarthHTTPError: If the refresh request fails.
            Exception: If tokens cannot be loaded or refreshed.
        """
        self._load_tokens()
        try:
            garth.client.refresh_oauth2()
            self._save_tokens()
            logger.debug("OAuth2 token refreshed successfully")
        except GarthHTTPError:
            logger.error("Failed to refresh OAuth2 token")
            raise
        except Exception:
            logger.exception("Unexpected error refreshing token")
            raise

    def upload_fit_file(self, path: Path) -> None:
        """Upload a FIT file to Garmin Connect.

        HTTP 409 (Conflict / duplicate activity) is treated as success.

        Args:
            path: Path to the ``.fit`` file to upload.

        Raises:
            GarthHTTPError: On non-409 HTTP errors.
            FileNotFoundError: If *path* does not exist.
            Exception: On unexpected failures.
        """
        logger.info("Uploading %s", path.name)
        with open(path, "rb") as fp:
            try:
                garth.client.upload(fp)
                logger.info("Upload successful: %s", path.name)
            except GarthHTTPError as exc:
                if exc.error is not None and exc.error.response is not None:
                    status = exc.error.response.status_code
                    if status == 409:
                        logger.info(
                            "Activity already exists (409), treating as success: %s",
                            path.name,
                        )
                        return
                logger.error("Upload HTTP error for %s: %s", path.name, exc)
                raise

    # ── Internal helpers ─────────────────────────────────────────────────

    def _save_tokens(self) -> None:
        """Persist garth tokens to disk."""
        try:
            GARTH_TOKENS_DIR.mkdir(parents=True, exist_ok=True)
            garth.client.dump(str(GARTH_TOKENS_DIR))
            logger.debug("Tokens saved to %s", GARTH_TOKENS_DIR)
        except Exception:
            logger.exception("Failed to save tokens")

    def _load_tokens(self) -> None:
        """Load garth tokens from disk."""
        garth.client.load(str(GARTH_TOKENS_DIR))
        logger.debug("Tokens loaded from %s", GARTH_TOKENS_DIR)


# ── Lazy singleton ───────────────────────────────────────────────────────────
_auth_manager: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    """Get or create the singleton AuthManager."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
