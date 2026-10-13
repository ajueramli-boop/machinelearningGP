"""Synthetic FFB (fresh fruit bunch) collection logistics dataset: plantation -> mill.
Fully synthetic. Mill/block locations are fictional, placed in the Pahang region of Malaysia.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
START, END = "2025-10-01", "2026-09-30"
dates = pd.date_range(START, END, freq="D")

# ---------------- Mills ----------------
mills = pd.DataFrame({
    "mill_id": [f"M{i:02d}" for i in range(1, 6)],
    "mill_name": ["Mill Alpha", "Mill Bravo", "Mill Charlie", "Mill Delta", "Mill Echo"],
    "latitude": [3.62, 3.85, 3.41, 3.97, 3.30],
    "longitude": [102.95, 103.30, 103.15, 102.78, 103.45],
    "capacity_t_per_hr": [60, 45, 60, 30, 45],
    "weighbridges": [2, 2, 2, 1, 2],
    "ramp_capacity_t": [400, 300, 400, 200, 300],
})
mills["unload_min_per_truck_mean"] = [14, 16, 14, 18, 16]

# ---------------- Blocks ----------------
n_blocks = 60
bl_lat = rng.uniform(3.15, 4.10, n_blocks)
bl_lon = rng.uniform(102.65, 103.60, n_blocks)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

d = np.stack([haversine(bl_lat, bl_lon, m.latitude, m.longitude) for m in mills.itertuples()], axis=1)
nearest = d.argmin(axis=1)
air_km = d[np.arange(n_blocks), nearest]
road_km = np.round(air_km * rng.uniform(1.25, 1.6, n_blocks), 1)

blocks = pd.DataFrame({
    "block_id": [f"B{i:03d}" for i in range(1, n_blocks + 1)],
    "estate": [f"Estate {chr(65 + i // 10)}" for i in range(n_blocks)],
    "latitude": np.round(bl_lat, 5),
    "longitude": np.round(bl_lon, 5),
    "area_ha": np.round(rng.uniform(25, 120, n_blocks), 1),
    "palm_age_years": rng.integers(3, 26, n_blocks),
    "terrain": rng.choice(["flat", "undulating", "hilly"], n_blocks, p=[0.5, 0.35, 0.15]),
    "road_surface": rng.choice(["paved", "gravel", "earth"], n_blocks, p=[0.35, 0.45, 0.2]),
    "mill_id": mills.mill_id.values[nearest],
    "road_distance_km": np.maximum(road_km, 3.0),
})

# yield factor by palm age (peaks 8-18 years)
age = blocks.palm_age_years.values
age_factor = np.where(age < 4, 0.35, np.where(age < 8, 0.8, np.where(age <= 18, 1.0, 0.8)))
blocks["base_yield_t_per_ha_month"] = np.round(1.7 * age_factor * rng.uniform(0.85, 1.15, n_blocks), 2)

# ---------------- Trucks ----------------
n_trucks = 30
trucks = pd.DataFrame({
    "truck_id": [f"T{i:02d}" for i in range(1, n_trucks + 1)],
    "capacity_t": rng.choice([7, 10, 12], n_trucks, p=[0.3, 0.45, 0.25]),
    "age_years": rng.integers(1, 15, n_trucks),
    "fuel_l_per_100km": 0,
    "home_mill_id": rng.choice(mills.mill_id, n_trucks, p=[0.25, 0.2, 0.25, 0.1, 0.2]),
})
trucks["fuel_l_per_100km"] = np.round(18 + trucks.capacity_t * 1.6 + trucks.age_years * 0.25 + rng.normal(0, 1.5, n_trucks), 1)

# ---------------- Weather & seasonality (monthly peaks Sep-Nov, trough Feb) ----------------
doy = dates.dayofyear.values
season = 1 + 0.30 * np.cos(2 * np.pi * (doy - 275) / 365)  # peak ~ early Oct
monsoon = np.where(np.isin(dates.month, [11, 12, 1, 2]), 1.0, 0.35)  # NE monsoon over east coast
rain_prob = 0.25 + 0.4 * monsoon
rain_mm = np.where(rng.random(len(dates)) < rain_prob, rng.gamma(2.0, 12 * (0.6 + monsoon)), 0.0)
weather = pd.DataFrame({"date": dates, "rainfall_mm": np.round(rain_mm, 1), "season_index": np.round(season, 3)})
rain_map = dict(zip(dates, rain_mm))
season_map = dict(zip(dates, season))

# ---------------- Daily harvest & trips ----------------
harvest_rows, trip_rows = [], []
trip_id = 0
truck_by_mill = {m: trucks[trucks.home_mill_id == m].reset_index(drop=True) for m in mills.mill_id}
mill_idx = mills.set_index("mill_id")
# fruit rotation: each block harvested roughly every 10 days
rotation_offset = rng.integers(0, 10, n_blocks)

for day in dates:
    dow = day.dayofweek  # 0=Mon .. 6=Sun
    if dow == 6:  # Sunday: no harvest
        continue
    rain = rain_map[day]
    day_factor = season_map[day] * (0.5 if rain > 40 else 1.0)  # heavy rain cuts harvest
    for bi, b in enumerate(blocks.itertuples()):
        if (day.dayofyear + rotation_offset[bi]) % 10 != 0:
            continue
        monthly = b.area_ha * b.base_yield_t_per_ha_month
        tonnes = max(0.0, monthly / 2.6 * day_factor * rng.uniform(0.7, 1.3))  # ~2.6 rounds per month of 26 working days
        tonnes = round(tonnes, 2)
        if tonnes < 1:
            continue
        harvest_start_h = rng.uniform(7.0, 11.0)
        harvest_rows.append((day.date(), b.block_id, b.mill_id, tonnes, round(harvest_start_h, 2)))

        # split into truckloads
        pool = truck_by_mill[b.mill_id]
        remaining = tonnes
        slot_clock = harvest_start_h + rng.uniform(2.0, 4.0)  # first load ready
        while remaining > 0.5 and len(pool) > 0:
            tr = pool.iloc[rng.integers(0, len(pool))]
            load = round(min(remaining, tr.capacity_t * rng.uniform(0.85, 1.0)), 2)
            remaining -= load
            trip_id += 1

            # times (hours of day)
            wait_load = abs(rng.normal(0.35, 0.2))                    # waiting at block for loading
            load_time = load / rng.uniform(15, 25)                    # hours to load
            depart = slot_clock + wait_load + load_time
            slot_clock += rng.uniform(0.3, 0.9)

            # speed depends on surface, rain, terrain
            base_speed = {"paved": 42, "gravel": 30, "earth": 22}[b.road_surface]
            terr_pen = {"flat": 1.0, "undulating": 0.9, "hilly": 0.78}[b.terrain]
            rain_pen = 1.0 if rain < 5 else (0.85 if rain < 25 else 0.65)
            speed = max(8.0, base_speed * terr_pen * rain_pen * rng.uniform(0.9, 1.1) * (1 - 0.05 * (load / tr.capacity_t)))
            travel_h = b.road_distance_km / speed
            breakdown = rng.random() < (0.004 + 0.0007 * tr.age_years)
            breakdown_h = rng.uniform(0.5, 3.0) if breakdown else 0.0
            arrive = depart + travel_h + breakdown_h

            # mill queue: grows with arrival congestion at midday/afternoon and season peak
            hr = arrive % 24
            congestion = 1.0 + 1.2 * np.exp(-((hr - 15.0) ** 2) / 8.0)
            mrow = mill_idx.loc[b.mill_id]
            queue_min = max(0.0, rng.gamma(2.0, 9.0) * congestion * season_map[day] / mrow.weighbridges * 1.4)
            unload_min = max(5.0, rng.normal(mrow.unload_min_per_truck_mean, 3.0))
            unload_end = arrive + (queue_min + unload_min) / 60

            harvest_to_mill_h = unload_end - harvest_start_h
            # quality: FFA rises with delay beyond 24h-equivalent (here same-day, sensitive to hours)
            ffa = 2.2 + 0.05 * max(0.0, harvest_to_mill_h - 6) + rng.normal(0, 0.15) + (0.3 if rain > 25 else 0.0)
            ffa = round(max(1.5, ffa), 2)
            rejected = (ffa > 4.0) or (rng.random() < 0.004)
            rej_pct = round(rng.uniform(1, 8), 1) if rejected else round(rng.uniform(0, 1.2), 1)
            fuel_l = round(tr.fuel_l_per_100km * (b.road_distance_km * 2) / 100 * rng.uniform(0.95, 1.1), 2)

            def hhmm(h):
                h = h % 24
                return f"{int(h):02d}:{int((h % 1) * 60):02d}"

            trip_rows.append({
                "trip_id": f"TR{trip_id:06d}",
                "date": day.date(),
                "day_of_week": day.day_name(),
                "truck_id": tr.truck_id,
                "block_id": b.block_id,
                "mill_id": b.mill_id,
                "road_distance_km": b.road_distance_km,
                "road_surface": b.road_surface,
                "terrain": b.terrain,
                "truck_capacity_t": tr.capacity_t,
                "ffb_weight_t": load,
                "load_utilisation_pct": round(load / tr.capacity_t * 100, 1),
                "harvest_start_time": hhmm(harvest_start_h),
                "departure_time": hhmm(depart),
                "mill_arrival_time": hhmm(arrive),
                "load_wait_min": round(wait_load * 60, 1),
                "travel_time_min": round(travel_h * 60, 1),
                "avg_speed_kmh": round(b.road_distance_km / travel_h, 1),
                "mill_queue_min": round(queue_min, 1),
                "unload_min": round(unload_min, 1),
                "harvest_to_mill_hours": round(harvest_to_mill_h, 2),
                "rainfall_mm": round(rain, 1),
                "breakdown_flag": int(breakdown),
                "breakdown_delay_min": round(breakdown_h * 60, 1),
                "fuel_l": fuel_l,
                "ffa_pct": ffa,
                "rejection_pct": rej_pct,
                "batch_rejected_flag": int(rejected),
            })

harvest = pd.DataFrame(harvest_rows, columns=["date", "block_id", "mill_id", "harvested_t", "harvest_start_hour"])
trips = pd.DataFrame(trip_rows)

mills.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/mills.csv", index=False)
blocks.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/blocks.csv", index=False)
trucks.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/trucks.csv", index=False)
weather.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/weather_daily.csv", index=False)
harvest.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/harvest_daily.csv", index=False)
trips.to_csv("/tmp/claude-0/-home-claude/06875dbf-37fc-5525-a9c3-d309c88e8cba/scratchpad/ffb/trips.csv", index=False)
print({k: len(v) for k, v in dict(mills=mills, blocks=blocks, trucks=trucks, weather=weather, harvest=harvest, trips=trips).items()})
