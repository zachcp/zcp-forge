package org.openscience.cdk.app;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** File/stdout interface to the same controller used by the upstream web app. */
public final class DepictCli {
    public static void main(String[] args) {
        int status = 0;
        try {
            run(args);
        } catch (Exception ex) {
            System.err.println("cdk-depict: " + ex.getMessage());
            status = 1;
        }
        // The upstream controller owns a SMARTS executor, which otherwise keeps
        // a completed one-shot CLI invocation alive after highlighting.
        System.exit(status);
    }

    private static void run(String[] args) throws Exception {
        String smiles = null;
        String input = null;
        String output = "-";
        String format = null;
        String style = "cow";
        Map<String, String> params = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            String option = args[i];
            if (option.equals("--help")) {
                System.out.println("""
                    Usage: cdk-depict (--smiles SMILES | --input FILE) [options]
                      --input FILE      Read SMILES/CXSMILES or MOL text; '-' reads stdin
                      --output FILE     Write depiction; '-' writes stdout (default)
                      --format png|svg  Infer from output extension; stdout defaults to SVG
                      --style STYLE     cow (default), cob, cot, bow, wob, bot, wot, nob
                      --param KEY=VALUE Repeatable upstream web API option, e.g. w=640,
                                        h=360, annotate=cip, sma=CO, bgcolor=transparent
                      --version         Print the CDK Depict version
                      --help            Show this help
                    Web application: cdk-depict-web [Spring Boot options]
                    """);
                return;
            }
            if (option.equals("--version")) {
                System.out.println("CDK Depict 1.17 (CDK 2.14.1)");
                return;
            }
            if (!Set.of("--smiles", "--input", "--output", "--format", "--style", "--param").contains(option))
                throw new IllegalArgumentException("Unknown option: " + option);
            if (++i == args.length)
                throw new IllegalArgumentException("Missing value for " + option);
            String value = args[i];
            switch (option) {
                case "--smiles" -> smiles = value;
                case "--input" -> input = value;
                case "--output" -> output = value;
                case "--format" -> format = value.toLowerCase(Locale.ROOT);
                case "--style" -> style = value.toLowerCase(Locale.ROOT);
                case "--param" -> {
                    int separator = value.indexOf('=');
                    if (separator < 1)
                        throw new IllegalArgumentException("Expected --param KEY=VALUE");
                    params.put(value.substring(0, separator), value.substring(separator + 1));
                }
            }
        }
        if ((smiles == null) == (input == null))
            throw new IllegalArgumentException("Provide exactly one of --smiles or --input");
        if (input != null)
            smiles = input.equals("-")
                ? new String(System.in.readAllBytes(), StandardCharsets.UTF_8)
                : Files.readString(Path.of(input));
        if (smiles.isBlank())
            throw new IllegalArgumentException("Input must not be empty");
        if (format == null)
            format = output.equals("-") ? "svg" : output.substring(output.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
        if (!Set.of("png", "svg").contains(format))
            throw new IllegalArgumentException("Supported formats: png, svg");
        if (!Set.of("cow", "cob", "cot", "bow", "wob", "bot", "wot", "nob").contains(style))
            throw new IllegalArgumentException("Unknown style: " + style);
        byte[] bytes = (byte[]) new DepictController().depict(smiles, format, style, params).getBody();
        if (output.equals("-")) {
            System.out.write(bytes);
            System.out.flush();
        } else {
            Files.write(Path.of(output), bytes);
        }
    }
}
