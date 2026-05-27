import os
import subprocess
import urllib.request
import json
import time

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

print("\n[*] Updating Termux & installing dependencies...")
run("pkg update -y && pkg upgrade -y", critical=False)

run("pkg install wget xz-utils python clang make openssl libffi rust git -y")

# --- FIX frida-tools install (AUTO RETRY SYSTEM) ---
def install_frida_tools():
    print("\n[*] Installing frida-tools (auto fix mode)...")

    commands = [
        "pip install frida-tools --no-cache-dir --break-system-packages",
        "pip install frida-tools --no-cache-dir",
        "pip install frida-tools"
    ]

    for c in commands:
        print(f"\n[*] Trying: {c}")
        if run(c, critical=False):
            # test
            if os.system("frida-ps --version") == 0:
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
install_frida_tools()

# --- get latest frida version ---
print("\n[*] Fetching latest Frida version...")
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
if os.system("frida-ps -U") != 0:
    print("[!] frida-ps not working, auto-repairing...")

    run("pip install --force-reinstall frida-tools --break-system-packages", critical=False)

    print("\n[*] Retesting...")
    os.system("frida-ps -U")

print("\n[✓] FULL AUTO FRIDA INSTALL COMPLETE")
