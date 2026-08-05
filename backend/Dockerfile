# Two targets from one file, sharing a base layer.
#
#   api     serving only. Small, and the layer that gets rebuilt constantly.
#   worker  adds the geospatial stack for pipeline and simulation jobs.
#
# Python 3.12 rather than the host's 3.14: the geospatial wheels are mature
# there, and the container does not need to match the machine that built it.
# That independence is most of the reason to containerise at all.

# ─────────────────────────────────────────────────────────── base
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend/src

WORKDIR /app

# curl is here for the healthcheck, which is how Compose knows the service is
# actually answering rather than merely started.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root. A container that does not need to be root should not be.
RUN useradd --create-home --uid 10001 reefshield

# ─────────────────────────────────────────────────────────── api
FROM base AS api

# proj-data for coordinate transforms. The geopandas/pyproj wheels bundle their own
# PROJ, but not the datum grids, and the exposure engine cannot report an area without
# EPSG:4326 -> EPSG:32636. Same reason the worker target installs it; the api target
# needs it now that exposure.engine is imported at module scope.
#
# libexpat1 for rasterio's bundled GDAL (models/particle_engine.py's BathymetrySampler,
# imported at module scope by api/main.py since the particle engine landed) — same
# package the worker target installs for the same reason.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 proj-data \
 && rm -rf /var/lib/apt/lists/*

# Requirements copied alone first, so a code change does not invalidate the
# dependency layer. Rebuilds go from minutes to seconds.
COPY backend/requirements-api.txt /tmp/
RUN pip install --only-binary=:all: -r /tmp/requirements-api.txt

COPY --chown=reefshield:reefshield backend/ /app/backend/

# The one writable path, created BEFORE the volume is attached and owned by the
# non-root user. Docker seeds a fresh named volume from whatever the image has at the
# mount point, ownership included; if the directory does not exist in the image the
# volume lands owned by root and sqlite fails with "unable to open database file"
# despite the mount being present and writable-looking. That is what kept /alerts at
# a bare 500 after the volume was added.
RUN mkdir -p /app/var && chown reefshield:reefshield /app/var

USER reefshield

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "/app/backend/src"]

# ─────────────────────────────────────────────────────────── worker
FROM base AS worker

# GDAL/PROJ system libraries for rasterio and geopandas. The wheels bundle
# their own, but proj-data is needed for coordinate transforms - EPSG:4326 to
# UTM 36N is the one this project cannot do without.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libexpat1 proj-data \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-api.txt backend/requirements-worker.txt /tmp/
RUN pip install --only-binary=:all: -r /tmp/requirements-worker.txt

COPY --chown=reefshield:reefshield backend/ /app/backend/
COPY --chown=reefshield:reefshield scripts/ /app/scripts/
USER reefshield

# No EXPOSE and no port. The worker is not called; it picks work up.
CMD ["python", "-m", "worker.run"]
