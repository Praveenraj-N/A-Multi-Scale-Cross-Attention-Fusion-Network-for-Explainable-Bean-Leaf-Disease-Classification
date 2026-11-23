# Outbreak Monitoring

Geospatial disease surveillance added on top of the MSCAF-Net leaf classifier. The classifier, its
checkpoint, preprocessing and `/predict` endpoint are unchanged.

## 1. What it does

- Records disease observations (a predicted class, confidence, location, time, verification status).
- Registers plantations and finds those within a radius of a point.
- Computes a **preliminary inspection-priority index** per plantation and disease from nearby
  reports and, when available, current weather.
- Shows everything on an interactive map with filters, a legend, a history chart and a time slider.

It does **not** diagnose, confirm infection, or predict transmission. A report near a plantation is one
risk factor, never proof that the plantation is infected. A "Healthy" classification describes one
image, not a whole plantation.

## 2. Recording observations

`POST /api/observations` (key required). Fields: `disease` (`angular_leaf_spot | bean_rust | healthy`),
`confidence` (0-1, required for model detections), `latitude`/`longitude` (or a `plantation_id`),
`observed_at` (timezone-aware, not in the future), `crop_type`, `notes`, `detection_source`
(`model_detection | manual_report`), `location_source`, `verification_status` (`unverified | confirmed`),
optional `client_id`.

- Model detections start as **unverified**; `POST /api/observations/{id}/verification` can set
  `confirmed` or `rejected`.
- **Duplicates:** resending the same `client_id` returns the original (HTTP 200). A different submission
  of the same disease within 25 m and 10 minutes of an existing one returns HTTP 409.
- The classifier does not store images, so no image reference is kept.
- From **Disease Prediction**, "Report this detection" opens the form pre-filled with the prediction
  (not offered for mock results).

## 3. Location

The image is never assumed to carry GPS. Sources: browser geolocation (only after the browser's own
permission prompt), manually typed coordinates, a registered plantation, or administrator entry. If
permission is denied the form says so and the other options stay available. Latitude must be within
-90..90 and longitude within -180..180, checked in the browser and again on the server.

## 4. Nearby plantations

Distances use great-circle (haversine) distance. SQLite narrows candidates with an indexed
latitude/longitude bounding box (poles and the antimeridian handled), then exact distances decide. The
dashed circle on the map is labelled a *proximity-search area*; it is not a model of disease spread.
`GET /api/plantations/nearby?lat=&lon=&radius_km=&crop_type=`.

## 5-7. How the risk index works

Code: `backend/app/services/outbreak_risk_service.py`; parameters: `risk_config.py`.

For one plantation and one disease (`angular_leaf_spot`, `bean_rust`; `healthy` is not assessable):

1. **Select reports** of that disease within the disease's distance limit and the lookback window
   (default 30 days). Rejected reports are dropped; unverified model detections below the minimum
   confidence (0.7) are dropped. Confidence only filters unreliable detections. It is never treated as a
   transmission probability.
2. **Disease pressure** = `1 - exp(-sum(w) / saturation)`, where each report's
   `w = proximity x recency x verification weight` (linear distance decay, 7-day half-life, confirmed 1.0,
   unverified 0.5).
3. **Environmental factors**, each normalised to 0..1 with piecewise-linear rules:

   | Disease | Factors (default weights) |
   |---|---|
   | Angular leaf spot | pressure .40, 24 h rainfall .20, humidity .20, temperature .10, crop susceptibility .10 |
   | Bean rust | pressure .40, wind speed x alignment of wind from the reported cases towards the plantation .20, humidity .15, temperature .15, crop susceptibility .10 |

4. **Score** = weighted mean of the factors that have data, x100. Missing factors are dropped and the
   remaining weights renormalised, so missing data neither adds risk nor counts as zero risk. Missing
   factors and an "environmental assessment incomplete" flag are reported.
5. **Category:** Low < 25 <= Moderate < 50 <= High < 75 <= Very High (configurable).
6. **No nearby reports:** *Low* only if the area has other observations (including healthy ones) in the
   window, with the explanation "absence of reports, not proof of absence". With no observations at
   all the result is **Insufficient Data** and no score.

Every number above is a **provisional placeholder** for a transparent baseline, not a scientifically
established threshold. Have an agronomist review them. Crop susceptibility is empty by default (no
susceptibility is assumed). The output is named a "preliminary inspection-priority index" and is never
called an infection probability. Explanations only state what the inputs support (for example weather
is mentioned only if weather was used).

Override defaults without code changes: point `OUTBREAK_RISK_CONFIG` at a JSON file (deep-merged over
the defaults, validated at start-up; invalid files are rejected).

```json
{ "category_thresholds": { "moderate": 30, "high": 55, "very_high": 80 },
  "crop_susceptibility": { "common_bean": { "bean_rust": 0.8 } },
  "diseases": { "bean_rust": { "max_distance_km": 10 } } }
```

## 6, 8. Weather

Variables: temperature, relative humidity, rainfall over the last 24 h, wind speed and wind direction.
Provider: [Open-Meteo](https://open-meteo.com/en/docs) forecast API (`current=` plus hourly
precipitation with `past_hours=24`), requested in UTC. It needs no key for non-commercial use; commercial
plans set `WEATHER_API_KEY` and `WEATHER_BASE_URL`. `WEATHER_PROVIDER=none` disables weather. The
provider sits behind a small interface (`WeatherProvider`) so another one can be added.

