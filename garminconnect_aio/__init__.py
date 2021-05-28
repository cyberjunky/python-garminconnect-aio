"""Asynchronous Garmin Connect Python 3 API wrapper."""
import logging
import re

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from yarl import URL

logger = logging.getLogger(__name__)

URL_BASE = "https://connect.garmin.com/modern/"
URL_BASE_PROXY = "https://connect.garmin.com/proxy/"
URL_LOGIN = "https://sso.garmin.com/sso/login"


class Garmin:
    """Garmin Connect's API wrapper."""

    def __init__(self, websession: ClientSession, email: str, password: str):
        """Initialize module."""

        self._websession = websession
        self._timeout = ClientTimeout(total=10)

        self._email = email
        self._password = password
        self._username = None
        self._display_name = None

    async def _check_response(self, resp: ClientResponse):
        """Check the response and throw the appropriate exception if needed."""

        if resp.status != 200:
            try:
                response = await resp.json()
                error = response["message"]
            except Exception:
                error = None

            if resp.status == 401:
                raise GarminConnectAuthenticationError("Authentication error")

            if resp.status == 403:
                raise GarminConnectConnectionError("Error connecting to Garmin Connect")

            if resp.status == 429:
                raise GarminConnectTooManyRequestsError("Too many requests")

            # We got an unknown status code
            raise ApiException(f"Unknown API response [{resp.status}] - {error}")

    async def _get_data(self, url):
        """Get and return requests data, relogin if needed."""

        try:
            async with self._websession.request(
                "GET",
                url,
                headers=self._websession.headers,
                timeout=self._timeout,
            ) as resp:
                await self._check_response(resp)
                response = await resp.json()
        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
        ):
            logger.debug("Session expired, trying relogin")
            await self.login()

            async with self._websession.request(
                "GET",
                url,
                headers=self._websession.headers,
                timeout=self._timeout,
            ) as resp:
                await self._check_response(resp)
                response = await resp.json()

        return response

    async def login(self):
        """Return a requests session, loaded with precious cookies."""

        logger.debug("Login")

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) Gecko/20100101 Firefox/50.0"
        }

        # Define a valid user agent
        self._websession.headers.update(headers)

        response = await self._get_data(URL_BASE + "auth/hostname")
        sso_hostname = response.get("host")

        logger.debug("Get login token")

        # Load login page to get login ticket
        params = [
            ("service", "https://connect.garmin.com/modern/"),
            ("webhost", "https://connect.garmin.com/modern/"),
            ("source", "https://connect.garmin.com/signin/"),
            ("redirectAfterAccountLoginUrl", "https://connect.garmin.com/modern/"),
            ("redirectAfterAccountCreationUrl", "https://connect.garmin.com/modern/"),
            ("gauthHost", sso_hostname),
            ("locale", "fr_FR"),
            ("id", "gauth-widget"),
            ("cssUrl", "https://connect.garmin.com/gauth-custom-v3.2-min.css"),
            ("privacyStatementUrl", "https://www.garmin.com/fr-FR/privacy/connect/"),
            ("clientId", "GarminConnect"),
            ("rememberMeShown", "true"),
            ("rememberMeChecked", "false"),
            ("createAccountShown", "true"),
            ("openCreateAccount", "false"),
            ("displayNameShown", "false"),
            ("consumeServiceTicket", "false"),
            ("initialFocus", "true"),
            ("embedWidget", "false"),
            ("generateExtraServiceTicket", "true"),
            ("generateTwoExtraServiceTickets", "true"),
            ("generateNoServiceTicket", "false"),
            ("globalOptInShown", "true"),
            ("globalOptInChecked", "false"),
            ("mobile", "false"),
            ("connectLegalTerms", "true"),
            ("showTermsOfUse", "false"),
            ("showPrivacyPolicy", "false"),
            ("showConnectLegalAge", "false"),
            ("locationPromptShown", "true"),
            ("showPassword", "true"),
            ("useCustomHeader", "false"),
            ("mfaRequired", "false"),
            ("performMFACheck", "false"),
            ("rememberMyBrowserShown", "false"),
            ("rememberMyBrowserChecked", "false"),
        ]

        async with self._websession.request(
            "GET",
            URL_LOGIN,
            headers=headers,
            params=params,
            timeout=self._timeout,
        ) as resp:
            await self._check_response(resp)
            csrf_response = await resp.text()
            url_response = URL(resp.url).human_repr()

        # logger.debug("URL: %s", url_response)

        # Lookup csrf token
        csrf = re.search(
            r'<input type="hidden" name="_csrf" value="(\w+)" />',
            csrf_response,
        )
        if csrf is None:
            raise Exception("No CSRF token found")
        csrf_token = csrf.group(1)

        logger.debug("Got CSRF token: %s", csrf_token)

        # Login/password with login ticket
        data = {
            "embed": "false",
            "username": self._email,
            "password": self._password,
            "_csrf": csrf_token,
        }

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://sso.garmin.com",
            "DNT": "1",
            "Connection": "keep-alive",
            "Referer": url_response,
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "TE": "Trailers",
        }

        async with self._websession.request(
            "POST",
            URL_LOGIN,
            headers=headers,
            params=params,
            data=data,
            timeout=self._timeout,
        ) as resp:
            await self._check_response(resp)
            response = resp.cookies

        # Check we have sso guid in cookies
        if not response.get("GARMIN-SSO-GUID"):
            raise GarminConnectAuthenticationError(400, "Authentication error")

        logger.debug("Get user infomation")
        response = await self._get_data(URL_BASE + "currentuser-service/user/info")

        self._display_name = response.get("displayName")
        self._username = response.get("username")
        logger.debug("Logged in with %s", self._username)

        return self._username

    async def get_devices(self):
        """Return available devices for the current user account."""

        logger.debug("Get devices")
        return await self._get_data(
            URL_BASE_PROXY + "device-service/deviceregistration/devices"
        )

    async def get_device_settings(self, device_id):
        """Return device settings for specific device."""

        logger.debug("Get devices settings")
        return await self._get_data(
            URL_BASE_PROXY
            + "device-service/deviceservice/device-info/settings/"
            + str(device_id)
        )

    async def get_user_summary(self, cdate):
        """Return user activity summary for 'cDate' format 'YYYY-mm-dd'."""

        logger.debug("Get user summary")

        url = (
            URL_BASE_PROXY
            + "usersummary-service/usersummary/daily/"
            + self._display_name
            + "?"
            + "calendarDate="
            + cdate
        )

        response = await self._get_data(url)

        if response["privacyProtected"] is True:
            logger.debug("Session expired, trying relogin")

            await self.login()
            response = await self._get_data(url)

        return response

    async def get_body_composition(self, cdate):
        """Return available body composition data for 'cDate' format 'YYYY-mm-dd'."""

        logger.debug("Get body composition")
        url = (
            URL_BASE_PROXY
            + "weight-service/weight/daterangesnapshot"
            + "?startDate="
            + cdate
            + "&endDate="
            + cdate
        )
        return await self._get_data(url)

    async def get_device_alarms(self):
        """Combine list of active alarms from all garmin devices."""
        alarms = []
        logger.debug("Get device alarms")

        devices = await self.get_devices()
        for device in devices:
            device_settings = await self.get_device_settings(device["deviceId"])
            alarms += device_settings["alarms"]

        return alarms

    async def logout(self):
        """Session logout."""

        logger.debug("Logout")
        async with self._websession.request(
            "GET",
            URL_BASE + "/auth/logout/?url=",
            headers=self._websession.headers,
            timeout=self._timeout,
        ) as resp:
            await self._check_response(resp)


class ApiException(Exception):
    """Exception for API calls."""

    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    def __str__(self):
        return f"API Error: {self.msg}"


class GarminConnectConnectionError(Exception):
    """Raised when communication ended in error."""


class GarminConnectTooManyRequestsError(Exception):
    """Raised when rate limit is exceeded."""


class GarminConnectAuthenticationError(Exception):
    """Raised when authentication is failed."""
