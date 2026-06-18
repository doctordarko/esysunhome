"""Time platform for ESY Sunhome BEM schedule."""
import logging
from datetime import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsySunhomeEntity

if TYPE_CHECKING:
    from .coordinator import ESYSunhomeCoordinator

_LOGGER = logging.getLogger(__name__)

# (translation_key, name, category, boundary, icon)
BEM_TIME_SLOTS = [
    ("charge_schedule_start", "BEM Charge Start Time", "charge", "start", "mdi:clock-start"),
    ("charge_schedule_end", "BEM Charge End Time", "charge", "end", "mdi:clock-end"),
    ("discharge_schedule_start", "BEM Discharge Start Time", "discharge", "start", "mdi:clock-start"),
    ("discharge_schedule_end", "BEM Discharge End Time", "discharge", "end", "mdi:clock-end"),
    ("release_schedule_start", "BEM Release Start Time", "release", "start", "mdi:clock-start"),
    ("release_schedule_end", "BEM Release End Time", "release", "end", "mdi:clock-end"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BEM schedule time entities."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        ESYSunhomeBEMScheduleTime(coordinator, key, name, category, boundary, icon)
        for key, name, category, boundary, icon in BEM_TIME_SLOTS
    )


class ESYSunhomeBEMScheduleTime(EsySunhomeEntity, TimeEntity):
    """Time entity for a BEM schedule start/end time."""

    def __init__(
        self,
        coordinator: "ESYSunhomeCoordinator",
        translation_key: str,
        name: str,
        category: str,
        boundary: str,
        icon: str,
    ) -> None:
        """Initialize the BEM schedule time entity."""
        self._attr_translation_key = translation_key
        self._attr_name = name
        self._category = category
        self._boundary = boundary
        self._attr_icon = icon
        super().__init__(coordinator)

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time entity."""
        return self.coordinator.get_bem_schedule_time(self._category, self._boundary)

    async def async_set_value(self, value: time) -> None:
        """Update the value."""
        await self.coordinator.set_bem_schedule_time(self._category, self._boundary, value)
        self.async_write_ha_state()
