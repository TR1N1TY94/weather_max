# Weather and Climate Alert Script

This script fetches the daily maximum temperature from both local ASOS stations (via Mesonet) and NOAA Climate Reports for several U.S. cities. It monitors changes in these temperatures and sends desktop notifications if a temperature increase is detected within a short period (5 minutes).

## Features
- Fetches ASOS max temperatures from the Mesonet API.
- Fetches and parses NOAA Climate Reports for max temp and occurrence time.
- Sends cross-platform desktop notifications (macOS, Windows, Linux) when temperatures rise.
- Displays local time for each city.
- Automatically updates every minute.

## Supported Cities
- Austin, TX
- Denver, CO
- New York City, NY
- Chicago, IL
- Houston, TX
- Philadelphia, PA
- Miami, FL

## Requirements
- **Python 3.11+** (you can adjust if needed)
- **Dependencies:**  
  - `requests`  
  - `pytz`  
  - `colorama`  
  - `win10toast` (Windows only)
- **Pipenv:**
  - ```bash
    pip3 install pipenv
- **Notification Tools:**  
  - **macOS:** Uses built-in `osascript`
  - **Windows:** Uses `win10toast`  
  - **Linux:** `notify-send` (install `libnotify-bin`)

## Installation Steps

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/TR1N1TY94/weather_max.git
   cd weather_max

2. **Install Dependencies using Pipenv:**
    `pipenv install`
    This command creates a virtual environment and installs the required packages as defined in `Pipfile`.

3. **Set up Notifications:**
	- macOS:
        No additional setup required. Uses `osascript`.
	- Windows:
        `win10toast` is already included in the Pipfile.
	- Linux:
        Install `notify-send`:
        ```sudo apt-get install libnotify-bin```

4. **Run the Script:**
   
    ```pipenv run python weather_max.py```
    
    The script will fetch data, display current conditions, and send notifications if the temperature rises within a short time frame. It updates automatically every minute.

## Notes:
- Ensure your system and timezone settings are correct. Local times are displayed based on each city’s timezone.
- To change the cities or data sources, edit the `city_data` and `climate_urls` dictionaries within the script.