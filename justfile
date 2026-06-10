run-hass:
    @echo "Starting Home Assistant (dev)…"
    mkdir -p hass-state
    sudo podman run \
        --rm \
        --name homeassistant-dev \
        --net=host \
        --cap-add=NET_ADMIN \
        --cap-add=NET_RAW \
        -e DBUS_SYSTEM_BUS_ADDRESS="unix:path=/run/dbus/system_bus_socket" \
        -v "/run/dbus/system_bus_socket:/run/dbus/system_bus_socket" \
        -e TZ="America/New_York" \
        -v "./hass-state:/config/.storage" \
        -v "./configuration.yaml:/config/configuration.yaml:ro" \
        -v "./src/switchbot:/config/custom_components/switchbot:ro" \
        docker.io/homeassistant/home-assistant:stable

format:
    ruff check --fix
    ruff format

# Run the test suite.
test:
    uv run pytest

# Type-check, lint, and test — the full pre-commit gate.
check:
    uv run pyright src/switchbot tests
    uv run ruff check src tests
    uv run pytest

# Download + unpack + decompile the SwitchBot APK into ./decomp (gitignored).
decomp:
    tools/apk/switchbot-apk.sh all
