# iRacing Series & Season Synchronisation Plan

_Last updated: 2025-06-28_

## 1. Goal
Create a repeatable pipeline that minimises iRacing Data API calls while reliably synchronising:
* **Series** – high-level championships (e.g. _Toyota GR86 Cup_)
* **Seasons** – yearly/quarterly iterations of a series
* **Schedules / Rounds** – individual race-week events contained in a season

The pipeline must:
1. Avoid duplicate inserts/updates (idempotent).
2. Cache API responses aggressively during development.
3. Separate data-fetching from data-persistence (Celery tasks vs. management command).
4. Produce Celery jobs that can be safely re-queued by a nightly cron.

---

## 2. APIs Involved
| Endpoint | Params | Purpose |
| -------- | ------ | ------- |
| `get_series()` | _None_ | Returns **all** series metadata. |
| `series_seasons(series_id=<id>)` | `include_series=true` (default) | Returns current **and** future seasons for a series incl. schedules. |
| `series_past_seasons(series_id=<id>)` | – | List of **historic** seasons (IDs + basic meta). |
| `series_season_schedule(season_id=<id>)` | – | Full schedule for a given historic season. |
| `season_list(season_year, season_quarter)` | Year/quarter | Convenience search for all series active in a period, **not** required for the sync but useful validation. |

---

## 3. Data-Model Mapping
| API Field | Django Model | Field | Notes |
| --------- | ----------- | ----- | ----- |
| `series_id` | `Series` | `external_series_id` | Unique per series |
| `series_name` | `Series` | `name` |
| `allowed_licenses` | `Series` | **new** `allowed_licenses` JSONField | store raw list |
| `season_id` | `Season` | `external_season_id` |
| `season_name` | `Season` | `name` |
| `schedules[]` | `Event` | round-level records |
| `car_class_ids` | `Series` / `EventClass` | `allowed_car_class_ids` etc. | multi-class support |
| `car_restrictions` | `CarRestriction` | – |
| `weather` | `Event.weather_config` | JSON |
| Track block | `SimTrack`/`SimLayout` | link via `layout_code==track_id` |

See `docs/iracing/FIELD_MAPPING.md` for full mappings.

---

## 4. Caching Strategy
* Use Django's default cache (`django.core.cache`) with a 24h TTL in dev.
* Helper util `cache_or_fetch(key:str, ttl:int, fetch_fn:Callable)` wraps API calls.
* Cache keys:
  * `iracing:series` – full list (approx 1.2 KB)
  * `iracing:series:{series_id}:seasons` – current/future seasons
  * `iracing:series:{series_id}:past_seasons` – list of past seasons
  * `iracing:season:{season_id}:schedule` – schedule details

During local development reruns, the management command will skip network if cached.

For production/nightly jobs we can lower TTLs or bypass cache via `--refresh` flag.

---

## 5. Management Command: `sync_iracing_series`
### CLI
```bash
# Fetch & process everything (uses cache where possible)
just manage sync_iracing_series

# Force refresh & limit to specific year/quarter (optional)
just manage sync_iracing_series --year 2025 --quarter 2 --refresh
```

### High-level Flow
1. **Bootstrap** – instantiate `IRacingAPIService` (credential check).
2. **Fetch series list** (cached) → `Series` upsert (create/update via `get_or_create`).
   * Store `allowed_licenses` raw JSON.
3. **Queue season sync tasks**:
   * **Current/Future seasons**: Single task `queue_series_seasons_fetch.delay()` processes all series in one API call
   * **Past seasons**: Per-series tasks `queue_season_schedule_fetch.delay(series_id)` for historical data
4. **Logging** – Summarise created/updated counts, skipped duplicates, cache hits.
5. **API-Call Ledger** – optional model `APICallLog` (time, endpoint, params, http_status, cached:boolean) to aid debugging and throttle.

---

## 6. Celery Tasks
### `queue_series_seasons_fetch()`
* **Optimized**: Single API call to `get_series_seasons()` returns data for all series
* Wrapper around service methods with cache.
* Calls internal helper `process_series_seasons_data(data)` (leverages `_process_series_seasons` already present in `simlane.iracing.tasks`).

### `queue_season_schedule_fetch(series_id)`
* Fetch schedule for historic season.
* Use existing event-creation utilities to avoid duplicate rounds/events.

Both tasks should honour `self.retry` on `IRacingServiceError` and rate-limit via `IRACING_API_RPS` setting.

---

## 7. Duplicate/Idempotency Rules
* `Series.external_series_id` – unique; use `update_or_create`.
* `Season.external_season_id` – unique; likewise.
* `Event`: rely on helper `_get_or_create_iracing_event` (unique by `series + round_number + sim_layout`).
* `CarRestriction`: unique_together (`event`, `sim_car`).
* `EventClass`: unique_together (`event`, `car_class`).

With these constraints the command can be safely re-run.

---

## 8. Scheduling & Future Automation
* **Development** – run on-demand via management command.
* **Production** – nightly cron (e.g. Celery beat) triggers the same command with a `--headless` flag that skips interactive prompts.
* Incremental update idea: store last-processed `season_id` & `schedule_hash` to avoid reprocessing unchanged historic seasons.

---

## 9. Next Steps
1. Add `allowed_licenses` JSONField to `Series` model (non-null, default=list).
2. Scaffold `sync_iracing_series` management command (template below).
3. Implement `queue_series_seasons_fetch` & `queue_season_schedule_fetch` tasks.
4. Integrate `cache_or_fetch` utility into `IRacingAPIService`.
5. Add unit tests using `pytest-django` with `vcr.py` cassettes for API mocks.

### Management Command Skeleton
```python
# simlane/iracing/management/commands/sync_iracing_series.py
class Command(BaseCommand):
    help = "Synchronise iRacing series, seasons and schedules"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Specific season year")
        parser.add_argument("--quarter", type=int, choices=[1,2,3,4], help="Season quarter")
        parser.add_argument("--refresh", action="store_true", help="Bypass cache")

    def handle(self, *args, **options):
        from simlane.iracing.tasks import fetch_series_data
        # 1. Kick-off immediate fetch (returns within same process so we have the list)
        series_result = fetch_series_data.apply(args=[], kwargs={})
        series_list = series_result.result.get("data", [])

        # 2. Upsert Series
        ...

        # 3. Queue per-series tasks
        for s in series_list:
            queue_series_seasons_fetch.delay(s["series_id"], refresh=options["refresh"])  # pseudo-code

        self.stdout.write(self.style.SUCCESS("Queued {} series for season sync.".format(len(series_list))))
```

---

## 10. Open Questions
1. Should we mark **retired** series/seasons as `active=False` when no longer present in current `get_series()` output?
2. Where to persist API-call hashes to detect unchanged season schedules? (Redis vs. DB model)
3. How to handle track layouts not yet in DB – auto-trigger `sync_tracks`?  

Feedback welcome! 