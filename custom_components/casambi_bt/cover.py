"""Support for Casambi compatible covers (blinds, shutters, venetian blinds)."""

from __future__ import annotations

import logging
from typing import Final, cast

from CasambiBt import Unit, UnitControl, UnitControlType

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CasambiApi
from .const import DOMAIN
from .entities import CasambiUnitEntity, TypedEntityDescription

_LOGGER = logging.getLogger(__name__)

# ── Library workaround (Illumy DNS dakramen) ──────────────────────────────────
# casambi-bt-skk parses SLIDER controls as `cInt << (8 - length)`. The Illumy
# DNS has SLIDER controls wider than 8 bits, so that shift is negative and
# setStateFromBytes() raises "ValueError: negative shift count". That happens
# before the unit is marked online, so the light and the covers stay
# unavailable. We catch the error: raw_state and every control before the
# sliders are already parsed, and the cover entities below read the slider
# bits straight from raw_state.
_orig_set_state_from_bytes = Unit.setStateFromBytes


def _safe_set_state_from_bytes(self: Unit, value: bytes) -> None:
    try:
        _orig_set_state_from_bytes(self, value)
    except ValueError as err:
        _LOGGER.debug("Ignored state parse error for unit %s: %s", self.name, err)


if not getattr(Unit.setStateFromBytes, "_casambi_illumy_patched", False):
    _safe_set_state_from_bytes._casambi_illumy_patched = True  # type: ignore[attr-defined]
    Unit.setStateFromBytes = _safe_set_state_from_bytes  # type: ignore[method-assign]

# Controls that indicate a light fixture rather than a motor-driven blind.
# An EXT/1ch/Dim unit with any of these is a luminaire (e.g. Occhio Mito), not a cover.
_LIGHT_CTRL_TYPES: Final[frozenset[UnitControlType]] = frozenset(
    {
        UnitControlType.RGB,
        UnitControlType.WHITE,
        UnitControlType.TEMPERATURE,
        UnitControlType.XY,
        UnitControlType.VERTICAL,
    }
)


def _is_cover_unit(unit: Unit) -> bool:
    """Return True if the unit should be treated as a cover (blind/shutter).

    Cover units are identified by the EXT/1ch/Dim mode combined with a DIMMER
    control (position feedback) and the absence of any light-specific controls.
    Luminaires such as Occhio Mito also use EXT/1ch/Dim + DIMMER but additionally
    carry TEMPERATURE, VERTICAL, etc. — these must not be treated as covers.
    """
    controls = {c.type for c in unit.unitType.controls}
    return (
        unit.unitType.mode.startswith("EXT/1ch/Dim")
        and UnitControlType.DIMMER in controls
        and not controls.intersection(_LIGHT_CTRL_TYPES)
    )


_SLIDER_NAMES: Final = ("Plissé", "Zonwering")


def _slider_controls(unit: Unit) -> list[UnitControl]:
    """Return the SLIDER controls of an Illumy-style unit, ordered by offset.

    Only for EXT units that also have a light (DIMMER) and at least one
    SLIDER, i.e. the Illumy DNS skylight (light + plissé + zonwering).
    The Winsol Lamel is excluded: it has its own entities in lamel_controls.
    """
    ctypes = {c.type for c in unit.unitType.controls}
    if (
        not unit.unitType.mode.startswith("EXT/")
        or UnitControlType.SLIDER not in ctypes
        or UnitControlType.ONOFF in ctypes
    ):
        return []
    return sorted(
        (c for c in unit.unitType.controls if c.type == UnitControlType.SLIDER),
        key=lambda c: c.offset,
    )


