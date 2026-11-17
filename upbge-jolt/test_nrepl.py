"""Start upbge-jolt headless and evaluate (+ 1 2) over its nREPL server."""
import os
import socket
import subprocess
import sys
import tempfile
import time

port_file = os.path.join(tempfile.mkdtemp(), "nrepl-port")
env = dict(os.environ, UPBGE_JOLT_PORT_FILE=port_file)
proc = subprocess.Popen(["upbge-jolt", "headless"], env=env)
try:
    deadline = time.time() + 120
    while not (os.path.exists(port_file) and open(port_file).read().strip()):
        if proc.poll() is not None or time.time() > deadline:
            sys.exit(f"no nREPL port file (exit code {proc.poll()})")
        time.sleep(1)
    port = int(open(port_file).read())

    with socket.create_connection(("127.0.0.1", port), timeout=60) as s:
        code = "(+ 1 2)"
        s.sendall(f"d4:code{len(code)}:{code}2:op4:evale".encode())
        reply = b""
        while b"4:done" not in reply:
            chunk = s.recv(4096)
            if not chunk:
                break
            reply += chunk
    print(reply.decode(errors="replace"))
    if b"5:value1:3" not in reply:
        sys.exit("nREPL eval did not return 3")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
