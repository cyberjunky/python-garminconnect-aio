# Python: Asynchronous Garmin Connect API wrapper

Asynchronous Garmin Connect Python 3 API wrapper

## About

This package allows you to request your device, activity and health data from your Garmin Connect account.
See https://connect.garmin.com/

## Installation

```bash
pip install garminconnect-aio
```

## Example Usage

```python
#!/usr/bin/env python3
"""Asynchronous Garmin Connect Python 3 API wrapper."""
import asyncio
import logging
from datetime import date

from aiohttp import ClientSession

from garminconnect_aio import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

today = date.today()

async def async_main():
    """Example code."""
    async with ClientSession() as session:
        try:

            ## Init

            # Initialize Garmin Connect client with your credentials
            client = Garmin(session, "YOUR_EMAIL", "YOUR_PASSWORD")

            # Login to Garmin Connect portal
            username = await client.login()
            logger.debug("Username = %s", username)

            ## User

            # Get users activity summary data for 'YYYY-MM-DD'
            logger.debug(await client.get_user_summary(today.isoformat()))

            # Get users body composition data for 'YYYY-MM-DD'
            logger.debug(await client.get_body_composition(today.isoformat()))

            ## Devices

            # Get users devices data
            devices = await client.get_devices()
            logger.debug(devices)

            # Get details of users device with deviceId
            logger.debug(await client.get_device_settings(devices[0]["deviceId"]))

            # Get alarm data from all devices
            logger.debug(await client.get_device_alarms())

            # Get last used garmin device
            logger.debug(await client.get_device_last_used())

            ## Activities

            # Get activities by from and to date and type (YYYY-MM-DD, YYYY-MM-DD, cycling, running, swimming, multi_sport, fitness_equipment, hiking, walking, other)
            logger.debug(await client.get_activities_by_date(twodaysback.isoformat(), today.isoformat(), "walking"))

            # Get available activites for start and limit (default 1)
            activities = await client.get_activities(1, 1)
            logger.debug(activities)

            if activities:
                # Get excercise sets for activity id
                logger.debug(await client.get_excercise_sets(activities[0]["activityId"]))

                # Get activity splits for activity id
                logger.debug(await client.get_activity_splits(activities[0]["activityId"]))

                # Get activity split summaries for activity id
                logger.debug(await client.get_activity_split_summaries(activities[0]["activityId"]))

                # Get activity weather for activity id
                logger.debug(await client.get_activity_weather(activities[0]["activityId"]))

                # Get activity heart rates time in zones for activity id
                logger.debug(await client.get_activity_hr_in_timezones(activities[0]["activityId"]))

                # Get activity details for activity id
                logger.debug(await client.get_activity_details(activities[0]["activityId"]))

                # Download activity data for activity id in specified format
                for activity in activities:
                    activityId = activity["activityId"]

                    gpx_data = await client.download_activity(activityId, dl_fmt=client.ActivityDownloadFormat.GPX)
                    output_file = f"./{str(activityId)}.gpx"
                    with open(output_file, "wb") as fb:
                        fb.write(gpx_data)

                    tcx_data = await client.download_activity(activityId, dl_fmt=client.ActivityDownloadFormat.TCX)
                    output_file = f"./{str(activityId)}.tcx"
                    with open(output_file, "wb") as fb:
                        fb.write(tcx_data)

                    zip_data = await client.download_activity(activityId, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
                    output_file = f"./{str(activityId)}.zip"
                    with open(output_file, "wb") as fb:
                        fb.write(zip_data)

                    csv_data = await client.download_activity(activityId, dl_fmt=client.ActivityDownloadFormat.CSV)
                    output_file = f"./{str(activityId)}.csv"
                    with open(output_file, "wb") as fb:
                        fb.write(csv_data)

            ## Misc information

            # Get personal records for user account
            logger.debug(await client.get_personal_records())

            # Get hydration data (YYYY-MM-DD)
            logger.debug(await client.get_hydration_data(today.isoformat()))

            # Get heart rates data for 'YYYY-MM-DD'
            logger.debug(await client.get_heart_rates( today.isoformat()))

            # Get sleep data for 'YYYY-MM-DD'
            logger.debug(await client.get_sleep_data(today.isoformat()))

            # Get steps data for 'YYYY-MM-DD'
            logger.debug(await client.get_steps_data( today.isoformat()))

            # Logout
            await client.logout()

        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ) as err:
            logger.debug("Error occurred during Garmin Connect communication: %s", err)


asyncio.run(async_main())
