# SimLane – Project Documentation

## 1. Overview
SimLane is a **sim-racing companion platform** built with Django. It aggregates data from services such as iRacing and Garage-61, offers team and club management, and integrates with Discord for rich community features.

The project started from the Cookiecutter-Django template, but has been heavily tailored for container-first development and modern frontend tooling (Tailwind CSS v4, HTMX, Webpack).

---

## 2. Tech Stack

| Concern                | Implementation |
|------------------------|----------------|
| Backend                | Python 3 · Django 5  |
| Worker / Background    | Celery (Redis broker) |
| Database               | PostgreSQL |
| Caching / Broker       | Redis |
| Task Queue Dashboard   | Flower |
| Front-end Styling      | Tailwind CSS v4 |
| Progressive Enhancement| HTMX |
| Asset Bundling         | Webpack |
| Containerisation       | Docker Compose |
| Secrets & Config       | Doppler |

---

## 3. Directory Layout (root level)

```
compose/            # Docker compose files (local & production)
config/             # Django project config (settings, urls, wsgi, asgi, celery)
requirements/       # Python dependency spec split by environment
simlane/            # All Django apps live here
  ├─ core/          # Generic site functionality (home, contact, static pages)
  ├─ users/         # User & auth management
  ├─ iracing/       # iRacing API integration & data models
  ├─ discord/       # Discord bot commands & webhooks
  ├─ garage61/      # Garage-61 API integration
  ├─ sim/           # Sim racing utilities / domain models
  └─ teams/         # Team / club functionality
static/             # Compiled/static assets served by Django
templates/          # Django templates (site-wide & per-app)
justfile            # Task runner shortcuts
manage.py           # Django entry-point (used inside containers)
```

> Refer to `.cursorrules` for a fully annotated structure.

---

## 4. Development Environment

Development is **container-first**. All commands are executed via the `just` task runner, which wraps Docker Compose.

1. **Start services**
   ```bash
   just up
   ```
   This boots PostgreSQL, Redis, Mailpit, Celery workers/beat, Flower, and the Django & Node containers with auto-reload.

2. **Stop services**
   ```bash
   just down
   ```

3. **View logs**
   ```bash
   just logs [service]
   ```

### 4.1 Django Management
Replace any `python manage.py <cmd>` with:
```bash
just manage <cmd>
```
Examples:
```bash
just manage makemigrations core
just manage migrate
just manage createsuperuser
```

### 4.2 Dependency Management
• **Python** – add the package to `requirements/{base|local|production}.txt` then run `just build` to rebuild images.

• **Node** – edit `package.json` (no version pin change without approval), then `just build`.

### 4.3 Pre-commit & Quality
Run checks locally before committing:
```bash
pre-commit run --all-files
```

---

## 5. Common Workflows

| Task | Command |
|------|---------|
| Run tests | `just manage test` or `pytest` inside `web` container |
| Static analysis (Ruff & mypy) | `ruff check .` · `mypy simlane` |
| Create migration | `just manage makemigrations <app>` |
| Apply migration | `just manage migrate` |
| Rebuild after dependency change | `just build` |
| Open interactive shell | `just manage shell_plus` |

---

## 6. Coding Guidelines (excerpt)

1. Prefer **CBVs** for complex views, **FBVs** for simple endpoints.
2. Keep business logic in **models** & **forms**; keep views thin.
3. Use Django ORM – avoid raw SQL unless necessary.
4. Validate data with Django **forms / model validations**.
5. Optimise queries with `select_related` / `prefetch_related`.
6. Use Celery for long-running or IO-bound tasks.
7. Adhere to **PEP-8** style and project linter settings.

Refer to `.cursorrules` for the complete list.

---

## 7. Deployment

* **Production compose file** – `docker-compose.production.yml` (Traefik, gunicorn, etc.)
* **Environment variables** – managed by **Doppler**. The `.envs/` directory from the template is kept for reference but not used.
* **Static & media** – served via S3/CloudFront (settings already scaffolded).

A full deployment script lives under `scripts/deploy.sh`.

---

## 8. Support & Contact

Found a bug? Open an issue or reach out on Discord.

Enjoy the drive and happy coding! 🚗💨 

---

## 9. Data Model Overview

Below is a concise catalogue of the primary Django models grouped by app.  The aim is to give contributors a _mental map_ of where data lives and how tables connect.  Field lists are condensed to focus on relationships; refer to the source for full details.

### simlane.core

