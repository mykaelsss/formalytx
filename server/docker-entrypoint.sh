#!/bin/sh
set -e

# A platform persistent disk (Render/Railway) mounts over the cache dir as a
# fresh, root-owned filesystem that is NOT seeded from the image, so the
# unprivileged runtime user can't write to it. Fix ownership of the mount root
# here (as root) before dropping privileges. Non-recursive: only the mount
# point needs fixing — entries we create afterward are already nonroot-owned.
dir="${FASTF1_CACHE_DIR:-/home/nonroot/.fastf1}"
if [ -d "$dir" ]; then
    chown nonroot:nonroot "$dir"
fi

exec gosu nonroot "$@"
