import requests
from datetime import datetime, timezone, timedelta
import pytz
import time
import os
import subprocess
import sys
import re

from functools import partial
from mac_notifications import client

from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# ---------------- Configuration ----------------

# City-specific Mesonet API endpoints and time zones
# Added "current_url" to fetch `max_dayairtemp[F]` from the real-time JSON
city_data = {
    "Austin, TX": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=TX_ASOS&station=AUS&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=TX_ASOS&station=AUS",
        "timezone": "America/Chicago"
    },
    "Denver, CO": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=CO_ASOS&station=DEN&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=CO_ASOS&station=DEN",
        "timezone": "America/Denver"
    },
    "Miami, FL": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=FL_ASOS&station=MIA&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=FL_ASOS&station=MIA",
        "timezone": "America/New_York"
    },
    "New York City, NY": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=NY_ASOS&station=NYC&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=NY_ASOS&station=NYC",
        "timezone": "America/New_York"
    },
    "Chicago, IL": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=IL_ASOS&station=MDW&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=IL_ASOS&station=MDW",
        "timezone": "America/Chicago"
    },
    "Houston, TX": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=TX_ASOS&station=HOU&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=TX_ASOS&station=HOU",
        "timezone": "America/Chicago"
    },
    "Philadelphia, PA": {
        "daily_url": "https://mesonet.agron.iastate.edu/api/1/daily.json?network=PA_ASOS&station=PHL&month=12&year=2024",
        "current_url": "https://mesonet.agron.iastate.edu/json/current.py?network=PA_ASOS&station=PHL",
        "timezone": "America/New_York"
    },
}

# NOAA climate product URLs
climate_urls = {
    "Austin, TX": "https://forecast.weather.gov/product.php?site=EWX&product=CLI&issuedby=AUS",
    "Denver, CO": "https://forecast.weather.gov/product.php?site=BOU&product=CLI&issuedby=DEN",
    "Miami, FL": "https://forecast.weather.gov/product.php?site=MFL&product=CLI&issuedby=MIA",
    "New York City, NY": "https://forecast.weather.gov/product.php?site=OKX&product=CLI&issuedby=NYC",
    "Chicago, IL": "https://forecast.weather.gov/product.php?site=LOT&product=CLI&issuedby=MDW",
    "Houston, TX": "https://forecast.weather.gov/product.php?site=HGX&product=CLI&issuedby=HOU",
    "Philadelphia, PA": "https://forecast.weather.gov/product.php?site=HGX&product=CLI&issuedby=PHL",
}

# City colors for display
city_colors = [
    Fore.RED,
    Fore.GREEN,
    Fore.BLUE,
    Fore.YELLOW,
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.WHITE,
]

city_color_map = {city: color for city, color in zip(city_data.keys(), city_colors)}

# Track ASOS and climate report temperatures over time
# Adding 'last_notified_temp' to handle the "don't notify more than once" scenario
temperature_history = {
    city: {
        "temp": None,              # Last stored temperature
        "timestamp": None,         # Last updated UTC time
        "last_notified_temp": None # Last temperature that triggered a notification
    } 
    for city in city_data.keys()
}

climate_temperature_history = {
    city: {
        "temp": None,              # Last stored climate temperature
        "timestamp": None,         # Last updated UTC time
        "last_notified_temp": None # Last climate temperature that triggered a notification
    } 
    for city in city_data.keys()
}

# ---------------- Notification System ----------------

def send_notification(city, message):
    """
    Send a notification to the user depending on the operating system:
    - macOS (darwin): uses AppleScript via osascript
    - Windows (win): uses win10toast (if available)
    - Linux (linux): uses notify-send
    - Otherwise: prints to console
    """
    platform = sys.platform
    title = f"Temperature Alert: {city}"

    if platform == "darwin":
        # macOS notification
        client.create_notification(
            title=title,
            subtitle=message,
        )

    elif "win" in platform:
        # Windows notification using win10toast if available
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            # If win10toast not installed, fallback to console print
            print(f"Notification: {title} - {message}")

    elif "linux" in platform:
        # Linux notification using notify-send
        subprocess.call(["notify-send", title, message])

    else:
        # Other platforms, fallback to console print
        print(f"Notification: {title} - {message}")

# ---------------- Data Fetching Functions ----------------

