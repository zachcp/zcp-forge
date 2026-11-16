#!/bin/bash
# Follows upbge-jolt's own build (docs/getting-started.md, deps.edn tasks):
# jolt test, jolt lib, clone UPBGE + prebuilt libs, host/integrate.sh.
set -euxo pipefail

# Let Blender's CMake pick its own minimum macOS version.
unset MACOSX_DEPLOYMENT_TARGET

# jolt, from the release tarball in the sources
JOLT_BIN="$(find "$SRC_DIR/_jolt" -maxdepth 2 -type f -name jolt | head -1)"
chmod +x "$JOLT_BIN"
export PATH="$(dirname "$JOLT_BIN"):$PATH"
jolt --version

# threaded Chez Scheme for `jolt build --library`
CHEZ_PREFIX="$SRC_DIR/_chez_install"
(
  cd "$SRC_DIR/_chez"
  ./configure --threads --disable-x11 --installprefix="$CHEZ_PREFIX"
  make -j"$(sysctl -n hw.ncpu)"
  make install
)
export PATH="$CHEZ_PREFIX/bin:$PATH"
export JOLT_CHEZ_CSV="$(echo "$CHEZ_PREFIX"/lib/csv*/tarm64osx)"

# headless tests against the mock shim, then the runtime library
jolt test
jolt lib

# UPBGE at the pinned revision, with the prebuilt platform libraries
# (`make update` without touching the pinned code)
mkdir -p native/upbge
(
  cd native/upbge
  git init -q
  git remote add origin https://github.com/UPBGE/upbge.git
  git fetch --depth 1 origin "$UPBGE_REV"
  git checkout -q FETCH_HEAD
  python3 build_files/utils/make_update.py --no-blender
)

# patch UPBGE, configure and build Blender + the player into build_darwin/bin
bash host/integrate.sh

BIN="native/upbge/build_darwin/bin"
DEST="$PREFIX/lib/upbge-jolt"
mkdir -p "$DEST" "$PREFIX/bin"
ditto "$BIN/Blender.app" "$DEST/Blender.app"
ditto "$BIN/Blenderplayer.app" "$DEST/Blenderplayer.app"
cp native/libjolt_upbge.dylib "$DEST/"
# the jolt sources, for (load-file ...) over nREPL
cp -R src "$DEST/src"

# host/run.sh, pointed at the installed app and runtime
cat > "$PREFIX/bin/upbge-jolt" <<'EOF'
#!/bin/bash
# upbge-jolt [editor|play|headless] [scene.blend] [blender args]
set -euo pipefail
DIR="$(cd "$(dirname "$0")/../lib/upbge-jolt" && pwd)"
MODE="${1:-editor}"
case "$MODE" in
  editor|play|headless) shift || true ;;
  *) MODE=editor ;;
esac
export UPBGE_JOLT="$MODE"
export UPBGE_JOLT_LIB="${UPBGE_JOLT_LIB:-$DIR/libjolt_upbge.dylib}"
export UPBGE_JOLT_PORT_FILE="${UPBGE_JOLT_PORT_FILE:-$PWD/.nrepl-port}"
BLENDER="$DIR/Blender.app/Contents/MacOS/Blender"
if [ "$MODE" = headless ]; then
  exec "$BLENDER" -b "$@"
fi
exec "$BLENDER" "$@"
EOF
chmod 0755 "$PREFIX/bin/upbge-jolt"
