"""Pytest bootstrap for pure Dummy OS Energy logic tests without Home Assistant."""

from __future__ import annotations

from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]
CUSTOM_COMPONENTS = ROOT / "custom_components"
DUMMY_OS_DATA = CUSTOM_COMPONENTS / "dummy_os_data"

# Step-6 logic modules are deliberately pure Python, but importing them via the
# package name would normally execute custom_components.dummy_os_data.__init__,
# which imports Home Assistant. CI for pure logic does not install Home Assistant.
# Register lightweight namespace packages so relative imports between Step-6
# modules work without importing the integration entrypoint.
if "custom_components" not in sys.modules:
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(CUSTOM_COMPONENTS)]
    sys.modules["custom_components"] = custom_components

if "custom_components.dummy_os_data" not in sys.modules:
    dummy_os_data = types.ModuleType("custom_components.dummy_os_data")
    dummy_os_data.__path__ = [str(DUMMY_OS_DATA)]
    sys.modules["custom_components.dummy_os_data"] = dummy_os_data
