import urllib

import requests
from imapclient import IMAPClient
from nylas.logging import get_logger

from inbox.basicauth import ConnectionError, OAuthError
from inbox.models.backends.oauth import token_manager
from inbox.models.secret import SecretType

from .base import AuthHandler

log = get_logger()


class OAuthAuthHandler(AuthHandler):
    # Defined by subclasses
    OAUTH_ACCESS_TOKEN_URL = None

    def _new_access_token_from_refresh_token(self, account):
        refresh_token = account.refresh_token
        if not refresh_token:
            raise OAuthError("refresh_token required")

        client_id, client_secret = account.get_client_info()

        access_token_url = self.OAUTH_ACCESS_TOKEN_URL

        data = urllib.urlencode(
            {
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            }
        )
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
        }
        try:
            response = requests.post(access_token_url, data=data, headers=headers)
        except requests.exceptions.ConnectionError as e:
            log.error("Network error renewing access token", error=e)
            raise ConnectionError()

        try:
            session_dict = response.json()
        except ValueError:
            log.error("Invalid JSON renewing on renewing token", response=response.text)
            raise ConnectionError("Invalid JSON response on renewing token")

        if "error" in session_dict:
            if session_dict["error"] == "invalid_grant":
                # This is raised if the user has revoked access to the
                # application (or if the refresh token is otherwise invalid).
                raise OAuthError("invalid_grant")
            elif session_dict["error"] == "deleted_client":
                # If the developer has outright deleted their Google OAuth app
                # ID. We treat this too as a case of 'invalid credentials'.
                raise OAuthError("deleted_client")
            else:
                # You can also get e.g. {"error": "internal_failure"}
                log.error("Error renewing access token", session_dict=session_dict)
                raise ConnectionError("Server error renewing access token")

        return session_dict["access_token"], session_dict["expires_in"]

    def _access_token_from_authalligator(self, account):
        assert account.secret.type == SecretType.AuthAlligator.value
        # aa_data = json.loads(account.secret.secret)
        # TODO: get verified token

    def acquire_access_token(self, account):
        if account.secret.type == SecretType.AuthAlligator.value:
            return self._new_access_token_from_authalligator(account)
        elif account.secret.type == SecretType.Token.value:
            return self._new_access_token_from_refresh_token(account)
        else:
            raise OAuthError("No supported secret found.")

    def authenticate_imap_connection(self, account, conn):
        token = token_manager.get_token(account)
        try:
            conn.oauth2_login(account.email_address, token)
        except IMAPClient.Error as exc:
            log.error(
                "Error during IMAP XOAUTH2 login", account_id=account.id, error=exc,
            )
            raise

    def _get_user_info(self, access_token):
        try:
            response = requests.get(
                self.OAUTH_USER_INFO_URL, params={"access_token": access_token}
            )
        except requests.exceptions.ConnectionError as e:
            log.error("user_info_fetch_failed", error=e)
            raise ConnectionError()

        userinfo_dict = response.json()

        if "error" in userinfo_dict:
            assert userinfo_dict["error"] == "invalid_token"
            log.error(
                "user_info_fetch_failed",
                error=userinfo_dict["error"],
                error_description=userinfo_dict["error_description"],
            )
            log.error(
                "%s - %s" % (userinfo_dict["error"], userinfo_dict["error_description"])
            )
            raise OAuthError()

        return userinfo_dict

    def _get_authenticated_user(self, authorization_code):
        args = {
            "client_id": self.OAUTH_CLIENT_ID,
            "client_secret": self.OAUTH_CLIENT_SECRET,
            "redirect_uri": self.OAUTH_REDIRECT_URI,
            "code": authorization_code,
            "grant_type": "authorization_code",
        }

        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
        }
        data = urllib.urlencode(args)
        resp = requests.post(self.OAUTH_ACCESS_TOKEN_URL, data=data, headers=headers)

        session_dict = resp.json()

        if u"error" in session_dict:
            raise OAuthError(session_dict["error"])

        access_token = session_dict["access_token"]

        userinfo_dict = self._get_user_info(access_token)

        z = session_dict.copy()
        z.update(userinfo_dict)

        return z


class OAuthRequestsWrapper(requests.auth.AuthBase):
    """Helper class for setting the Authorization header on HTTP requests."""

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = "Bearer {}".format(self.token)
        return r