def fetch_daily_temp(daily_url, city):
    """
    Fetch the max temperature for today from the Mesonet daily API using the city's local date.
    Returns None if not found or an error occurred.
    """
    try:
        response = requests.get(daily_url)
        response.raise_for_status()
        data = response.json()

        # Determine the local date for the city
        tz = pytz.timezone(city_data[city]["timezone"])
        local_now = datetime.now(tz)
        today = local_now.strftime('%Y-%m-%d')

        for record in data.get('data', []):
            if record.get('date') == today:
                return record.get('max_tmpf')
        return None
    except requests.RequestException:
        return None

def fetch_current_max_dayairtemp(current_url):
    """
    Fetch the 'max_dayairtemp[F]' value from the 'last_ob' section 
    of the real-time Mesonet JSON (e.g. https://mesonet.agron.iastate.edu/json/current.py?network=TX_ASOS&station=AUS).
    Returns None if not found or an error occurred.
    """
    try:
        response = requests.get(current_url)
        response.raise_for_status()
        data = response.json()

        # JSON structure:
        # {
        #   "last_ob": {
        #       "max_dayairtemp[F]": 74.0,
        #       ...
        #   }
        # }
        last_ob = data.get("last_ob", {})
        return last_ob.get("max_dayairtemp[F]", None)
    except requests.RequestException:
        return None

def fetch_max_temperature(city):
    """
    Combines the daily Mesonet 'max_tmpf' and the current 'max_dayairtemp[F]' 
    and returns the greater of the two as the current daily max temperature.
    """
    daily_url = city_data[city]["daily_url"]
    current_url = city_data[city]["current_url"]

    daily_temp = fetch_daily_temp(daily_url, city)
    current_temp = fetch_current_max_dayairtemp(current_url)

    # If both are None, result is None
    if daily_temp is None and current_temp is None:
        return None

    # Convert to float if needed (the daily_temp might come back as an int or float)
    vals = []
    for val in (daily_temp, current_temp):
        try:
            vals.append(float(val))
        except (TypeError, ValueError):
            pass

    # Return the maximum of all valid numeric values
    return max(vals) if vals else None

def fetch_climate_report(city):
    """
    Fetch the NOAA climate report and parse out the max temperature and time.
    Handles times like '1:44 PM' and '1136 AM' by inserting a colon if missing.
    """
    url = climate_urls[city]
    try:
        response = requests.get(url)
        response.raise_for_status()
        text = response.text

        lines = text.splitlines()
        max_temp = None
        max_time = None

        for line in lines:
            if "MAXIMUM" in line.upper():
                parts = line.split()

                if len(parts) > 3 and parts[0].upper() == "MAXIMUM" and parts[1].isdigit():
                    max_temp = parts[1]

                    # Time extraction
                    time_str = parts[2]
                    am_pm = parts[3].upper() if parts[3].upper() in ["AM", "PM"] else None

                    if am_pm:
                        # If time already has a colon, use it
                        if re.match(r"\d{1,2}:\d{2}", time_str):
                            max_time = time_str + " " + am_pm
                        else:
                            # Insert a colon if missing
                            if len(time_str) == 3:
                                # '736' -> '7:36'
                                time_str = time_str[0] + ":" + time_str[1:]
                            elif len(time_str) == 4:
                                # '1136' -> '11:36'
                                time_str = time_str[:2] + ":" + time_str[2:]

                            max_time = time_str + " " + am_pm

                break

        return max_temp, max_time

    except requests.RequestException:
        return None, None

def fetch_all_cities():
    """
    Fetch the daily max temperatures for all cities by combining daily and current endpoints.
    Returns a dictionary of city -> temperature.
    """
    results = {}
    for city in city_data.keys():
        max_temp = fetch_max_temperature(city)
        results[city] = max_temp
    return results

# ---------------- Helper Functions ----------------

def get_local_time(city):
    """
    Get the local time for a given city, based on its configured timezone.
    """
    tz = pytz.timezone(city_data[city]["timezone"])
    local_time = datetime.now(tz)
    return local_time.strftime('%Y-%m-%d %I:%M %p')

