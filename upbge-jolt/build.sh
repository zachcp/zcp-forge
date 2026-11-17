#!/bin/bash
# The jolt half of upbge-jolt's build (docs/getting-started.md, deps.edn
# tasks): jolt test, jolt lib. Blender comes prebuilt from upbge-jolt-engine.
set -euxo pipefail

jolt --version

# headless tests against the mock shim, then the runtime library
jolt test
jolt lib

DEST="$PREFIX/lib/upbge-jolt"
mkdir -p "$DEST" "$PREFIX/bin"
cp native/libjolt_upbge.dylib "$DEST/"
# the jolt sources, for (load-file ...) over nREPL
cp -R src "$DEST/src"

# host/run.sh, pointed at the installed app and runtime
cat > "$PREFIX/bin/upbge-jolt" <<'SH'
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
SH
chmod 0755 "$PREFIX/bin/upbge-jolt"