| Model | Relationships |
|-------|---------------|
| `ContactMessage` | • `user` → `users.User` _(nullable)_ |

---

### simlane.users

| Model | Notes |
|-------|-------|
| `User` | Custom `AbstractUser` replacement with an extra `name` field |

---

### simlane.discord

| Model | Relationships |
|-------|---------------|
| `DiscordGuild` | • `club` → `teams.Club` _(one-to-one)_ |
| `BotCommand` | • `guild` → `DiscordGuild` <br/> • `django_user` (via social-account lookup) |
| `BotSettings` | _stand-alone key/value store_ |

---

### simlane.garage61

| Model | Relationships |
|-------|---------------|
| `Garage61SyncLog` | • `user` → `users.User` |

---

### simlane.sim (🚨 _largest domain area_)

| Model | Relationships (↙ inbound / ↘ outbound) |
|-------|-----------------------------------------|
| `Simulator` | ↘ `SimProfile`, `SimCar`, `SimTrack`, `Event`, `RatingSystem` |
| `SimProfile` | • `user` → `users.User` <br/> • `simulator` → `Simulator` <br/> ↘ `LapTime`, `ProfileRating` |
| `CarClass` | ↘ `CarModel`, `EventClass` |
| `CarModel` | • `car_class` → `CarClass` <br/> ↘ `SimCar` |
| `PitData` | ↙ `SimCar`, `SimLayout` _(one-to-one)_ |
| `SimCar` | • `simulator` → `Simulator` <br/> • `car_model` → `CarModel` <br/> • `pit_data` → `PitData` _(O2O)_ <br/> ↙ `EventEntry` |
| `TrackModel` | ↘ `SimTrack` |
| `SimTrack` | • `simulator` → `Simulator` <br/> • `track_model` → `TrackModel` <br/> ↘ `SimLayout` |
| `SimLayout` | • `sim_track` → `SimTrack` <br/> • `pit_data` → `PitData` _(O2O)_ <br/> ↙ `Event`, `LapTime` |
| `Series` | ↘ `Event` |
| `Event` | • `series` → `Series` _(nullable)_ <br/> • `simulator` → `Simulator` <br/> • `sim_layout` → `SimLayout` <br/> ↘ `EventSession`, `EventClass`, `EventInstance`, `EventEntry` |
| `EventSession` | • `event` → `Event` |
| `EventClass` | • `event` → `Event` <br/> • `car_class` → `CarClass` _(nullable)_ <br/> ↙ `EventEntry` |
| `EventInstance` | • `event` → `Event` <br/> ↘ `WeatherForecast`, `DriverAvailability`, `PredictedStint` |
| `LapTime` | • `sim_profile` → `SimProfile` <br/> • `sim_layout` → `SimLayout` |
| `RatingSystem` | • `simulator` → `Simulator` <br/> ↘ `ProfileRating` |
| `ProfileRating` | • `sim_profile` → `SimProfile` <br/> • `rating_system` → `RatingSystem` |
| `WeatherForecast` | • `event_instance` → `EventInstance` |

---

### simlane.teams

| Model | Relationships |
|-------|---------------|
| `Club` | ↘ `ClubMember`, `Team`, `DiscordGuild` |
| `ClubMember` | • `user` → `users.User` <br/> • `club` → `Club` |
| `Team` | • `club` → `Club` <br/> ↘ `TeamMember`, `EventEntry` |
| `TeamMember` | • `team` → `Team` <br/> • `user` → `users.User` |
| `EventEntry` | • `event` → `sim.Event` <br/> • `sim_car` → `sim.SimCar` <br/> • `team` → `Team` _(nullable)_ <br/> • `user` → `users.User` _(nullable)_ <br/> • `event_class` → `sim.EventClass` _(nullable)_ <br/> ↘ `DriverAvailability`, `PredictedStint` |
| `DriverAvailability` | • `event_entry` → `EventEntry` <br/> • `user` → `users.User` <br/> • `instance` → `sim.EventInstance` |
| `PredictedStint` | • `event_entry` → `EventEntry` <br/> • `user` → `users.User` <br/> • `instance` → `sim.EventInstance` |

> NOTE: Many smaller fields (timestamps, JSON blobs, indexes, etc.) are omitted here for brevity. Always consult the actual model file before making schema changes.

---

### Entity-Relationship Diagram (high-level)

The following Mermaid diagram visualises the _core_ relationships among the most frequently accessed tables (omitting supporting look-up tables for clarity): 