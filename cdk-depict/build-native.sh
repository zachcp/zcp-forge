#!/bin/bash
# Experiment with stock GraalVM; never silently fall back to a JVM launcher.
# Usage: JAVA_HOME=/path/to/graalvm build-native.sh INSTALLED_PREFIX OUTPUT_DIR
set -euo pipefail
prefix=$(CDPATH= cd -- "${1:?Provide the installed cdk-depict prefix}" && pwd)
mkdir -p "${2:?Provide an output directory}"
out=$(CDPATH= cd -- "$2" && pwd)
recipe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app="$prefix/share/cdk-depict"
: "${JAVA_HOME:?Set JAVA_HOME to the GraalVM installation}"
"$JAVA_HOME/bin/native-image" --version

# Collect reflection/JNI/resources from the full CLI test matrix, not just --help.
mkdir -p "$out/config"
# A warm Java font cache skips JNI calls required on fresh installations.
training_home=$(mktemp -d "$out/font-training.XXXXXX")
DEPICT_COMMAND="\"$JAVA_HOME/bin/java\" -Djava.awt.headless=true -cp \"$app/cli:$app/lib/*\" org.openscience.cdk.app.DepictCli" \
JAVA_TOOL_OPTIONS="-Duser.home=\"$training_home\" -agentlib:native-image-agent=config-merge-dir=\"$out/config\"" \
DEPICT_SKIP_WEB=1 "${PYTHON:-python}" "$recipe/test_depict.py"
rm -r "$training_home"

"$JAVA_HOME/bin/native-image" \
    -J-Xmx"${NATIVE_IMAGE_XMX:-2000m}" -J-XX:-UseParallelGC -J-XX:+UseSerialGC \
    --parallelism="${NATIVE_IMAGE_THREADS:-1}" -Ob -march=compatibility \
    --native-compiler-path="$(command -v "${CC:-cc}")" \
    -H:CLibraryPath="${PREFIX:-$prefix}/lib" \
    -Djava.awt.headless=true \
    -H:ConfigurationFileDirectories="$out/config" \
    -cp "$app/cli:$app/lib/*" \
    org.openscience.cdk.app.DepictCli "$out/cdk-depict-native"

# A successful compilation alone is not a successful native renderer.
mkdir -p "$out/lib"
cp "$JAVA_HOME/lib/psfontj2d.properties" "$out/lib/"
DEPICT_COMMAND="\"$out/cdk-depict-native\" -Djava.home=\"$out\"" DEPICT_SKIP_WEB=1 \
    "${PYTHON:-python}" "$recipe/test_depict.py"
