"""Asynchronous Garmin Connect Python 3 API wrapper."""
import logging
import re
from enum import Enum, auto

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

        logger.debug("Checking status code: %s", resp.status)
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
            logger.debug("Session expired, trying re-login")
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

        logger.debug("Login attempt")

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) Gecko/20100101 Firefox/50.0"
        }

        # Define a valid user agent
        self._websession.headers.update(headers)

        url = URL_BASE + "auth/hostname"
        logger.debug("Requesting sso hostname with url: %s", url)

        response = await self._get_data(url)
        sso_hostname = response.get("host")

        logger.debug("Requesting login token with url: %s", URL_LOGIN)

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

        # Lookup csrf token
        csrf = re.search(
            r'<input type="hidden" name="_csrf" value="(\w+)" />',
            csrf_response,
        )
        if csrf is None:
            raise Exception("No CSRF token found")
        csrf_token = csrf.group(1)

        logger.debug("Got CSRF token: %s", csrf_token)
        logger.debug("Referer: %s", url_response)

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

        url = URL_BASE + "currentuser-service/user/info"
        logger.debug("Requesting user information with url: %s", url)
        response = await self._get_data(url)

        self._display_name = response.get("displayName")
        self._username = response.get("username")
        logger.debug("Logged in with account: %s", self._username)

        return self._username

    async def get_devices(self):
        """Return available devices for the current user account."""

        url = URL_BASE_PROXY + "device-service/deviceregistration/devices"
        logger.debug("Requesting devices with url: %s", url)

        return await self._get_data(url)

    async def get_device_settings(self, device_id):
        """Return device settings for specific device."""

        url = (
            URL_BASE_PROXY
            + "device-service/deviceservice/device-info/settings/"
            + str(device_id)
        )
        logger.debug("Requesting device settings with url: %s", url)

        return await self._get_data(url)

    async def get_user_summary(self, cdate):
        """Return user activity summary for 'cDate' format 'YYYY-mm-dd'."""

        url = (
            URL_BASE_PROXY
            + "usersummary-service/usersummary/daily/"
            + self._display_name
            + "?calendarDate="
            + cdate
        )
        logger.debug("Requesting user summary with url: %s", url)

        response = await self._get_data(url)

        if response["privacyProtected"] is True:
            logger.debug("Session expired, trying re-login")

            await self.login()
            response = await self._get_data(url)

        return response

    async def get_body_composition(self, cdate):
        """Return available body composition data for 'cDate' format 'YYYY-mm-dd'."""

        url = (
            URL_BASE_PROXY
            + "weight-service/weight/daterangesnapshot"
            + "?startDate="
            + cdate
            + "&endDate="
            + cdate
        )
        logger.debug("Requesting body composition with url: %s", url)

        return await self._get_data(url)

    async def get_device_alarms(self):
        """Combine list of active alarms from all garmin devices."""

        logger.debug("Gathering device alarms")

        alarms = []
        devices = await self.get_devices()
        for device in devices:
            device_settings = await self.get_device_settings(device["deviceId"])
            alarms += device_settings["alarms"]

        return alarms

    async def logout(self):
        """Session logout."""

        url = URL_BASE + "/auth/logout/?url="
        logger.debug("Logout with url: %s", url)

        async with self._websession.request(
            "GET",
            url,
            headers=self._websession.headers,
            timeout=self._timeout,
        ) as resp:
            await self._check_response(resp)

    async def get_heart_rates(self, cdate):
        """Fetch available heart rates data for 'cDate' format 'YYYY-mm-dd'."""

        url = (
            URL_BASE_PROXY
            + "wellness-service/wellness/dailyHeartRate/"
            + self._display_name
            + "?date="
            + cdate
        )
        logger.debug("Requesting heart rates with url %s", url)

        return await self._get_data(url)

    async def get_sleep_data(self, cdate):
        """Fetch available sleep data for 'cDate' format 'YYYY-mm-dd'."""

        url = (
            URL_BASE_PROXY
            + "wellness-service/wellness/dailySleepData/"
            + self._display_name
            + "?date="
            + cdate
        )
        logger.debug("Requesting sleep data with url: %s", url)

        return await self._get_data(url)

    async def get_steps_data(self, cdate):
        """Fetch available steps data for 'cDate' format 'YYYY-mm-dd'."""

        url = (
            URL_BASE_PROXY
            + "wellness-service/wellness/dailySummaryChart/"
            + self._display_name
            + "?date="
            + cdate
        )
        logger.debug("Requesting steps data with url: %s", url)

        return await self._get_data(url)

    async def get_activities(self, start=1, limit=1):
        """Fetch available activities for start en limit."""

        url = (
            URL_BASE_PROXY
            + "activitylist-service/activities/search/activities?start="
            + str(start)
            + "&limit="
            + str(limit)
        )
        logger.debug("Requesting activities data for start and limit with url: %s", url)

        return await self._get_data(url)

    async def get_activities_by_date(self, startdate, enddate, activitytype):
        """
        Fetch available activities between specific dates
        :param startdate: String in the format YYYY-MM-DD
        :param enddate: String in the format YYYY-MM-DD
        :param activitytype: Type of activity you are searching
                             Possible values are [cycling, running, swimming,
                             multi_sport, fitness_equipment, hiking, walking, other]
        :return: list of JSON activities
        """

        activities = []
        start = 0
        limit = 20
        returndata = True
        # mimicking the behavior of the web interface that fetches 20 activities at a time
        # and automatically loads more on scroll
        if activitytype:
            activityslug = "&activityType=" + str(activitytype)
        else:
            activityslug = ""
        while returndata:
            url = (
                URL_BASE_PROXY
                + "activitylist-service/activities/search/activities"
                + "?startDate="
                + str(startdate)
                + "&endDate="
                + str(enddate)
                + "&start="
                + str(start)
                + "&limit="
                + str(limit)
                + activityslug
            )
            logger.debug("Requesting activities by date with url %s", url)
            response = await self._get_data(url)
            if response:
                activities.extend(response)
                start = start + limit
            else:
                returndata = False

        return activities

    async def get_excercise_sets(self, activity_id):
        """Fetch excersise sets with id."""

        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
        )
        logger.debug("Requesting excercise sets with url %s", url)

        return await self._get_data(url)

    async def get_activity_splits(self, activity_id):
        """Fetch activity splits with id."""

        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
            + "/splits"
        )
        logger.debug("Requesting activities splits with url %s", url)

        return await self._get_data(url)

    async def get_activity_split_summaries(self, activity_id):
        """Fetch activity split summaries with id."""

        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
            + "/split_summaries"
        )
        logger.debug("Requesting activities split summaries with url %s", url)

        return await self._get_data(url)

    async def get_activity_weather(self, activity_id):
        """Fetch activity split summaries with id."""

        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
            + "/weather"
        )
        logger.debug("Requesting weather with url %s", url)

        return await self._get_data(url)

    async def get_activity_hr_in_timezones(self, activity_id):
        """Fetch activity split summaries with id."""

        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
            + "/hrTimeInZones"
        )
        logger.debug("Requesting hr time in zones with url %s", url)

        return await self._get_data(url)

    async def get_activity_details(
        self, activity_id, max_chart_size=2000, max_polyline_size=4000
    ):
        """Fetch activity details with id."""

        params = f"maxChartSize={max_chart_size}&maxPolylineSize={max_polyline_size}"
        url = (
            URL_BASE_PROXY
            + "activity-service/activity/"
            + str(activity_id)
            + "/details?"
            + params
        )
        logger.debug("Requesting activity details with url %s", url)

        return await self._get_data(url)

    async def get_personal_records(self):
        """Fetch personal records for person."""

        url = (
            URL_BASE_PROXY
            + "personalrecord-service/personalrecord/prs/"
            + self._display_name
        )
        logger.debug("Requesting personal records with url %s", url)

        return await self._get_data(url)

    async def get_device_last_used(self):
        """Fetch last used garmin device."""

        url = URL_BASE_PROXY + "device-service/deviceservice/mylastused"
        logger.debug("Requesting last used garmin device with url %s", url)

        return await self._get_data(url)

    async def get_hydration_data(self, cdate):  # cDate = 'YYYY-mm-dd'
        """Fetch hydration data for 'cDate' format 'YYYY-mm-dd'"""

        url = (
            URL_BASE_PROXY + "usersummary-service/usersummary/hydration/daily/" + cdate
        )
        logger.debug("Requesting hydration data with url %s", url)

        return await self._get_data(url)

    class ActivityDownloadFormat(Enum):
        """Defines for downloads."""
        ORIGINAL = auto()
        TCX = auto()
        GPX = auto()
        KML = auto()
        CSV = auto()

    async def download_activity(self, activity_id, dl_fmt=ActivityDownloadFormat.TCX):
        """
        Downloads activity in requested format and returns the raw bytes. For
        "Original" will return the zip file content, up to user to extract it.
        "CSV" will return a csv of the splits.
        """

        urls = {
            Garmin.ActivityDownloadFormat.ORIGINAL: URL_BASE_PROXY
            + "download-service/files/activity/"
            + str(activity_id),
            Garmin.ActivityDownloadFormat.TCX: URL_BASE_PROXY
            + "download-service/export/tcx/activity/"
            + str(activity_id),
            Garmin.ActivityDownloadFormat.GPX: URL_BASE_PROXY
            + "download-service/export/gpx/activity/"
            + str(activity_id),
            Garmin.ActivityDownloadFormat.KML: URL_BASE_PROXY
            + "download-service/export/kml/activity/"
            + str(activity_id),
            Garmin.ActivityDownloadFormat.CSV: URL_BASE_PROXY
            + "download-service/export/csv/activity/"
            + str(activity_id),
        }
        if dl_fmt not in urls:
            raise ValueError(f"Unexpected value {dl_fmt} for dl_fmt")
        url = urls[dl_fmt]
        logger.debug("Downloading activity data with url %s", url)

        try:
            async with self._websession.request(
                "GET",
                url,
                headers=self._websession.headers,
                timeout=self._timeout,
            ) as resp:
                await self._check_response(resp)
                response = await resp.read()
        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
        ):
            logger.debug("Error occured while downloading activity data")

        return response


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
