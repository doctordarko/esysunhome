"""Switch platform for ESY Sunhome."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .battery import BatteryState
from .const import CONF_ENABLE_POLLING, DEFAULT_ENABLE_POLLING
from .entity import EsySunhomeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESY Sunhome switches based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        ESYSunhomePollingSwitch(coordinator=coordinator, entry=entry),
        ESYSunhomeBEMSwitch(coordinator=coordinator, entry=entry),
        ESYSunhomeBEMScheduleSwitch(
            coordinator=coordinator,
            entry=entry,
            category="charge",
            translation_key="bem_charge_schedule",
            name="BEM Charge Schedule",
            icon="mdi:battery-charging-wireless",
        ),
        ESYSunhomeBEMScheduleSwitch(
            coordinator=coordinator,
            entry=entry,
            category="discharge",
            translation_key="bem_discharge_schedule",
            name="BEM Discharge Schedule",
            icon="mdi:battery-arrow-down",
        ),
        ESYSunhomeBEMScheduleSwitch(
            coordinator=coordinator,
            entry=entry,
            category="release",
            translation_key="bem_release_schedule",
            name="BEM Release Schedule",
            icon="mdi:battery-arrow-up",
        ),
        ESYSunhomeHoldingRegisterSwitch(
            coordinator=coordinator,
            entry=entry,
            translation_key="feed_in_restriction",
            name="Feed-in Restriction",
            register_address=28,
            data_key="hardLimitEnable",
            icon="mdi:export-off",
        ),
    ])


class ESYSunhomePollingSwitch(EsySunhomeEntity, SwitchEntity):
    """Switch to control API polling."""

    _attr_translation_key = "api_polling"
    _attr_name = "API Polling"
    _attr_icon = "mdi:reload"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_api_polling"
        self._attr_entity_registry_enabled_default = True

    @property
    def is_on(self) -> bool:
        """Return true if polling is enabled."""
        return self._entry.options.get(CONF_ENABLE_POLLING, DEFAULT_ENABLE_POLLING)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on polling."""
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_ENABLE_POLLING: True},
        )
        self.coordinator.set_polling_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off polling."""
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_ENABLE_POLLING: False},
        )
        self.coordinator.set_polling_enabled(False)
        self.async_write_ha_state()


class ESYSunhomeBEMSwitch(EsySunhomeEntity, SwitchEntity):
    """Switch to control Battery Energy Management mode.

    BEM is a server-side scheduling feature — the ESY server decides which
    base mode (Regular, Emergency, Sell) the inverter is operating in based on
    a defined schedule (done on the app).
     
    While BEM is active, the Operating Mode select entity is locked because
    the server controls mode changes.

    BEM can only be toggled via the API (not MQTT).
    """

    _attr_translation_key = "bem"
    _attr_name = "Battery Energy Management"
    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the BEM switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_bem"

    @property
    def is_on(self) -> bool:
        """Return true if BEM is active (from API device info)."""
        return self.coordinator.bem_active

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state when coordinator data changes (BEM state may have changed)."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate Battery Energy Management via API."""
        try:
            await self.coordinator.api.set_mode(BatteryState.BEM_API_CODE)
            self.coordinator.bem_active = True
            _LOGGER.info("BEM activated via API")
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to activate BEM: %s", err)
            raise HomeAssistantError(f"Failed to activate BEM: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate BEM by reverting to the current base mode via API.

        Reads the current base mode from MQTT register 5 (systemRunMode)
        and sends that mode via the API to exit BEM.
        """
        try:
            # Get the base mode the inverter is currently running under BEM
            mqtt_mode = self.coordinator._last_data.get("systemRunMode", 1)
            api_code = BatteryState.mqtt_to_api.get(mqtt_mode, 1)  # Default Regular

            _LOGGER.info(
                "Deactivating BEM: reverting to base mode (MQTT reg5=%d -> API code=%d)",
                mqtt_mode, api_code,
            )
            await self.coordinator.api.set_mode(api_code)
            self.coordinator.bem_active = False
            _LOGGER.info("BEM deactivated, reverted to base mode")
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to deactivate BEM: %s", err)
            raise HomeAssistantError(f"Failed to deactivate BEM: {err}") from err


class ESYSunhomeBEMScheduleSwitch(EsySunhomeEntity, SwitchEntity):
    """Switch to enable/disable a BEM schedule category."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        category: str,
        translation_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the switch."""
        self._category = category
        self._attr_translation_key = translation_key
        self._attr_name = name
        self._attr_icon = icon
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_bem_{category}_schedule"

    @property
    def is_on(self) -> bool:
        """Return true if schedule is active."""
        return self.coordinator.get_bem_schedule_switch(self._category)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state when coordinator data changes."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the schedule."""
        await self.coordinator.set_bem_schedule_switch(self._category, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the schedule."""
        await self.coordinator.set_bem_schedule_switch(self._category, False)
        self.async_write_ha_state()


class ESYSunhomeHoldingRegisterSwitch(EsySunhomeEntity, SwitchEntity):
    """Switch entity mapped to an inverter holding register (0 = Off, 1 = On)."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        translation_key: str,
        name: str,
        register_address: int,
        data_key: str,
        icon: str,
    ) -> None:
        self._attr_translation_key = translation_key
        self._attr_name = name
        self._register_address = register_address
        self._data_key = data_key
        self._attr_icon = icon
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{data_key}"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        if hasattr(self.coordinator.data, "get"):
            val = self.coordinator.data.get(self._data_key)
        else:
            val = getattr(self.coordinator.data, self._data_key, None)
        return val == 1

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        success = await self.coordinator.set_holding_register_mqtt(
            self._register_address, 1
        )
        if success:
            if self.coordinator.data:
                if hasattr(self.coordinator.data, "_data") and isinstance(self.coordinator.data._data, dict):
                    self.coordinator.data._data[self._data_key] = 1
                    setattr(self.coordinator.data, self._data_key, 1)
                elif isinstance(self.coordinator.data, dict):
                    self.coordinator.data[self._data_key] = 1
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        success = await self.coordinator.set_holding_register_mqtt(
            self._register_address, 0
        )
        if success:
            if self.coordinator.data:
                if hasattr(self.coordinator.data, "_data") and isinstance(self.coordinator.data._data, dict):
                    self.coordinator.data._data[self._data_key] = 0
                    setattr(self.coordinator.data, self._data_key, 0)
                elif isinstance(self.coordinator.data, dict):
                    self.coordinator.data[self._data_key] = 0
            self.async_write_ha_state()
