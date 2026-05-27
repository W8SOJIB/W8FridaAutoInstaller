import os
import subprocess
import urllib.request
import json
import time
import sys

def run(cmd, critical=True):
    print(f"\n[+] {cmd}")
    code = os.system(cmd)
    if code != 0:
        print(f"[!] FAILED: {cmd}")
        if critical:
            exit(1)
        return False
    return True

def out(cmd):
    return subprocess.getoutput(cmd).strip()

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
LIBPYTHON = f"{PREFIX}/lib/libpython{sys.version_info.major}.{sys.version_info.minor}.so"
FRIDA_HOST = "127.0.0.1:27042"

def frida_env_cmd(cmd):
    return f"LD_PRELOAD={LIBPYTHON} {cmd}"

def run_with_timeout(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[!] Timed out: {cmd}")
        return False

def test_frida_connection():
    return run_with_timeout(frida_env_cmd(f"frida-ps -H {FRIDA_HOST}"), timeout=10)

def fix_frida_tool_wrappers():
    if not os.path.exists(LIBPYTHON):
        return False

    repaired = False
    for tool in ["frida", "frida-ps", "frida-ls-devices", "frida-trace", "frida-discover", "frida-kill", "frida-apk"]:
        path = out(f"command -v {tool}")
        if not path or not os.path.isfile(path):
            continue

        real_path = f"{path}.real"
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                current = fh.read(256)
            if "W8FRIDA_LDPRELOAD_WRAPPER" in current:
                repaired = True
                continue
            if not os.path.exists(real_path):
                os.rename(path, real_path)
            wrapper = (
                "#!/data/data/com.termux/files/usr/bin/sh\n"
                "# W8FRIDA_LDPRELOAD_WRAPPER\n"
                f"export LD_PRELOAD=\"{LIBPYTHON}${{LD_PRELOAD:+:$LD_PRELOAD}}\"\n"
                f"exec \"{real_path}\" \"$@\"\n"
            )
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(wrapper)
            os.chmod(path, 0o755)
            repaired = True
        except OSError as exc:
            print(f"[!] Could not repair {tool}: {exc}")

    return repaired

print("\n[*] Updating Termux & installing dependencies...")
run("pkg update -y && pkg upgrade -y", critical=False)

run("pkg install wget xz-utils python git which frida-python -y")

# --- FIX frida-tools install (TERMUX FIRST) ---
def install_frida_tools():
    print("\n[*] Installing frida-tools...")

    fix_frida_tool_wrappers()

    if os.system(frida_env_cmd("frida-ps --version")) == 0:
        print("[+] frida-tools already installed")
        return True

    print("\n[*] Trying Termux package: pkg install frida-python -y")
    if run("pkg install frida-python -y", critical=False):
        fix_frida_tool_wrappers()
        if os.system(frida_env_cmd("frida-ps --version")) == 0:
            print("[+] frida-tools installed successfully")
            return True

    print("[!] Termux package did not provide frida-ps, trying pip fallback...")

    commands = [
        "pip install frida-tools --no-cache-dir --break-system-packages --only-binary=:all:",
        "pip install frida-tools --no-cache-dir --only-binary=:all:"
    ]
    for c in commands:
        print(f"\n[*] Trying: {c}")
        if run(c, critical=False):
            fix_frida_tool_wrappers()
            if os.system(frida_env_cmd("frida-ps --version")) == 0:
                print("[+] frida-tools installed successfully")
                return True

    print("[-] frida-tools install failed")
    return False

# --- architecture detect ---
print("\n[*] Detecting architecture...")
abi = out("getprop ro.product.cpu.abi")
print("[+] ABI:", abi)

if "arm64" in abi:
    arch = "android-arm64"
elif "armeabi" in abi or "arm" in abi:
    arch = "android-arm"
elif "x86_64" in abi:
    arch = "android-x86_64"
else:
    print("[-] Unsupported arch")
    exit(1)

print("[+] Arch:", arch)

# --- install frida-tools ---
tools_ok = install_frida_tools()

def get_installed_frida_version():
    version = out(frida_env_cmd("python -c \"import frida; print(frida.__version__)\""))
    if version and "Traceback" not in version and "ModuleNotFoundError" not in version:
        return version
    return ""

# --- get matching frida version ---
print("\n[*] Detecting Frida version...")
ver = get_installed_frida_version()

if ver:
    version = ver
    print("[+] Using installed frida-python version:", ver)
else:
    print("[!] Could not detect installed frida-python version")
    print("[*] Fetching latest Frida version...")
    api = "https://api.github.com/repos/frida/frida/releases/latest"
    data = json.loads(urllib.request.urlopen(api).read().decode())
    version = data["tag_name"]
    ver = version.replace("v", "")

file = f"frida-server-{ver}-{arch}.xz"
url = f"https://github.com/frida/frida/releases/download/{version}/{file}"

print("[+] Version:", ver)
print("[+] Download:", url)

# --- download ---
print("\n[*] Downloading...")
run(f"wget -O {file} {url}")

# --- extract ---
print("\n[*] Extracting...")
run(f"unxz -f {file}")

binfile = file.replace(".xz", "")

# --- rename ---
run(f"mv {binfile} frida-server")
run("chmod +x frida-server")

# --- root install + start ---
print("\n[*] Starting frida-server as root...")
root_cmd = """
mv frida-server /data/local/tmp/
chmod 755 /data/local/tmp/frida-server
pkill frida-server
nohup /data/local/tmp/frida-server >/dev/null 2>&1 &
"""

run(f"su -c '{root_cmd}'")

# --- wait ---
time.sleep(3)

# --- test ---
print("\n[*] Testing frida connection...")
if not test_frida_connection():
    print("[!] frida-ps not working, auto-repairing...")

    run("pkg install frida-python -y", critical=False)
    fix_frida_tool_wrappers()

    print("\n[*] Retesting...")
    tools_ok = test_frida_connection()
else:
    tools_ok = True

if not tools_ok:
    print("[-] frida-ps is still not working.")
    print(f"[-] Try manually: LD_PRELOAD={LIBPYTHON} frida-ps -H {FRIDA_HOST}")
    exit(1)

print("\n[OK] FULL AUTO FRIDA INSTALL COMPLETE")
