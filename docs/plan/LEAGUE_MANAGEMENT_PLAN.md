# League Management — Implementation Road-map  
_Created: June 2025_

This document captures the agreed-upon plan for adding League functionality to SimLane.  
(It deliberately keeps the existing "Club" terminology; no database or API renaming is scheduled.)

---

## 1  Overview

We will extend the current data-model so that a **Series** can act as a user- or club-run _League_.  
Key goals:

1. Any authenticated user can create a league without first setting up a Club.  
2. A Club owner can host multiple leagues under the Club umbrella.  
3. Custom scoring rules & automatic Season standings.  
4. Personal "one-click" organiser flow: if the user lacks a Club, the system silently creates a private **Personal Club** for them.  
5. All changes are additive; no breaking migrations.

Total effort ≈ 4–5 dev-weeks spread across three sprints.

---

## 2  Back-end / DB (Sprint 1)

| Item | Description |
|------|-------------|
| **M1 — Series fields** | Add to `sim.Series`<br>• `organising_club` FK → teams.Club<br>• `organising_user` FK → users.User<br>• `visibility` (choices already exist on Event)<br>• `registration_opens`, `registration_closes` (optional)<br>• `scoring_rules` JSON<br>Constraint: exactly **one** of `organising_club` / `organising_user` must be set when `is_official = False`. |
| **M2 — SeasonStanding** | New table storing points & positions per Season.<br>Polymorphic participant: FK `team` *or* FK `user` with check-constraint. |
| **Admin** | Extend `SeriesAdmin`; add inline for SeasonStanding. |
| **Migrations** | `just manage makemigrations sim` → check in. |

---

## 3  Services / Business Logic (Sprint 1-2)

1. **LeagueCreationService**  
   Input: organiser (user or club) + meta → creates Series row.  
   If user has no admin clubs ⇒ create "Personal Club" (`is_public=False`).

2. **Standings Engine**  
   Celery task triggered on `EventResult.save`:  
   • apply league `scoring_rules`  
   • update/create SeasonStanding rows  
   • recalc positions.

---

## 4  API / Routers (Sprint 2)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/series/?type=league` | list leagues |
| POST | `/api/series/` | create league (organiser chosen) |
| POST | `/api/series/{id}/seasons/` | create season |
| GET | `/api/seasons/{id}/standings/` | current points table |

Permissions: organiser user or Club admin can modify; visibility enforced for reads.

---

## 5  Front-end (HTMX / Tailwind) (Sprint 2 ½)

1. "Create League" modal  
   • Selector: existing Club / "Just me" / "New Club".  
   • Scoring-rules textarea (JSON for v1).

2. Series list filter: tabs **Official** • **Leagues**.

3. Season Standings page: HTMX table, auto updates post-event.

4. Club dashboard: new "Leagues" tab showing Series where `organising_club = club`.

---

## 6  Mobile Preparation (Sprint 3 parallel)

• Document JSON schema & auth ﬂow in `docs/mobile/league_endpoints.md`.  
• Provide filtered endpoints by organiser for mobile consumption.

---

## 7  QA & Testing

Unit tests  
• Model constraints, permission helpers, scoring maths.

Integration / e2e  
• Cypress: create league → add season → ingest dummy EventResult → verify standings.

Regression  
• Existing Club workflows (member invite, event sign-up) must still pass.

---

## 8  Release Strategy / Feature Flag

1. Add `FEATURE_LEAGUES = False` (default) in `config/settings/local.py`.  
2. Wrap new menu items & routes behind the flag.  
3. Turn on in staging after Sprint 2 QA; promote to prod once stable.

---

## 9  Timeline Summary

| Sprint | Deliverables |
|--------|--------------|
| 1 | DB migrations, admin, LeagueCreation service |
| 2 | Standings engine, API routes, HTMX CRUD UI |
| 3 | Mobile docs/API polish, full QA, feature flag live |

---

## 10  Run-book (dev)

```bash
# After merging model changes
just manage makemigrations sim
just manage migrate

# Run lint + tests
pre-commit run --all-files
pytest

# Bring stack up (auto-reload)
just up
```

---

_End of document_ 