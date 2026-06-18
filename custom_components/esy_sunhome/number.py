"""SOC cutoff number entities for ESY Sunhome BEM scheduling."""

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsySunhomeEntity

if TYPE_CHECKING:
    from .coordinator import ESYSunhomeCoordinator

_LOGGER = logging.getLogger(__name__)

# (translation_key, name, schedule field, icon)
SOC_CUTOFFS = [
    ("soc_purchase_cutoff", "SOC Purchase Cutoff", "chargeCutOff", "mdi:battery-charging-60"),
    ("soc_sale_cutoff", "SOC Sale Cutoff", "dischargeCutOff", "mdi:battery-minus-outline"),
    ("soc_use_cutoff", "SOC Use Cutoff", "releaseCutOff", "mdi:battery-outline"),
]

BEM_SCHEDULE_SOCS = [
    ("bem_charge_schedule_soc", "BEM Charge Schedule Target SOC", "charge", "mdi:battery-charging-wireless"),
    ("bem_discharge_schedule_soc", "BEM Discharge Schedule Target SOC", "discharge", "mdi:battery-arrow-down"),
    ("bem_release_schedule_soc", "BEM Release Schedule Target SOC", "release", "mdi:battery-arrow-up"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SOC cutoff number entities."""
    coordinator = config_entry.runtime_data
    
    entities = []
    entities.extend(
        ESYSunhomeSOCNumber(coordinator, key, name, field, icon)
        for key, name, field, icon in SOC_CUTOFFS
    )
    entities.extend(
        ESYSunhomeBEMScheduleSOCNumber(coordinator, key, name, category, icon)
        for key, name, category, icon in BEM_SCHEDULE_SOCS
    )
    
    async_add_entities(entities)


class ESYSunhomeSOCNumber(EsySunhomeEntity, NumberEntity):
    """Number entity for a BEM SOC cutoff value."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: "ESYSunhomeCoordinator",
        translation_key: str,
        name: str,
        field: str,
        icon: str,
    ) -> None:
        self._attr_translation_key = translation_key
        self._attr_name = name
        self._field = field
        self._attr_icon = icon
        super().__init__(coordinator)

    @property
    def native_value(self) -> float | None:
        schedule = self.coordinator.schedule_data
        if schedule is None:
            return None
        val = schedule.get(self._field)
        if val is None:
            return None
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        """Set the SOC cutoff via the API."""
        coordinator = self.coordinator
        # Fetch the latest schedule so we send back the full payload
        schedule = await coordinator.api.get_schedule()
        schedule[self._field] = int(value)
        await coordinator.api.save_schedule(schedule)
        # Update cached schedule
        coordinator.schedule_data = schedule
        self.async_write_ha_state()


class ESYSunhomeBEMScheduleSOCNumber(EsySunhomeEntity, NumberEntity):
    """Number entity for a BEM schedule Target SOC value."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: "ESYSunhomeCoordinator",
        translation_key: str,
        name: str,
        category: str,
        icon: str,
    ) -> None:
        self._attr_translation_key = translation_key
        self._attr_name = name
        self._category = category
        self._attr_icon = icon
        super().__init__(coordinator)

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.get_bem_schedule_soc(self._category)
        if val is None:
            return None
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        """Set the BEM schedule SOC target via the API."""
        await self.coordinator.set_bem_schedule_soc(self._category, int(value))
        self.async_write_ha_state()