Safeguards: 4 s timeout, results cached per 0.1 degree cell for 30 min, a 60 s back-off after a failure,
at most 8 cells fetched per map request, observations older than 6 h ignored, impossible values dropped
(never defaulted). Weather failures never break classification or the map; the assessment is marked
incomplete. Weather is a *current observation*; no forecasts or historical series are used for scoring.

## 9-11. Setup, run, test

```powershell
# backend (from the project root, existing .venv)
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt   # only pytest/httpx are new
$env:OUTBREAK_ADMIN_API_KEY = "choose-a-long-random-string"
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1

# frontend
cd frontend; npm install; npm run dev        # http://localhost:5173/outbreak

# tests
.venv\Scripts\python -m pytest backend\tests -q
cd frontend; npm test
```

**Database:** SQLite at `backend/data/outbreak.db` (git-ignored; set `OUTBREAK_DB_PATH` to change). The
schema is created and versioned automatically at start-up (`schema_migrations`); existing data is never
touched. Tables: `plantations`, `observations`, `risk_assessments`, `weather_observations`. If outbreak
start-up fails, `/predict` still works and `/api/*` returns 503.

**Access:** without `OUTBREAK_ADMIN_API_KEY` the map is read-only and public. With it, enter the key in
the page's "Access key" box (kept in `sessionStorage`, never in the bundle) to submit data and see
exact locations. Public viewers get coordinates rounded to 2 decimals and no plantation names, owners,
notes, boundaries or plantation links on observations.

## 12. Using the map

Pan/zoom with mouse, touch or keyboard; click a marker for details. Circles are reported observations
(solid = confirmed, hollow dashed = unverified model detection); squares with a letter are plantations
coloured by inspection priority. Numbered markers are clusters. "Show my location" (permission
required), "Reset view", "Refresh data", and "Search around a point" (click the map) are above the map.
Filters: disease, verification status, plantation priority, crop, date range, search radius. The slider
under *Reported activity* hides observations after a chosen day. Selecting a plantation shows its
assessment, weather used, nearby cases and recommended next step.

## API examples

```http
POST /api/observations        X-API-Key: ...
{"disease":"bean_rust","confidence":0.93,"latitude":12.9,"longitude":77.6,
 "location_source":"manual_entry","observed_at":"2026-06-01T08:30:00Z"}
-> 201 {"id":"...","disease":"bean_rust","verification_status":"unverified","detection_source":"model_detection",...}

GET /api/plantations/nearby?lat=12.9&lon=77.6&radius_km=5
-> {"search_area":{...,"note":"Proximity-search area only..."},"items":[{"alias":"PL-3F2A1C","distance_km":1.1,...}],"count":1}

GET /api/outbreak-risk?plantation_id=<id>
-> {"assessments":[{"disease":"bean_rust","risk_score":36.9,"risk_category":"moderate","explanation":"...",
    "recommended_action":"...","data_quality":{"weather_status":"available",...},"rule_version":"baseline-rules-0.1.0"}],
    "weather":{"status":"ok","kind":"current",...},"disclaimer":"..."}
```

Other endpoints: `GET /api/observations`, `GET /api/observations/{id}`, `POST /api/observations/{id}/verification`,
`POST /api/plantations`, `GET /api/plantations/{id}`, `GET /api/outbreak-history`,
`GET /api/map-data`, `POST /api/outbreak-risk/snapshot` (stores an assessment for every plantation to
build priority history), `GET /api/access`. Interactive schemas: `/docs`.

## 13. Limitations

- The index is a rule-based ranking aid with unvalidated thresholds. It has not been evaluated against
  real outbreaks and must not be read as an infection probability or spread forecast.
- Reports reflect where people look and submit, not true prevalence. A rise in reports may be survey
  effort, not spread. Unverified detections inherit the model's errors (99.22% accuracy on a 128-image
  test set says little about field photos).
- Weather is a single current observation at about 0.1 degree resolution; dispersal over days, leaf
  wetness, field management and varietal resistance are not modelled. Wind alignment ignores terrain.
- One shared access key, no per-user accounts or audit trail. Public rounding (~1 km) reduces but does
  not eliminate location disclosure.
- Priority *history* exists only for days where a snapshot was stored.
- SQLite with a bounding-box prefilter suits thousands of records; use PostgreSQL + PostGIS beyond that.

## 14. Replacing the baseline with a trained model

`assess_risk(target, disease, cases, weather, config, now, surveillance_observations, ...)` is a pure
function returning the result dictionary documented above. Implement a function with the same signature
(or add a model dispatch in `OutbreakService.assess_location`), train it on verified, georeferenced,
time-stamped records (plus matching weather), validate it on held-out areas and seasons, and keep the
data-quality and "insufficient data" behaviour. Stored `risk_assessments` and `weather_observations`
rows, which carry the rule version, give you the data to compare versions. Data needed for reliable
prediction: verified case records with dates and locations, negative (surveyed, disease-free)
observations, plantation boundaries and planting dates, variety susceptibility, and leaf-wetness or
hourly weather history.
