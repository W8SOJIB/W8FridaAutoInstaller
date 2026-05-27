import os
import subprocess
import json
import urllib.request

def run(cmd, critical=True):
    print(f"\n[+] {cmd}")
    code = os.system(cmd)
    if code != 0:
        print(f"[!] FAILED: {cmd}")
        if critical:
            exit(1)
        return False
    return True

def get_output(cmd):
    return subprocess.getoutput(cmd).strip()

print("\n[*] Detecting CPU architecture...")
abi = get_output("getprop ro.product.cpu.abi")
print("[+] ABI:", abi)

if "arm64" in abi:
    arch = "android-arm64"
elif "armeabi" in abi or "arm" in abi:
    arch = "android-arm"
elif "x86_64" in abi:
    arch = "android-x86_64"
else:
    print("[-] Unsupported architecture")
    exit(1)

print("[+] Using arch:", arch)

print("\n[*] Installing dependencies...")
run("pkg install wget xz-utils python clang make openssl libffi rust -y")

print("\n[*] Installing frida-tools (FIXED METHOD)...")
run("pip install --no-cache-dir frida-tools --break-system-packages", critical=False)

print("\n[*] Getting latest Frida version...")
api = "https://api.github.com/repos/frida/frida/releases/latest"

try:
    data = json.loads(urllib.request.urlopen(api).read().decode())
    version = data["tag_name"]
    ver = version.replace("v", "")
except:
    print("[-] Failed to fetch version")
    exit(1)

filename = f"frida-server-{ver}-{arch}.xz"
url = f"https://github.com/frida/frida/releases/download/{version}/{filename}"

print("[+] Version:", ver)
print("[+] Download URL:", url)

print("\n[*] Downloading Frida server...")
run(f"wget -O {filename} {url}")

print("\n[*] Extracting...")
run(f"unxz -f {filename}")

server = filename.replace(".xz", "")

print("\n[*] Renaming...")
run(f"mv {server} frida-server")

print("\n[*] Making executable...")
run("chmod +x frida-server")

print("\n[*] Moving to root location and starting...")
root_cmd = """
mv frida-server /data/local/tmp/
chmod 755 /data/local/tmp/frida-server
pkill frida-server
/data/local/tmp/frida-server &
"""

run(f"su -c '{root_cmd}'")

print("\n[*] Testing frida connection...")
run("frida-ps -U", critical=False)

print("\n[✓] DONE")
print("[*] If frida-ps not found, run: pip install frida-tools")
