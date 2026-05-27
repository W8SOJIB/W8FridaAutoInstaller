import os
import re
import json
import urllib.request
import subprocess

def run(cmd):
    print(f"\n[+] Running: {cmd}")
    os.system(cmd)

print("[*] Detecting CPU architecture...")

abi = subprocess.getoutput("getprop ro.product.cpu.abi").strip()
print(f"[+] CPU ABI: {abi}")

if "arm64" in abi:
    arch = "android-arm64"
elif "armeabi" in abi or "arm" in abi:
    arch = "android-arm"
elif "x86_64" in abi:
    arch = "android-x86_64"
elif "x86" in abi:
    arch = "android-x86"
else:
    print("[-] Unsupported architecture!")
    exit()

print(f"[+] Using Frida architecture: {arch}")

print("[*] Fetching latest Frida release...")

api_url = "https://api.github.com/repos/frida/frida/releases/latest"

try:
    with urllib.request.urlopen(api_url) as response:
        data = json.loads(response.read().decode())

    version = data["tag_name"]
    version_clean = version.replace("v", "")

    filename = f"frida-server-{version_clean}-{arch}.xz"
    download_url = f"https://github.com/frida/frida/releases/download/{version}/{filename}"

    print(f"[+] Latest Version: {version_clean}")
    print(f"[+] Download URL: {download_url}")

except Exception as e:
    print(f"[-] Failed to fetch release info: {e}")
    exit()

print("[*] Downloading Frida server...")
run(f"wget -O {filename} {download_url}")

print("[*] Extracting...")
run(f"unxz -f {filename}")

server_file = filename.replace(".xz", "")

print("[*] Renaming...")
run(f"mv {server_file} frida-server")

print("[*] Setting execute permission...")
run("chmod +x frida-server")

print("[*] Moving to /data/local/tmp/ and starting as root...")

root_commands = """
mv frida-server /data/local/tmp/
chmod 755 /data/local/tmp/frida-server
pkill frida-server
/data/local/tmp/frida-server &
"""

run(f'''su -c '{root_commands}' ''')

print("[*] Testing Frida connection...")
run("frida-ps -U")

print("\n[✓] Frida setup completed!")