def _read_bits(raw: bytes, offset: int, length: int) -> int:
    """Read `length` bits at bit `offset` from raw state bytes (little-endian)."""
    byte_offset = offset // 8
    bit_offset = offset % 8
    num_bytes = (length + bit_offset + 7) // 8
    val = int.from_bytes(raw[byte_offset : byte_offset + num_bytes], "little")
    return (val >> bit_offset) & ((1 << length) - 1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Casambi cover entities.

    All covers (SO! shutters and Lamel venetian blinds) use CasambiCover.
    Tilt (slat angle) for Lamel is exposed as a NumberEntity in lamel_controls.py.
    """
    casa_api: CasambiApi = hass.data[DOMAIN][config_entry.entry_id]

    cover_entities = [
        CasambiCover(casa_api, unit)
        for unit in casa_api.get_units()
        if _is_cover_unit(unit)
    ]

    # Illumy DNS dakramen: every SLIDER control is a separate cover
    # (index 0 = Plissé, index 1 = Zonwering).
    for unit in casa_api.get_units():
        if _is_cover_unit(unit):
            continue
        for index, ctrl in enumerate(_slider_controls(unit)):
            name = _SLIDER_NAMES[index] if index < len(_SLIDER_NAMES) else f"Slider {index + 1}"
            cover_entities.append(CasambiSliderCover(casa_api, unit, ctrl, index, name))

    _LOGGER.info("Creating %d cover entities", len(cover_entities))
    async_add_entities(cover_entities)


class CasambiCover(CasambiUnitEntity, CoverEntity):
    """Defines a Casambi cover entity for blinds and shutters."""

    def __init__(self, api: CasambiApi, unit: Unit) -> None:
        """Initialize a Casambi cover entity."""
        desc = TypedEntityDescription(key=unit.uuid, name=None, entity_type="cover")
        super().__init__(api, desc, unit)

        self._attr_device_class = CoverDeviceClass.BLIND
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position (0=closed, 100=open).

        Winsol/Casambi convention is inverted: dimmer=0 means fully open,
        dimmer=255 means fully closed. We invert to match HA convention.
        """
        unit = cast("Unit", self._obj)
        if unit.state is not None and unit.state.dimmer is not None:
            return 100 - (unit.state.dimmer * 100 // 255)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is fully closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover (dimmer=0 in Winsol convention)."""
        unit = cast("Unit", self._obj)
        await self._api.casa.setLevel(unit, 0)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover (dimmer=255 in Winsol convention)."""
        unit = cast("Unit", self._obj)
        await self._api.casa.setLevel(unit, 255)

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position (0=closed, 100=open)."""
        unit = cast("Unit", self._obj)
        position = kwargs[ATTR_POSITION]
        # Invert: HA 100%=open → Winsol dimmer=0; HA 0%=closed → Winsol dimmer=255
        await self._api.casa.setLevel(unit, (100 - position) * 255 // 100)


class CasambiSliderCover(CasambiUnitEntity, CoverEntity):
    """Cover for one SLIDER control of an Illumy DNS skylight.

    Position is the slider value scaled linearly to 0-100, without inversion:
    HA position 100 = slider at its maximum. (Hal and both plissés: 100 is
    physically closed; keuken zonwering: 0 is physically closed.)
    """

    def __init__(
        self,
        api: CasambiApi,
        unit: Unit,
        ctrl: UnitControl,
        index: int,
        name: str,
    ) -> None:
        """Initialise a cover for the given SLIDER control."""
        desc = TypedEntityDescription(
            key=unit.uuid, name=name, entity_type=f"slider-cover-{index}"
        )
        super().__init__(api, desc, unit)
        self._ctrl = ctrl
        self._max = (1 << ctrl.length) - 1
        self._attr_device_class = CoverDeviceClass.BLIND
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the slider value as 0-100."""
        unit = cast("Unit", self._obj)
        if unit.state is None or unit.state.raw_state is None:
            return None
        raw = _read_bits(unit.state.raw_state, self._ctrl.offset, self._ctrl.length)
        return round(raw * 100 / self._max)

    @property
    def is_closed(self) -> bool | None:
        """Return True at position 0 (HA convention)."""
        pos = self.current_cover_position
        return None if pos is None else pos == 0

    async def _set_position(self, position: int) -> None:
        unit = cast("Unit", self._obj)
        raw = max(0, min(self._max, round(position * self._max / 100)))
        await self._api.casa.setControlValue(unit, self._ctrl, raw)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs) -> None:
        """Move to position 100."""
        await self._set_position(100)

    async def async_close_cover(self, **kwargs) -> None:
        """Move to position 0."""
        await self._set_position(0)

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move to the requested position."""
        await self._set_position(int(kwargs[ATTR_POSITION]))
