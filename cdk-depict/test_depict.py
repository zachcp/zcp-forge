"""Black-box rendering contract; also runs unchanged against a native executable.

DEPICT_COMMAND overrides the installed CLI. DEPICT_WEB_URL additionally checks
the running upstream server and compares its PNG/SVG output with the CLI.
"""
import io
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image


COMMAND = shlex.split(os.environ.get("DEPICT_COMMAND", "cdk-depict"))
SVG = "{http://www.w3.org/2000/svg}"


class DepictTests(unittest.TestCase):
    def cli(self, *args, stdin=None, success=True):
        result = subprocess.run(
            [*COMMAND, *args], input=stdin, capture_output=True, timeout=60
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"cdk-depict:", result.stderr)
            self.assertEqual(result.stdout, b"")
        return result.stdout

    def image(self, data, fmt):
        if fmt == "png":
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            image = Image.open(io.BytesIO(data))
            image.load()  # Decode pixels, not just the file header.
            self.assertGreater(image.width, 1)
            self.assertGreater(image.height, 1)
            self.assertGreater(image.convert("RGBA").getextrema()[3][1], 0)
            self.assertGreater(len(image.getcolors(image.width * image.height)), 1)
            return image
        root = ET.fromstring(data)
        self.assertEqual(root.tag, SVG + "svg")
        self.assertIn("viewBox", root.attrib)
        self.assertTrue(list(root.iter(SVG + "path")) or list(root.iter(SVG + "line")))
        self.assertNotIn(b"NaN", data)
        return root

    def render(self, smi, fmt, *args):
        return self.cli("--smiles", smi, "--format", fmt, *args)

    def test_help_and_version(self):
        self.assertIn(b"Usage:", self.cli("--help"))
        self.assertIn(b"1.17", self.cli("--version"))

    def test_chemistry(self):
        # Heteroatom labels, aromaticity, stereo wedges, charges/isotopes,
        # disconnected salts, reactions, CXSMILES and abbreviation resources.
        molecules = {
            "ethanol": "CCO",
            "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
            "caffeine": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "stereo": "N[C@@H](C)C(=O)O",
            "isotopes": "[13CH3][NH3+].[Cl-]",
            "reaction": "CCO>>CC=O",
            "cxsmiles": "CCO |$;;oxygen$|",
            "abbreviations": "CCOC(=O)c1ccccc1",
        }
        for name, smi in molecules.items():
            for fmt in ("png", "svg"):
                with self.subTest(molecule=name, format=fmt):
                    self.image(self.render(smi, fmt), fmt)

    def test_styles(self):
        for style in ("cow", "cob", "cot", "bow", "wob", "bot", "wot", "nob"):
            for fmt in ("png", "svg"):
                with self.subTest(style=style, format=fmt):
                    self.image(self.render("NCCO", fmt, "--style", style), fmt)

    def test_dimensions_and_transparency(self):
        args = ("--param", "w=321", "--param", "h=187", "--param", "bgcolor=transparent")
        png = self.image(self.render("NCCO", "png", *args), "png")
        self.assertEqual(png.size, (321, 187))
        self.assertEqual(png.convert("RGBA").getpixel((0, 0))[3], 0)
        svg = self.image(self.render("NCCO", "svg", *args, "--param", "svgunits=px"), "svg")
        self.assertEqual(float(svg.attrib["width"].removesuffix("px")), 321)
        self.assertEqual(float(svg.attrib["height"].removesuffix("px")), 187)

    def test_annotations_and_highlights(self):
        for params in (("annotate=cip",), ("annotate=number",), ("sma=CO",), ("abbr=off", "hdisp=explicit")):
            for fmt in ("png", "svg"):
                with self.subTest(params=params, format=fmt):
                    args = [arg for value in params for arg in ("--param", value)]
                    data = self.render("C[C@H](O)C(=O)O", fmt, *args)
                    self.image(data, fmt)
                    baseline = self.render("C[C@H](O)C(=O)O", fmt)
                    self.assertNotEqual(data, baseline)

    def test_files_stdin_and_format_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input with spaces.smi"
            source.write_text("CCO", encoding="utf-8")
            for fmt in ("png", "svg"):
                target = Path(tmp) / f"output with spaces.{fmt}"
                self.assertEqual(self.cli("--input", str(source), "--output", str(target)), b"")
                self.image(target.read_bytes(), fmt)
                self.assertEqual(target.read_bytes(), self.cli("--input", "-", "--format", fmt, stdin=b"CCO"))
            self.image(self.cli("--input", "-", stdin=b"CCO"), "svg")

    def test_mol_input(self):
        mol = b"""ethanol
  test

  3  2  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500    1.2990    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  1  0  0  0  0
M  END
"""
        for fmt in ("png", "svg"):
            with self.subTest(format=fmt):
                self.image(self.cli("--input", "-", "--format", fmt, stdin=mol), fmt)

    def test_invalid_arguments_and_input(self):
        cases = (
            (), ("--smiles",), ("--unknown", "x"),
            ("--smiles", "CCO", "--input", "-"),
            ("--smiles", ""), ("--smiles", "C1CC"),
            ("--smiles", "CCO", "--format", "pdf"),
            ("--smiles", "CCO", "--style", "missing"),
            ("--smiles", "CCO", "--param", "w"),
            ("--smiles", "CCO", "--param", "w=abc"),
            ("--input", "/nonexistent/cdk-depict-input.smi"),
        )
        for args in cases:
            with self.subTest(args=args):
                self.cli(*args, success=False)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bad.png"
            self.cli("--smiles", "C1CC", "--output", str(output), success=False)
            self.assertFalse(output.exists())

    @unittest.skipIf(os.environ.get("DEPICT_SKIP_WEB") == "1", "Web application tested separately")
    def test_web_cli_parity(self):
        base = os.environ.get("DEPICT_WEB_URL")
        if base:
            self.check_web(base.rstrip("/"))
            return
        # Exercise the packaged launcher too, without leaving a server running.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([*COMMAND, "--serve", f"--server.port={port}"], stdout=log, stderr=log)
            try:
                base = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 60
                while True:
                    try:
                        with urllib.request.urlopen(base, timeout=2):
                            break
                    except (OSError, TimeoutError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            log.seek(0)
                            self.fail("Web application did not start:\n" + log.read().decode(errors="replace"))
                        time.sleep(0.2)
                self.check_web(base)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    def check_web(self, base):
        with urllib.request.urlopen(base, timeout=30) as response:
            self.assertIn(b"html", response.read().lower())
        # The HTML alone loads even when the JavaScript dependency is a 404.
        for asset in ("webjars/jquery/3.7.1/jquery.min.js", "webjars/font-awesome/6.7.2/css/all.css", "js/depict.js"):
            with urllib.request.urlopen(f"{base}/{asset}", timeout=30) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 100)
        for fmt, mime in (("png", "image/png"), ("svg", "image/svg+xml")):
            for smi in ("CC(=O)Oc1ccccc1C(=O)O", "CCO>>CC=O"):
                with self.subTest(format=fmt, smiles=smi):
                    query = urllib.parse.urlencode({"smi": smi, "w": "321", "h": "187"})
                    with urllib.request.urlopen(f"{base}/depict/cow/{fmt}?{query}", timeout=30) as response:
                        self.assertEqual(response.headers.get_content_type(), mime)
                        data = response.read()
                    self.image(data, fmt)
                    self.assertEqual(data, self.render(smi, fmt, "--param", "w=321", "--param", "h=187"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
