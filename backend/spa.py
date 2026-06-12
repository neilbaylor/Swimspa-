"""Spa controllers.

Two implementations share the same small async interface so the web layer
doesn't care whether it's talking to a real spa or the built-in demo:

    await controller.start()           # connect / begin background work
    await controller.stop()            # tidy shutdown
    controller.status() -> dict        # current snapshot for the UI
    await controller.step_up()         # raise setpoint by one step
    await controller.step_down()       # lower setpoint by one step
    await controller.set_temperature(v)

The real controller talks to a Gecko in.touch2 spa over the local network
using geckolib (https://github.com/gazoodle/geckolib). It must therefore run
on a machine on the same LAN/wifi as the spa.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

_LOGGER = logging.getLogger("swimspa")


def _step_for_unit(unit: str) -> float:
    """Gecko spas adjust in 1 degree steps in Fahrenheit, 0.5 in Celsius."""
    return 1.0 if "F" in (unit or "").upper() else 0.5


class SpaController:
    """Talks to a real Gecko spa via geckolib over the local network."""

    # How often to retry the discover/connect sequence while disconnected.
    RECONNECT_SECONDS = 15

    def __init__(self, spa_address: str | None = None) -> None:
        self._spa_address = spa_address or None
        self._spaman = None  # geckolib GeckoAsyncSpaMan subclass instance
        self._facade = None
        self._lock = asyncio.Lock()
        self._connect_task: asyncio.Task | None = None
        self._last_error: str | None = None

    async def start(self) -> None:
        # Imported lazily so the module (and demo mode) work without geckolib.
        from geckolib import GeckoAsyncSpaMan, GeckoSpaEvent

        class _SpaMan(GeckoAsyncSpaMan):
            async def handle_event(self, event: GeckoSpaEvent, **_kwargs) -> None:
                _LOGGER.debug("spa event: %s", event)

        client_uuid = str(uuid.uuid4())
        self._spaman = _SpaMan(client_uuid)
        await self._spaman.__aenter__()
        # Kick off connection in the background so the web server starts fast.
        self._connect_task = asyncio.ensure_future(self._connect_loop())

    async def _connect_loop(self) -> None:
        while True:
            try:
                if self._facade is None:
                    await self._try_connect()
            except Exception as exc:  # keep the loop alive across any failure
                self._last_error = str(exc)
                _LOGGER.warning("spa connect attempt failed: %s", exc)
            await asyncio.sleep(self.RECONNECT_SECONDS)

    async def _try_connect(self) -> None:
        _LOGGER.info("locating spa (address=%s)...", self._spa_address or "broadcast")
        descriptors = await self._spaman.async_locate_spas(self._spa_address)
        if not descriptors:
            self._last_error = "No spa found on the network"
            return
        facade = await self._spaman.async_connect_to_spa(descriptors[0])
        if facade is None:
            self._last_error = "Found spa but failed to connect"
            return
        await self._spaman.wait_for_facade()
        self._facade = facade
        self._last_error = None
        _LOGGER.info("connected to spa: %s", descriptors[0].name)

    def _safe_spa_name(self):
        # geckolib's spa_name property asserts non-None before connection.
        try:
            return self._spaman.spa_name
        except Exception:  # noqa: BLE001
            return None

    def _water_heater(self):
        if self._facade is None:
            return None
        wh = getattr(self._facade, "water_heater", None)
        if wh is None or not getattr(wh, "is_present", True):
            return None
        return wh

    def status(self) -> dict:
        wh = self._water_heater()
        if wh is None:
            return {
                "connected": False,
                "spa_name": self._safe_spa_name(),
                "error": self._last_error or "Connecting to spa...",
            }
        unit = wh.temperature_unit
        return {
            "connected": True,
            "spa_name": self._safe_spa_name(),
            "current_temperature": wh.current_temperature,
            "target_temperature": wh.target_temperature,
            "min_temp": wh.min_temp,
            "max_temp": wh.max_temp,
            "unit": unit,
            "operation": wh.current_operation,
            "step": _step_for_unit(unit),
            "error": None,
        }

    async def set_temperature(self, value: float) -> dict:
        wh = self._water_heater()
        if wh is None:
            return self.status()
        value = max(wh.min_temp, min(wh.max_temp, round(value, 1)))
        async with self._lock:
            await wh.async_set_target_temperature(value)
        return self.status()

    async def step_up(self) -> dict:
        wh = self._water_heater()
        if wh is None:
            return self.status()
        return await self.set_temperature(
            wh.target_temperature + _step_for_unit(wh.temperature_unit)
        )

    async def step_down(self) -> dict:
        wh = self._water_heater()
        if wh is None:
            return self.status()
        return await self.set_temperature(
            wh.target_temperature - _step_for_unit(wh.temperature_unit)
        )

    async def stop(self) -> None:
        if self._connect_task is not None:
            self._connect_task.cancel()
        if self._spaman is not None:
            try:
                await self._spaman.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass


class DemoSpaController:
    """In-memory fake spa so the app runs and demos without any hardware."""

    def __init__(self) -> None:
        self._unit = "°F"
        self._min = 60.0
        self._max = 104.0
        self._target = 100.0
        self._current = 98.0
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.ensure_future(self._drift())

    async def _drift(self) -> None:
        # Gently move the "water" toward the setpoint to feel alive.
        while True:
            await asyncio.sleep(3)
            if abs(self._current - self._target) < 0.1:
                self._current = self._target
            elif self._current < self._target:
                self._current = round(self._current + 0.2, 1)
            else:
                self._current = round(self._current - 0.2, 1)

    def _operation(self) -> str:
        if self._current < self._target - 0.2:
            return "Heating"
        return "Idle"

    def status(self) -> dict:
        return {
            "connected": True,
            "spa_name": "Demo Swim Spa",
            "current_temperature": self._current,
            "target_temperature": self._target,
            "min_temp": self._min,
            "max_temp": self._max,
            "unit": self._unit,
            "operation": self._operation(),
            "step": _step_for_unit(self._unit),
            "error": None,
            "demo": True,
        }

    async def set_temperature(self, value: float) -> dict:
        async with self._lock:
            self._target = max(self._min, min(self._max, round(value, 1)))
        return self.status()

    async def step_up(self) -> dict:
        return await self.set_temperature(self._target + _step_for_unit(self._unit))

    async def step_down(self) -> dict:
        return await self.set_temperature(self._target - _step_for_unit(self._unit))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
