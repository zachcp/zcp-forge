#!/bin/bash
# Blender half of upbge-jolt's build (docs/getting-started.md): clone UPBGE
# with its precompiled libraries, then host/integrate.sh.
set -euxo pipefail

# Let Blender's CMake pick its own minimum macOS version.
unset MACOSX_DEPLOYMENT_TARGET

# UPBGE at the pinned revision, with the precompiled platform libraries
# (`make update` without touching the pinned code). upbge-jolt's own
# `jolt upbge-deps` runs `make deps` instead, which compiles all of them.
mkdir -p native/upbge
(
  cd native/upbge
  git init -q
  git remote add origin https://github.com/UPBGE/upbge.git
  git fetch --depth 1 origin "$UPBGE_REV"
  git checkout -q FETCH_HEAD
  python3 build_files/utils/make_update.py --no-blender
)

# Newer macOS SDKs (27) declare Metal 4 types in headers Cycles includes,
# which Blender's -Werror turns into errors at its macOS 13 deployment target.
for v in CFLAGS CXXFLAGS OBJCFLAGS OBJCXXFLAGS; do
  export "$v=${!v:-} -Wno-error=unguarded-availability-new"
done

# patch UPBGE, configure and build Blender + the player into build_darwin/bin
bash host/integrate.sh

BIN="native/upbge/build_darwin/bin"
DEST="$PREFIX/lib/upbge-jolt"
mkdir -p "$DEST"
ditto "$BIN/Blender.app" "$DEST/Blender.app"
ditto "$BIN/Blenderplayer.app" "$DEST/Blenderplayer.app"
