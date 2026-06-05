# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Dict, Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Define a FastMCP instance
mcp = FastMCP("LocalWeatherServer")

# Amap (Gaode) weather API configuration
AMAP_WEATHER_API_BASE_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
AMAP_API_KEY = os.getenv("AMAP_API_KEY","")

async def get_amap_weather(city: str) -> Optional[Dict[str, Any]]:
    """Amap (Gaode) weather API configuration"""
    params = {
        "city": city,
        "key": AMAP_API_KEY,
        "extensions": "all", # all: forecast, base: current weather
        "output": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(AMAP_WEATHER_API_BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {"error": f"Weather service request failed: {e}"}


def parse_forecast(cast: Dict[str, str]) -> str:
    """ Format single-day weather information """
    return (
        f"Date: {cast.get('date', 'Unknown')}, "
        f"Weekday: {cast.get('week', 'Unknown')}, "
        f"Daytime Weather: {cast.get('dayweather', 'Unknown')}, "
        f"Nighttime Weather: {cast.get('nightweather', 'Unknown')}, "
        f"Temperature: {cast.get('nighttemp', 'Unknown')}~{cast.get('daytemp', 'Unknown')}℃, "
        f"Wind Direction: {cast.get('daywind', 'Unknown')}~{cast.get('nightwind', 'Unknown')}, "
        f"Day Wind Force: Level {cast.get('daypower', 'Unknown')}, "
        f"Night Wind Force: Level {cast.get('nightpower', 'Unknown')}."
    )


def format_weather_data(weather_data: Dict[str, Any],city:str) -> str:
    """Format the weather response data"""
    if "error" in weather_data:
        return weather_data["error"]

    forecasts = weather_data.get("forecasts", [])
    if not forecasts:
        return "No weather information found for the specified city."

    forecast = forecasts[0]
    city = forecast.get("city", "Unknown City")
    casts = forecast.get("casts", [])

    if not casts:
        return "No weather information found for the specified city."

    today = parse_forecast(casts[0])
    future = "\n".join(parse_forecast(c) for c in casts[1:])

    result = [f"{city}Today's weather in：{today}"]
    if future:
        result.append(f"Upcoming weather：\n{future}")
    return "\n".join(result)


@mcp.tool("fetch_weather")
async def fetch_weather(city: str) -> str:
    """
      Retrieve the weather forecast for a given city

    Uses a weather information service to fetch and return the forecast for the specified
    city

    Args:
        city (str): The name of the city to get the weather information for.
    """
    weather_data = await get_amap_weather(city)
    return format_weather_data(weather_data,city)


if __name__ == "__main__":
    # Run the MCP server with the default transport protocol: stdio
    mcp.run(transport="stdio")