def notify_temperature_change(city, current_temp):
    """
    Show in the Terminal if the ASOS temperature for a city has increased 
    (strictly greater) within the last 5 minutes, but only send a pop-up
    notification once per unique temperature jump.
    """
    previous_data = temperature_history[city]
    previous_temp = previous_data["temp"]
    previous_timestamp = previous_data["timestamp"]
    last_notified_temp = previous_data["last_notified_temp"]

    if not isinstance(current_temp, (int, float)):
        return ""

    # We'll build a suffix text we can print in the Terminal if there's an increase
    increase_suffix = ""

    # Always check if the temperature has risen since the last reading
    if previous_temp is not None and current_temp > previous_temp:
        time_diff = datetime.now(timezone.utc) - previous_timestamp
        if time_diff <= timedelta(minutes=5):
            # We'll always *show* in the Terminal if it's gone up in the last 5 minutes
            increase_suffix = f"(^ from {previous_temp}°F in last {int(time_diff.total_seconds() // 60)} minutes)"

            # But only send a notification if we haven't notified for this temp before
            if current_temp != last_notified_temp:
                message = (
                    f"ASOS Temperature in {city} increased to {current_temp}°F "
                    f"(from {previous_temp}°F)."
                )
                send_notification(city, message)
                previous_data["last_notified_temp"] = current_temp

    # Update the temperature/time for this city 
    temperature_history[city]["temp"] = current_temp
    temperature_history[city]["timestamp"] = datetime.now(timezone.utc)

    return increase_suffix

def notify_climate_temperature_change(city, current_temp):
    """
    Notify if the Climate Report temperature for a city has increased within the last 5 minutes,
    and only once for that temp.
    """
    previous_data = climate_temperature_history[city]
    previous_temp = previous_data["temp"]
    previous_timestamp = previous_data["timestamp"]
    last_notified_temp = previous_data["last_notified_temp"]

    # Convert current_temp (str) to int if possible
    try:
        current_temp_val = int(current_temp)
    except (ValueError, TypeError):
        return ""

    if (previous_temp is not None 
        and current_temp_val > previous_temp 
        and current_temp_val != last_notified_temp):
        
        time_diff = datetime.now(timezone.utc) - previous_timestamp
        if time_diff <= timedelta(minutes=5):
            message = f"Climate Report Temp in {city} increased to {current_temp_val}°F (from {previous_temp}°F)."
            send_notification(city, message)
            # Record that we have notified about this particular temperature
            previous_data["last_notified_temp"] = current_temp_val
            return f"(Climate: ^ from {previous_temp} in last {int(time_diff.total_seconds() // 60)} minutes)"

    if isinstance(current_temp_val, int):
        climate_temperature_history[city]["temp"] = current_temp_val
        climate_temperature_history[city]["timestamp"] = datetime.now(timezone.utc)

    return ""

def clear_console():
    """
    Clear the console for a cleaner output.
    """
    os.system("cls" if os.name == "nt" else "clear")

# ---------------- Main Execution Loop ----------------

def main():
    while True:
        clear_console()
        print(f"{Style.BRIGHT}Fetching data at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        
        # Fetch today's ASOS max temps from both daily + current JSON (combined)
        city_temperatures = fetch_all_cities()

        for city, temp in city_temperatures.items():
            color = city_color_map.get(city, Fore.WHITE)
            temp_color = Fore.RED if isinstance(temp, (int, float)) and temp > 80 else Fore.CYAN
            local_time = get_local_time(city)

            # Fetch Climate report max temp and time
            climate_max, climate_time = fetch_climate_report(city)
            climate_report_str = ""
            climate_notification = ""
            if climate_max and climate_time:
                climate_report_str = f"Climate Report Max Temp: {Style.BRIGHT}{climate_max} ({climate_time}){Style.RESET_ALL}"
                climate_notification = notify_climate_temperature_change(city, climate_max)

            # Check and notify ASOS temp increases
            notification = ""
            if isinstance(temp, (int, float)):
                notification = notify_temperature_change(city, temp)

            # Print results to console
            print(
                f"{color}{city} (Local Time: {local_time}): "
                f"{temp_color}{climate_report_str} {climate_notification} / "
                f"{temp_color}ASOS Current Max Temp: {Style.BRIGHT}{temp}{Style.RESET_ALL} {notification}"
            )

        print(f"\n{Style.BRIGHT}Updating in 1 minute...\n")
        time.sleep(30)

if __name__ == "__main__":
    main()
