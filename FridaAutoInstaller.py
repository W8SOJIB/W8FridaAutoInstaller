import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request


TOOL_NAME = "W8FridaAutoInstaller"
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
LIBPYTHON = f"{PREFIX}/lib/libpython{sys.version_info.major}.{sys.version_info.minor}.so"
FRIDA_HOST = "127.0.0.1:27042"
LOCAL_TMP = "/data/local/tmp"

COLORS = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "blue": "\033[94m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

SCRIPT_ORDER = [
    "sslunpinning.js",
    "frida_ssl_multiple.js",
    "hidessl.js",
    "hidessl2.js",
    "sslunpinanti.js",
    "frida-ssl-script.js",
    "ssl.js",
    "FulterSSLUnpinning.js",
    "unissl.js",
    "unissl2.js",
    "AntiDebug.js",
]


def c(text, color):
    return f"{COLORS[color]}{text}{COLORS['reset']}"


def type_line(text, color="green", delay=0.006):
    for ch in text:
        print(c(ch, color), end="", flush=True)
        time.sleep(delay)
    print()


def banner():
    os.system("clear")
    print(c("=" * 48, "cyan"))
    type_line(f"        {TOOL_NAME}", "green", 0.01)
    print(c("        Termux Frida SSL Unpinning Tool", "yellow"))
    print(c("=" * 48, "cyan"))


def run(cmd, critical=True):
    print(c(f"\n[+] {cmd}", "cyan"))
    code = os.system(cmd)
    if code != 0:
        print(c(f"[!] FAILED: {cmd}", "red"))
        if critical:
            raise SystemExit(1)
        return False
    return True


def out(cmd):
    return subprocess.getoutput(cmd).strip()


