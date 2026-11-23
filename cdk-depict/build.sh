#!/bin/bash
set -euo pipefail

# Run the complete upstream reactor, including JUnit tests and bootable WAR.
mvn -B verify
app="$PREFIX/share/cdk-depict"
mkdir -p "$app/cli" "$app/lib" "$PREFIX/bin"
cp cdkdepict-webapp/target/cdkdepict-webapp-*.war "$app/cdkdepict.war"
# Reuse the WAR's exact dependencies, including Spring's provided HTTP types.
unzip -q "$app/cdkdepict.war" 'WEB-INF/lib/*' 'WEB-INF/lib-provided/*' -d extracted
cp extracted/WEB-INF/lib/*.jar extracted/WEB-INF/lib-provided/*.jar "$app/lib/"
javac --release 17 -cp "$app/lib/*" -d "$app/cli" "$RECIPE_DIR/DepictCli.java"
install -m 755 "$RECIPE_DIR/cdk-depict" "$RECIPE_DIR/cdk-depict-web" "$PREFIX/bin/"
