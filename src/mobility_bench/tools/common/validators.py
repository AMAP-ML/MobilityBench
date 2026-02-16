"""Input validation functions for tools."""

import logging

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Input validation error."""
    pass


def validate_coordinate(coord_str: str, coord_name: str = "coordinate") -> tuple[float, float]:
    """
    Validate coordinate string format.

    Args:
        coord_str: Coordinate string, format 'longitude,latitude'
        coord_name: Coordinate name for error messages

    Returns:
        Tuple[float, float]: (longitude, latitude)

    Raises:
        ValidationError: If coordinate format is invalid
    """
    if not coord_str or not isinstance(coord_str, str):
        raise ValidationError(f"{coord_name} cannot be empty, should be a string")

    try:
        parts = coord_str.split(",")
        if len(parts) != 2:
            raise ValidationError(
                f"{coord_name} format error, should be 'longitude,latitude', actual: {coord_str}"
            )

        lon, lat = map(float, parts)

        # Validate longitude range [-180, 180]
        if not (-180 <= lon <= 180):
            raise ValidationError(
                f"{coord_name} longitude out of range, should be [-180,180], actual: {lon}"
            )

        # Validate latitude range [-90, 90]
        if not (-90 <= lat <= 90):
            raise ValidationError(
                f"{coord_name} latitude out of range, should be [-90,90], actual: {lat}"
            )

        return lon, lat

    except ValueError as e:
        raise ValidationError(
            f"{coord_name} parse error, cannot convert to number: {coord_str}. Error: {str(e)}"
        ) from e


def validate_address(address: str) -> str:
    """
    Validate address string.

    Args:
        address: Address string

    Returns:
        str: Validated address

    Raises:
        ValidationError: If address is invalid
    """
    if not address or not isinstance(address, str):
        raise ValidationError("Address cannot be empty, should be a non-empty string")

    address = address.strip()
    if not address:
        raise ValidationError("Address cannot be empty")

    if len(address) < 2:
        raise ValidationError("Address too short, at least 2 characters required")

    if len(address) > 200:
        raise ValidationError("Address too long, max 200 characters supported")

    return address


def validate_city(city: str) -> str:
    """
    Validate city name.

    Args:
        city: City name

    Returns:
        str: Validated city name

    Raises:
        ValidationError: If city name is invalid
    """
    if not city:
        return ""  # City is optional, empty string is allowed

    if not isinstance(city, str):
        raise ValidationError("City name should be a string")

    city = city.strip()

    if len(city) > 50:
        raise ValidationError("City name too long, max 50 characters supported")

    return city


def validate_radius(radius: int, min_radius: int = 1, max_radius: int = 50000) -> int:
    """
    Validate search radius.

    Args:
        radius: Radius value (meters)
        min_radius: Minimum radius
        max_radius: Maximum radius

    Returns:
        int: Validated radius value

    Raises:
        ValidationError: If radius is invalid
    """
    if not isinstance(radius, int):
        raise ValidationError(f"Radius should be an integer, actual type: {type(radius).__name__}")

    if radius < min_radius:
        raise ValidationError(f"Radius too small, min is {min_radius}m, actual: {radius}m")

    if radius > max_radius:
        raise ValidationError(f"Radius too large, max is {max_radius}m, actual: {radius}m")

    return radius
