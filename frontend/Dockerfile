# ReefShield Aqaba — frontend dev container.
#
# The compose build context is ./frontend, so nothing outside this directory is
# reachable at build time. That is why the derived basemap, the six woff2 faces
# and the vendored MapLibre RTL plugin are all committed under public/ rather
# than generated here — see scripts/13_frontend_basemap.py, which runs in the
# worker container because the geospatial stack lives there.

FROM node:22-bookworm-slim AS dev

# glibc, not alpine. Vite 8 pulls rolldown and lightningcss, both native Rust
# addons; their musl builds exist but are the least-exercised path, and this is a
# ten-day window.

ENV NODE_ENV=development \
    CI=true
WORKDIR /app

# Lockfile first, so editing a component does not reinstall the world.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host is not optional. Vite binds 127.0.0.1 by default, which is unreachable
# from the host even with 5173:5173 published. vite.config.ts sets `host: true`
# as well; both are here because either one alone is a silent failure if the
# other is edited.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--strictPort"]
