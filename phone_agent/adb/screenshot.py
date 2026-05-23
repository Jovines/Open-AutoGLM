"""Screenshot utilities for capturing Android device screen."""

import base64
import subprocess
from dataclasses import dataclass
from io import BytesIO

from PIL import Image


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False
    is_fallback: bool = False


def get_screenshot(device_id: str | None = None, timeout: int = 10) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
    """
    adb_prefix = _get_adb_prefix(device_id)

    for attempt in range(2):
        try:
            result = subprocess.run(
                adb_prefix + ["exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=timeout,
            )

            stderr_text = (result.stderr or b"").decode("utf-8", errors="ignore")

            # Check for screenshot failure (sensitive screen)
            if "Status: -1" in stderr_text or "Failed" in stderr_text:
                return _create_fallback_screenshot(is_sensitive=True)

            if result.returncode != 0:
                raise RuntimeError(
                    f"screencap failed rc={result.returncode}: {stderr_text.strip()}"
                )

            png_data = result.stdout or b""
            if len(png_data) < 16:
                raise RuntimeError("screencap output is too small")

            # Read and encode image
            with Image.open(BytesIO(png_data)) as img:
                img.load()
                width, height = img.size
                base64_data = base64.b64encode(png_data).decode("utf-8")

            return Screenshot(
                base64_data=base64_data,
                width=width,
                height=height,
                is_sensitive=False,
                is_fallback=False,
            )

        except Exception as e:
            if attempt == 1:
                print(f"Screenshot error: {e}")
                return _create_fallback_screenshot(is_sensitive=False)

    return _create_fallback_screenshot(is_sensitive=False)


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
        is_fallback=True,
    )
