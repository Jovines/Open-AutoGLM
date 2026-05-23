"""Device control utilities for Android automation."""

import json
import os
import re
import subprocess
import time
from typing import List, Optional, Tuple

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.config.timing import TIMING_CONFIG

_APP_CACHE_TTL_SECONDS = 60
_dynamic_apps_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}


def get_current_app(device_id: str | None = None) -> str:
    """
    Get the currently focused app name.

    Args:
        device_id: Optional ADB device ID for multi-device setups.

    Returns:
        The app name if recognized, otherwise "System Home".
    """
    adb_prefix = _get_adb_prefix(device_id)

    result = subprocess.run(
        adb_prefix + ["shell", "dumpsys", "window"], capture_output=True, text=True, encoding="utf-8"
    )
    output = result.stdout
    if not output:
        raise ValueError("No output from dumpsys window")

    # Parse window focus info
    for line in output.split("\n"):
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            for app_name, package in APP_PACKAGES.items():
                if package in line:
                    return app_name

    return "System Home"


def tap(
    x: int, y: int, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Tap at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_tap_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def double_tap(
    x: int, y: int, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Double tap at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after double tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_double_tap_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(TIMING_CONFIG.device.double_tap_interval)
    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def long_press(
    x: int,
    y: int,
    duration_ms: int = 3000,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Long press at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        duration_ms: Duration of press in milliseconds.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after long press. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_long_press_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix
        + ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
        capture_output=True,
    )
    time.sleep(delay)


def swipe(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int | None = None,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Swipe from start to end coordinates.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        duration_ms: Duration of swipe in milliseconds (auto-calculated if None).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after swipe. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_swipe_delay

    adb_prefix = _get_adb_prefix(device_id)

    if duration_ms is None:
        # Calculate duration based on distance
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(1000, min(duration_ms, 2000))  # Clamp between 1000-2000ms

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        capture_output=True,
    )
    time.sleep(delay)


def back(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the back button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing back. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_back_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "4"], capture_output=True
    )
    time.sleep(delay)


def home(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the home button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing home. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_home_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True
    )
    time.sleep(delay)


def launch_app(
    app_name: str, device_id: str | None = None, delay: float | None = None
) -> bool:
    """
    Launch an app by name.

    Args:
        app_name: The app name (must be in APP_PACKAGES).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after launching. If None, uses configured default.

    Returns:
        True if app was launched, False if app not found.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_launch_delay

    adb_prefix = _get_adb_prefix(device_id)
    package = _resolve_package_name(app_name, device_id)
    if not package:
        return False

    result = subprocess.run(
        adb_prefix
        + [
            "shell",
            "monkey",
            "-p",
            package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    time.sleep(delay)

    if _is_package_focused(package, device_id):
        return True

    for _ in range(4):
        time.sleep(0.5)
        if _is_package_focused(package, device_id):
            return True

    return False


def _resolve_package_name(app_name: str, device_id: str | None = None) -> str | None:
    """Resolve user-facing app name to package name."""
    if app_name in APP_PACKAGES:
        return APP_PACKAGES[app_name]

    normalized = _normalize_app_name(app_name)

    for known_name, package in APP_PACKAGES.items():
        if _normalize_app_name(known_name) == normalized:
            return package

    dynamic_apps = _get_dynamic_app_mappings(device_id)
    if not dynamic_apps:
        return None

    for app in dynamic_apps:
        label = app.get("label", "")
        if _normalize_app_name(label) == normalized:
            return app.get("package")

    for app in dynamic_apps:
        label = app.get("label", "")
        package = app.get("package", "")
        if normalized and normalized in _normalize_app_name(label):
            return package

    for app in dynamic_apps:
        package = app.get("package", "")
        if normalized and normalized in _normalize_app_name(package):
            return package

    return None


def _normalize_app_name(name: str) -> str:
    """Normalize app names for flexible matching."""
    return re.sub(r"\s+", "", (name or "")).strip().lower()


def _get_dynamic_app_mappings(device_id: str | None = None) -> list[dict[str, str]]:
    """Get dynamic app mapping from ADBKeyboard receiver."""
    cache_key = device_id or "default"
    cached = _dynamic_apps_cache.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < _APP_CACHE_TTL_SECONDS:
        return cached[1]

    adb_prefix = _get_adb_prefix(device_id)
    result = subprocess.run(
        adb_prefix
        + [
            "shell",
            "am",
            "broadcast",
            "-n",
            "com.android.adbkeyboard/.AppListReceiver",
            "-a",
            "ADB_LIST_APPS",
            "--ez",
            "include_system",
            "false",
            "--ei",
            "limit",
            "300",
        ],
        capture_output=True,
        text=True,
    )

    apps = _parse_apps_json_from_broadcast(result.stdout)
    _dynamic_apps_cache[cache_key] = (now, apps)
    return apps


def _parse_apps_json_from_broadcast(output: str) -> list[dict[str, str]]:
    """Extract JSON payload from am broadcast output."""
    if not output:
        return []

    match = re.search(r'data="(\[.*\])"', output, re.DOTALL)
    if not match:
        return []

    payload = match.group(1)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        package = item.get("package")
        label = item.get("label")
        if isinstance(package, str) and isinstance(label, str):
            normalized.append(
                {
                    "label": label,
                    "package": package,
                    "activity": str(item.get("activity", "")),
                }
            )
    return normalized


def _is_package_focused(package: str, device_id: str | None = None) -> bool:
    """Check if target package is currently focused."""
    adb_prefix = _get_adb_prefix(device_id)
    result = subprocess.run(
        adb_prefix + ["shell", "dumpsys", "activity", "activities"],
        capture_output=True,
        text=True,
    )
    output = result.stdout or ""
    return package in output


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
