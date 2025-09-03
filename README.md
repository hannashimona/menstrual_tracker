# Menstrual Tracker

A simple Home Assistant integration that tracks your menstrual cycle and exposes helpful entities.

## Features

- **Day of Cycle** sensor
- **Predicted Fertility Window** sensor
- **Next Period Start** sensor
- **Currently Menstruating** binary sensor
- **Calendar** entity showing upcoming period and fertility window events

## Configuration

1. Install this integration to your `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration through the UI and provide:
   - Last period start date
   - Average cycle length
   - Average period length

The integration calculates cycle information locally and updates once per day.
