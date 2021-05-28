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
            # Initialize Garmin Connect client with your credentials
            client = Garmin(session, "YOUR_EMAIL", "YOUR_PASSWORD")

            # Login to Garmin Connect portal
            username = await client.login()
            logger.debug("Username = %s", username)

            # Get users activity summary data
            logger.debug(await client.get_user_summary(today.isoformat()))

            # Get users body composition data
            logger.debug(await client.get_body_composition(today.isoformat()))

            # Get users devices data
            devices = await client.get_devices()
            logger.debug(devices)

            # Get details of users device with deviceId
            logger.debug(await client.get_device_settings(devices[0]["deviceId"]))

            # Logout
            await client.logout()

        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ) as err:
            logger.debug("Error occurred during Garmin Connect communication: %s", err)


asyncio.run(async_main())
