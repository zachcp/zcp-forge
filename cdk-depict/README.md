# CDK Depict

Packages [`cdk/depict` 1.17](https://github.com/cdk/depict/tree/1.17), using
CDK 2.14.1. This is not `zachcp/cdk-cli`. The upstream Spring Boot web application
is retained, and a small Java CLI calls its `DepictController` directly. There
is no HTTP server involved in CLI rendering and no duplicate depiction engine.

## Build and use

```sh
rattler-build build --recipe cdk-depict/recipe.yaml -c conda-forge
```

The JVM recipe builds the source with Maven, runs all upstream tests, packages the
bootable WAR and CLI, and runs the installed-package tests. It currently targets
Linux and macOS; Windows is skipped because the launchers use a POSIX shell.
The JVM package needs Java 17 or newer and installs a font package.

Build the standalone native CLI separately (currently Linux x86-64 only):

```sh
rattler-build build --recipe cdk-depict/recipe-native.yaml -c conda-forge
```

This produces `cdk-depict-native`, with a command of the same name and no Java
runtime dependency. Install both packages to get the web app and native CLI;
their commands and installed files do not conflict. CI builds the JVM package
on its normal platforms and explicitly builds the native recipe on Linux.

```sh
cdk-depict --smiles 'CC(=O)Oc1ccccc1C(=O)O' --output aspirin.png
cdk-depict --smiles 'CCO>>CC=O' --output reaction.svg
cdk-depict --input molecule.mol --output molecule.png
printf '%s' 'N[C@@H](C)C(=O)O' | cdk-depict --input - --param annotate=cip > alanine.svg
cdk-depict --smiles NCCO --format png --param w=640 --param h=360 --param bgcolor=transparent > molecule.png
cdk-depict --serve --server.port=8080
cdk-depict-native --input molecule.mol --output molecule.svg
cdk-depict-native --serve --server.port=8080
cdk-depict-web --server.port=8080
```

Conversion is the default mode; it does not start a server. Put `--serve` first
to run the web application instead, forwarding remaining Spring Boot options.
Both packaged CLIs support it, and `cdk-depict-web` remains a direct server
command. Native `--serve` requires the optional `cdk-depict` JVM/web package in
the same environment and gives an actionable error when it is absent. The web
server still uses Java; native image conversion does not.

Open the web server's `/depict.html` page. Web API paths remain
`/depict/{style}/{format}?smi=...`. The recipe patches upstream's WebJar resource
location and uses explicit asset versions: otherwise jQuery and Font Awesome
return HTTP 404 on Spring 7 and the page cannot render structures.

CLI input is a single molecule/reaction, in SMILES, CXSMILES, or MOL text; it is
not a batch SMILES-file converter. Output defaults to SVG on stdout, or is
inferred from `.png`/`.svg` file extensions. `--format` overrides inference.
`--param KEY=VALUE` passes an option unchanged to the upstream controller; use
the web API parameter names (`w`, `h`, `sma`, `annotate`, `hdisp`, `abbr`, etc.).
Invalid requests fail with a nonzero exit status and an error on stderr, without
writing an output file. PNG data may have an alpha channel; view it against an
appropriate background.

## Tests

```sh
python cdk-depict/test_depict.py
DEPICT_COMMAND=/path/to/cdk-depict-native python cdk-depict/test_depict.py
```

Install Python and Pillow to run the tests outside `rattler-build`. The nine
test groups exercise both PNG and SVG for aromatic molecules, heteroatoms,
stereochemistry, isotopes/charges, salts, reactions, CXSMILES, abbreviations,
all eight styles, annotations, SMARTS highlighting, explicit hydrogens,
asymmetric dimensions, transparency, MOL input, stdin/stdout, file paths with
spaces, extension inference, and invalid inputs/options. PNGs are decoded and
checked for nonblank pixels; SVGs are parsed and checked for drawing elements.
Option tests also check that rendering actually changes.

The web test starts and stops the CLI's `--serve` mode, checks its page and
JavaScript/CSS assets, then compares molecule/reaction PNG and SVG responses
byte-for-byte with the CLI. Set `DEPICT_WEB_URL` to test an already-running
server instead. `DEPICT_SKIP_WEB=1` is reserved for CLI-only native testing.

## Stock GraalVM Native Image

Verified on Linux x86-64 with the latest GraalVM Community release available on
2026-11-23: **25.5.5.0.3+1.1**, JDK **25.0.5.0.3**. The native recipe pins the
toolchain archive and its SHA-256 checksum. Stock GraalVM successfully builds
the CLI and renders both PNG and SVG; no alternative GraalVM distribution is
used. The direct build took 6m26s with a peak RSS of 2.54 GiB, producing a
59.19 MiB executable plus eight companion libraries. All nine test groups,
including web/CLI output parity, passed against this native executable.
Both conda recipes also built successfully and passed their isolated
installed-package tests on Linux. The extracted native package passed all
nine groups against the running web application as well.

The first runtime attempt exposed AWT's requirement for `java.home` and a
`lib/` directory. The native package provides a small relocatable data directory
with the JDK's PostScript font properties, and its launcher sets `java.home`
there. This is not a bundled JVM: font discovery uses system Fontconfig and
FreeType. Keep the generated AWT/JNI libraries next to the executable and do
not rename the executable, because its shim libraries are bound to that name.

To build outside the native conda recipe, first install/build the JVM package
and provide a GraalVM installation, Python, and Pillow:

```sh
JAVA_HOME=/path/to/graalvm \
  bash cdk-depict/build-native.sh /path/to/installed/conda-prefix ./native-output
```

The script collects reflection, JNI, and resource metadata by running the full
CLI test matrix with GraalVM's tracing agent and an empty temporary `user.home`
directory. This prevents a warm font cache from hiding JNI calls
needed on fresh installations. It builds with `-march=compatibility`, then
reruns the same tests against the native executable. It defaults to a 2000 MB
builder heap, Serial GC, and one compiler thread for small build machines;
override `NATIVE_IMAGE_XMX`, `NATIVE_IMAGE_THREADS`, or `PYTHON` as needed.

For this direct build, invoke `native-output/cdk-depict-native` with
`-Djava.home=/absolute/path/to/native-output` before the CLI options. The conda
launcher's `cdk-depict-native` command supplies that property automatically.
The web WAR still runs on the JVM. Ship the complete native output, including
companion AWT libraries and the `lib/` directory, not just the executable.
