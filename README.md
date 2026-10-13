# Synthetic FFB Collection Logistics Dataset (Plantation → Mill)

Fully synthetic. Mill and block locations are fictional, placed roughly in the Pahang region of Malaysia. Period: 2025-10-01 to 2026-09-30. Seed 42, regenerate with `generate_ffb.py`.

## Files

| File | Rows | Grain |
|---|---|---|
| trips.csv | 9,748 | One truck trip, block → mill (main table) |
| harvest_daily.csv | 1,885 | One block harvest event |
| blocks.csv | 60 | Plantation block |
| mills.csv | 5 | Mill |
| trucks.csv | 30 | Truck |
| weather_daily.csv | 365 | Daily rainfall and season index |

Join keys: `block_id`, `mill_id`, `truck_id`, `date`.

## trips.csv

| Column | Meaning |
|---|---|
| trip_id, date, day_of_week | Trip identifiers and date (no Sunday trips) |
| truck_id, block_id, mill_id | Foreign keys |
| road_distance_km, road_surface, terrain | Route attributes (from blocks) |
| truck_capacity_t, ffb_weight_t, load_utilisation_pct | Load details |
| harvest_start_time, departure_time, mill_arrival_time | Clock times (HH:MM) |
| load_wait_min | Wait at block before and during loading |
| travel_time_min, avg_speed_kmh | Includes breakdown delay |
| mill_queue_min, unload_min | Time queuing and unloading at mill |
| harvest_to_mill_hours | Harvest start to unload end (key freshness metric) |
| rainfall_mm | Rain on trip date |
| breakdown_flag, breakdown_delay_min | Truck breakdown en route |
| fuel_l | Round-trip fuel |
| ffa_pct | Free fatty acid, rises with harvest-to-mill time and heavy rain |
| rejection_pct, batch_rejected_flag | Grading outcome |

## Built-in patterns
- Seasonal peak around Sep-Oct, trough in Feb.
- Monsoon (Nov-Feb) raises rain, slows trucks, cuts harvest on very wet days.
- Speed depends on surface (paved > gravel > earth), terrain and rain.
- Mill queues peak mid-afternoon, grow with season and fewer weighbridges.
- Older trucks break down more often.
- Palm age affects yield (peak 8-18 years).

## Suggested tasks
Trip time and queue prediction, mill congestion forecasting, FFA/quality prediction, truck-to-block assignment and routing optimization, fleet sizing.

## Limitations
Synthetic, so relationships are simplified. Block-to-mill assignment is nearest-mill. FFA values stay below typical rejection thresholds, so rejections are rare and mostly random; tune in the script if you need more.