def run_timeout(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            timeout=timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(c(f"[!] Timed out: {cmd}", "yellow"))
        return False


def frida_env_cmd(cmd):
    home = shlex.quote(f"{PREFIX}/tmp/frida-home")
    return (
        f"HOME={home} "
        f"XDG_CONFIG_HOME={home}/.config "
        f"XDG_CACHE_HOME={home}/.cache "
        f"XDG_DATA_HOME={home}/.local/share "
        f"LD_PRELOAD={shlex.quote(LIBPYTHON)} {cmd}"
    )


def frida_tool_ok():
    return run_timeout(frida_env_cmd("frida-ps --version"), timeout=8)


def frida_server_ok():
    return run_timeout(frida_env_cmd(f"frida-ps -H {FRIDA_HOST}"), timeout=8)


def detect_arch():
    abi = out("getprop ro.product.cpu.abi")
    print(c(f"[+] ABI: {abi}", "green"))

    if "arm64" in abi:
        return "android-arm64"
    if "armeabi" in abi or abi.startswith("arm"):
        return "android-arm"
    if "x86_64" in abi:
        return "android-x86_64"
    if abi == "x86":
        return "android-x86"

    print(c("[-] Unsupported Android ABI", "red"))
    raise SystemExit(1)


def fix_frida_tool_wrappers():
    if not os.path.exists(LIBPYTHON):
        print(c(f"[!] Missing {LIBPYTHON}", "yellow"))
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
            print(c(f"[!] Could not repair {tool}: {exc}", "yellow"))

    return repaired


def get_installed_frida_version():
    version = out(frida_env_cmd("python -c \"import frida; print(frida.__version__)\""))
    if version and "Traceback" not in version and "ModuleNotFoundError" not in version:
        return version
    return ""


def latest_frida_version():
    api = "https://api.github.com/repos/frida/frida/releases/latest"
    data = json.loads(urllib.request.urlopen(api).read().decode())
    tag = data["tag_name"]
    return tag.replace("v", "")


def install_termux_packages():
    print(c("\n[*] Updating Termux and installing dependencies...", "yellow"))
    run("pkg update -y && pkg upgrade -y", critical=False)
    run("pkg install root-repo -y", critical=False)
    run("pkg update -y", critical=False)
    return run("pkg install wget xz-utils python git which frida-python -y", critical=False)


def install_frida_tools():
    fix_frida_tool_wrappers()
    if frida_tool_ok():
        print(c("[OK] Frida tools are installed", "green"))
        return True

    print(c("[*] Reinstalling Termux frida-python...", "yellow"))
    run("pkg install frida-python -y", critical=False)
    fix_frida_tool_wrappers()

    if frida_tool_ok():
        print(c("[OK] Frida tools are ready", "green"))
        return True

    print(c("[-] Frida tools still failed. Termux package may be broken for this Python build.", "red"))
    return False


def download_frida_server():
    arch = detect_arch()
    ver = get_installed_frida_version() or latest_frida_version()
    file_name = f"frida-server-{ver}-{arch}.xz"
    bin_name = file_name.replace(".xz", "")
    url = f"https://github.com/frida/frida/releases/download/{ver}/{file_name}"

    print(c(f"[+] Frida version: {ver}", "green"))
    print(c(f"[+] Download: {url}", "green"))

    run(f"wget -O {shlex.quote(file_name)} {shlex.quote(url)}")
    run(f"unxz -f {shlex.quote(file_name)}")
    run(f"mv -f {shlex.quote(bin_name)} frida-server")
    run("chmod +x frida-server")

    root_cmd = (
        f"mkdir -p {LOCAL_TMP}; "
        f"cp {shlex.quote(os.path.abspath('frida-server'))} {LOCAL_TMP}/frida-server; "
        f"chmod 755 {LOCAL_TMP}/frida-server"
    )
    run(f"su -c {shlex.quote(root_cmd)}")
    print(c("[OK] frida-server installed to /data/local/tmp/frida-server", "green"))
    return True


def deploy_assets():
    actual_frida = out("command -v frida")
    if not actual_frida:
        print(c("[-] Could not find frida client on PATH", "red"))
        return False

    run(f"su -c {shlex.quote(f'mkdir -p {LOCAL_TMP}')}", critical=False)

    wrapper_path = os.path.join(LOCAL_TMP, "frida")
    wrapper = (
        "#!/data/data/com.termux/files/usr/bin/bash\n"
        "# W8FRIDA_LOCALTMP_WRAPPER\n"
        f"export HOME=\"{PREFIX}/tmp/frida-home\"\n"
        "export XDG_CONFIG_HOME=\"$HOME/.config\"\n"
        "export XDG_CACHE_HOME=\"$HOME/.cache\"\n"
        "export XDG_DATA_HOME=\"$HOME/.local/share\"\n"
        "mkdir -p \"$HOME\" \"$XDG_CONFIG_HOME\" \"$XDG_CACHE_HOME\" \"$XDG_DATA_HOME\"\n"
        f"export LD_PRELOAD=\"{LIBPYTHON}${{LD_PRELOAD:+:$LD_PRELOAD}}\"\n"
        "args=()\n"
        "for arg in \"$@\"; do\n"
        "    if [[ \"$arg\" == '-s' ]]; then\n"
        "        args+=('-l')\n"
        "    else\n"
        "        args+=(\"$arg\")\n"
        "    fi\n"
        "done\n"
        f"exec \"{actual_frida}\" -H {FRIDA_HOST} \"${{args[@]}}\"\n"
    )

    temp_wrapper = "frida-wrapper.tmp"
    with open(temp_wrapper, "w", encoding="utf-8") as fh:
        fh.write(wrapper)
    os.chmod(temp_wrapper, 0o755)
    temp_wrapper_abs = shlex.quote(os.path.abspath(temp_wrapper))
    wrapper_path_q = shlex.quote(wrapper_path)
    run(f"su -c {shlex.quote(f'cp {temp_wrapper_abs} {wrapper_path_q}; chmod 755 {wrapper_path_q}')}")

    for script in available_scripts():
        src = shlex.quote(os.path.abspath(script))
        dst = shlex.quote(f"{LOCAL_TMP}/{script}")
        run(f"su -c {shlex.quote(f'cp {src} {dst}; chmod 644 {dst}')}", critical=False)

    print(c("[OK] Scripts and /data/local/tmp/frida launcher deployed", "green"))
    return True


def install_frida():
    install_termux_packages()
    if not install_frida_tools():
        return False
    download_frida_server()
    deploy_assets()
    print(c("[OK] Install complete", "green"))
    return True


def start_frida_server():
    if not os.path.exists("frida-server"):
        print(c("[!] frida-server not found locally. Installing first...", "yellow"))
        download_frida_server()

    deploy_assets()
    root_cmd = (
        f"cd {LOCAL_TMP}; "
        "pkill frida-server >/dev/null 2>&1; "
        "chmod 755 frida-server; "
        "nohup ./frida-server >/dev/null 2>&1 &"
    )
    run(f"su -c {shlex.quote(root_cmd)}")
    time.sleep(2)

    if frida_server_ok():
        print(c("[OK] frida-server is running", "green"))
        return True

    print(c("[!] frida-server started, but client connection test failed", "yellow"))
    print(c("[!] You can still try option 4. Some ROMs block the quick process-list check.", "yellow"))
    return False


def stop_frida_server():
    run("su -c 'pkill frida-server >/dev/null 2>&1'", critical=False)
    print(c("[OK] frida-server stopped", "green"))
    return True


def available_scripts():
    scripts = [name for name in SCRIPT_ORDER if os.path.isfile(name)]
    extras = sorted(
        name for name in os.listdir(".")
        if name.endswith(".js") and os.path.isfile(name) and name not in scripts
    )
    return scripts + extras


def choose_script():
    scripts = available_scripts()
    if not scripts:
        print(c("[-] No .js scripts found in this folder", "red"))
        return ""

    print(c("\nSelect Frida script:", "cyan"))
    for idx, script in enumerate(scripts, start=1):
        print(c(f"{idx}. {script}", "green"))

    selected = input(c("\nEnter script number or path: ", "yellow")).strip()
    if not selected:
        return ""

    if selected.isdigit():
        index = int(selected)
        if 1 <= index <= len(scripts):
            return scripts[index - 1]
        print(c("[-] Invalid script number", "red"))
        return ""

    if os.path.isfile(selected):
        return selected

    print(c("[-] Script file not found", "red"))
    return ""


def run_frida_script():
    start_frida_server()

    script = choose_script()
    if not script:
        return False

    package_name = input(c("Enter APK package name, example com.via: ", "yellow")).strip()
    if not package_name:
        print(c("[-] Package name is required", "red"))
        return False

    script_name = os.path.basename(script)
    if os.path.abspath(script) != os.path.abspath(script_name):
        src = shlex.quote(os.path.abspath(script))
        dst = shlex.quote(f"{LOCAL_TMP}/{script_name}")
        run(f"su -c {shlex.quote(f'cp {src} {dst}; chmod 644 {dst}')}")

    print(c("\n[OK] Running Frida script", "green"))
    print(c(f"[+] Package: {package_name}", "cyan"))
    print(c(f"[+] Script: {script_name}", "cyan"))
    command = f"cd {LOCAL_TMP} && ./frida -f {shlex.quote(package_name)} -l {shlex.quote(script_name)}"
    return run(f"su -c {shlex.quote(command)}", critical=False)


def menu():
    while True:
        banner()
        print(c("1. Install Frida", "green"))
        print(c("2. Start Frida Server", "green"))
        print(c("3. Stop Frida", "green"))
        print(c("4. Run Frida Script", "green"))
        print(c("0. Exit", "red"))

        choice = input(c("\nSelect option: ", "yellow")).strip()

        if choice == "1":
            install_frida()
        elif choice == "2":
            start_frida_server()
        elif choice == "3":
            stop_frida_server()
        elif choice == "4":
            run_frida_script()
        elif choice == "0":
            print(c("Bye", "cyan"))
            break
        else:
            print(c("[-] Invalid option", "red"))

        input(c("\nPress Enter to continue...", "yellow"))


if __name__ == "__main__":
    menu()
