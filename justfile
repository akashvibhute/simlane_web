export COMPOSE_FILE := "docker-compose.yml"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments.
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands.
default:
    @just --list

# build: Build python image (web-only by default).
build config="web":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        echo "Building python image for web configuration..."
        doppler run -- docker compose build
    elif [ "{{config}}" = "full" ]; then
        echo "Building python image for full configuration..."
        doppler run -- docker compose -f docker-compose.full.yml build
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# up: Start up containers (web-only by default).
up config="web":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        echo "Starting up web containers..."
        doppler run --mount .env --mount-format env -- docker compose up --remove-orphans
    elif [ "{{config}}" = "full" ]; then
        echo "Starting up full containers..."
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml up --remove-orphans
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# up-web: Start web-only containers (Django, Postgres, Redis, Mailpit, Node).
up-web:
    @echo "Starting web-only containers..."
    @doppler run --mount .env --mount-format env -- docker compose up --remove-orphans

# up-full: Start all containers including Celery services.
up-full:
    @echo "Starting full containers including Celery..."
    @doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml up --remove-orphans

# down: Stop containers (attempts to stop all configurations).
down:
    @echo "Stopping containers..."
    @doppler run --mount .env --mount-format env -- docker compose down 2>/dev/null || true
    @doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml down 2>/dev/null || true

# prune: Remove containers and their volumes.
prune *args:
    @echo "Killing containers and removing volumes..."
    @doppler run --mount .env --mount-format env -- docker compose down -v {{args}} 2>/dev/null || true
    @doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml down -v {{args}} 2>/dev/null || true

# logs: View container logs (specify config and optional service names)
logs config *args:
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        doppler run -- docker compose logs -f {{args}}
    elif [ "{{config}}" = "full" ]; then
        doppler run -- docker compose -f docker-compose.full.yml logs -f {{args}}
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# logs-web: View container logs for web config
logs-web *args:
    @doppler run -- docker compose logs -f {{args}}

# logs-full: View container logs for full config  
logs-full *args:
    @doppler run -- docker compose -f docker-compose.full.yml logs -f {{args}}

# manage: Executes `manage.py` command (uses web config by default).
manage +args:
    @doppler run --mount .env --mount-format env -- docker compose run --rm django python ./manage.py {{args}}

# status: Show running containers
status:
    @echo "=== Running containers ==="
    @docker ps --filter "name=simlane_local"

# shell: Open a shell in the Django container
shell config="web":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        doppler run --mount .env --mount-format env -- docker compose exec django /bin/bash
    elif [ "{{config}}" = "full" ]; then
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml exec django /bin/bash
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# psql: Connect to PostgreSQL database
psql config="web":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        doppler run --mount .env --mount-format env -- docker compose exec postgres psql -U postgres simlane
    elif [ "{{config}}" = "full" ]; then
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml exec postgres psql -U postgres simlane
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# redis-cli: Connect to Redis
redis-cli config="web":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        doppler run --mount .env --mount-format env -- docker compose exec redis redis-cli
    elif [ "{{config}}" = "full" ]; then
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml exec redis redis-cli
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# flower: Open Flower monitoring (only works with full config)
flower:
    @echo "Starting Flower monitoring (requires full configuration)..."
    @doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml up -d flower
    @echo "Flower available at: http://localhost:5555"

# restart: Restart a specific service
restart config="web" service="django":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        echo "Restarting {{service}} service..."
        doppler run --mount .env --mount-format env -- docker compose restart {{service}}
    elif [ "{{config}}" = "full" ]; then
        echo "Restarting {{service}} service..."
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml restart {{service}}
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi

# rebuild: Rebuild and restart a service
rebuild config="web" service="django":
    #!/usr/bin/env bash
    if [ "{{config}}" = "web" ]; then
        echo "Rebuilding and restarting {{service}}..."
        doppler run -- docker compose build {{service}}
        doppler run --mount .env --mount-format env -- docker compose up -d {{service}}
    elif [ "{{config}}" = "full" ]; then
        echo "Rebuilding and restarting {{service}}..."
        doppler run -- docker compose -f docker-compose.full.yml build {{service}}
        doppler run --mount .env --mount-format env -- docker compose -f docker-compose.full.yml up -d {{service}}
    else
        echo "Unknown config: {{config}}. Use 'web' or 'full'"
        exit 1
    fi
