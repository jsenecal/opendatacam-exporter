import asyncio
import time
from enum import Enum
from typing import Callable

import httpx
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseSettings

from metrics import (
    opendatacam_counter_total_items_counter,
    opendatacam_current_fps_gauge,
    opendatacam_recording_counter_data_gauge,
    opendatacam_recording_elapsed_seconds_gauge,
)
from utils import elapsed_seconds_from_strings


class ProtocolEnum(str, Enum):
    http = "http"
    https = "https"


class Settings(BaseSettings):
    site_name: str = "default"
    fqdn: str = "opendatacam"
    port: int = 8080
    min_interval: int = 3600
    protocol: ProtocolEnum = ProtocolEnum.http


class OpenDataCamAPI:
    def __init__(self, settings):
        self.site_name = settings.site_name
        self.fqdn = settings.fqdn
        self.protocol = settings.protocol
        self.min_interval = settings.min_interval
        self.port = settings.port
        self.last_ts = int(time.time())
        self._config = None
        self._current_recording_id = None
        self._total_items = 0

    @property
    def url(self):
        return f"{self.protocol}://{self.fqdn}:{self.port}"

    @property
    async def config(self):
        if self._config is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.url}/config")
                self._config = response.json()
        return self._config

    @property
    async def classes(self):
        config = await self.config
        return config["DISPLAY_CLASSES"]

    @property
    async def status(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/status")
            return response.json()

    @property
    async def total_items_counter(self):
        status = await self.status
        counter_summary = status["counterSummary"]
        total = 0
        for counter, data in counter_summary.items():
            total += data.get("_total", 0)
        return total

    @property
    async def app_state(self):
        status = await self.status
        return status["appState"]

    @property
    async def yolo_status(self):
        app_state = await self.app_state
        return app_state["yoloStatus"]

    @property
    async def recording_status(self):
        app_state = await self.app_state
        return app_state["recordingStatus"]

    @property
    async def current_fps(self):
        recording_status = await self.recording_status
        return recording_status["currentFPS"]

    @property
    async def yolo_is_starting(self):
        yolo_status = await self.yolo_status
        return yolo_status["isStarting"] is True

    @property
    async def yolo_is_started(self):
        yolo_status = await self.yolo_status
        return yolo_status["isStarted"] is True

    async def start_yolo(self):
        async with httpx.AsyncClient() as client:
            while not await self.yolo_is_started:
                if await self.yolo_is_starting:
                    await asyncio.sleep(0.2)
                    continue
                response = await client.get(f"{self.url}/start")
                if response.status_code != 200:
                    await asyncio.sleep(5)

    async def stop_yolo(self):
        if not await self.yolo_is_starting and await self.yolo_is_started:
            async with httpx.AsyncClient() as client:
                return await client.get(f"{self.url}/stop").status_code == 200

    @property
    async def recording(self):
        if self._current_recording_id is not None:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/recording/{self._current_recording_id}"
                )
                return response.json()
        return {}

    @property
    async def counter_data(self):
        if self._current_recording_id is not None:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/recording/{self._current_recording_id}/counter"
                )
                return response.json()
        return {}

    @property
    async def counter_data_areas(self):
        counter_data = await self.counter_data
        return counter_data.get("areas", {})

    @property
    async def counter_data_summary(self):
        counter_data = await self.counter_data
        return counter_data.get("counterSummary", {})

    @property
    async def elapsed_seconds(self):
        recording = await self.recording
        return elapsed_seconds_from_strings(
            recording.get("dateStart"), recording.get("dateEnd")
        )

    async def restart_recording(self):
        recording_status = await self.recording_status
        async with httpx.AsyncClient() as client:
            self._current_recording_id = recording_status.get("recordingId")
            if recording_status["isRecording"]:
                await client.get(f"{self.url}/recording/stop")
            await client.get(f"{self.url}/recording/start")

    async def delete_recordings(self):
        async with httpx.AsyncClient() as client:
            recordings_data = await client.get(
                f"{self.url}/recordings", params={"offset": "2"}
            )
            recordings = recordings_data.json().get("recordings", dict())
            for recording in recordings:
                recording_id = recording["_id"]
                await client.delete(f"{self.url}/recording/{recording_id}")

    async def refresh_metrics(self):
        # Start yolo if not started
        if not await self.yolo_is_started:
            await self.start_yolo()

        # get current yolo fps
        opendatacam_current_fps_gauge.labels(self.site_name).set(await self.current_fps)

        # track total items
        total_items = await self.total_items_counter
        opendatacam_counter_total_items_counter.labels(settings.site_name).inc(
            abs(total_items - self._total_items)
        )
        self._total_items = total_items

        # restart recording
        if int(time.time()) - self.last_ts > self.min_interval:
            await self.restart_recording()
        self.last_ts = time.time()

        # get elasped seconds from the previously completed recording
        elapsed_seconds = await self.elapsed_seconds
        opendatacam_recording_elapsed_seconds_gauge.labels(settings.site_name).set(
            elapsed_seconds
        )
        counter_data = await self.counter_data

        # counter_data
        counter_data_areas = await self.counter_data_areas
        counter_data_summary = await self.counter_data_summary
        for area, data in counter_data_summary.items():
            counter_name = counter_data_areas[area]["name"]
            for class_name, value in data.items():
                labels = [self.site_name, counter_name, class_name]
                opendatacam_recording_counter_data_gauge.labels(*labels).set(value)

        # delete all recordings besides the latest one
        await self.delete_recordings()


settings = Settings()
odca = OpenDataCamAPI(settings)
app = FastAPI()


@app.get("/classes")
async def classes():
    return await odca.classes


@app.get("/status")
async def status():
    return await odca.status


@app.get("/app_state")
async def app_state():
    await odca.start_yolo()
    return await odca.app_state


@app.middleware("http")
async def refresh_metrics(request: Request, call_next: Callable):
    await odca.refresh_metrics()
    response = await call_next(request)
    return response


instrumentator = Instrumentator()
# instrumentator.instrument(app)
instrumentator.expose(app, should_gzip=True)
