# Menstrual Tracker

A simple Home Assistant integration that tracks your menstrual cycle and exposes helpful entities.

## Features

- **Day of Cycle** sensor
- **Predicted Fertility Window** sensor
- **Next Period Start** sensor
- **Average Cycle Length** sensor
- **Average Period Length** sensor
- **Cycle/Period Length Percentile** sensors (25th/50th/75th when history is available)
- **Currently Menstruating** binary sensor
- **Calendar** entity showing upcoming period and fertility window events

## Configuration

1. Install this integration to your `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration through the UI and provide:
   - Last period start date
   - Average cycle length
   - Average period length

   Alternatively, configure via YAML:

   ```yaml
   menstrual_tracker:
     last_period_start: "2025-08-01"
     cycle_length: 28
     period_length: 5
   ```

The integration calculates cycle information locally and updates once per day.
