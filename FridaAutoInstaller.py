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
FRIDA_HOST = "127.0.0.1:37123"
LOCAL_TMP = "/data/local/tmp"
SERVER_NAME = ".w8fs"

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
    "HideRoot.js",
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


def out_args(args, timeout=20):
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


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
        f"cp {shlex.quote(os.path.abspath('frida-server'))} {LOCAL_TMP}/{SERVER_NAME}; "
        f"chmod 755 {LOCAL_TMP}/frida-server {LOCAL_TMP}/{SERVER_NAME}"
    )
    run(f"su -c {shlex.quote(root_cmd)}")
    print(c(f"[OK] frida-server installed to /data/local/tmp/{SERVER_NAME}", "green"))
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
    server_path = f"{LOCAL_TMP}/{SERVER_NAME}"
    root_cmd = (
        f"cd {LOCAL_TMP}; "
        "pkill -f frida-server >/dev/null 2>&1; "
        f"pkill -f {SERVER_NAME} >/dev/null 2>&1; "
        f"cp frida-server {SERVER_NAME} >/dev/null 2>&1; "
        f"chmod 755 {SERVER_NAME}; "
        f"nohup {server_path} -l {FRIDA_HOST} >/dev/null 2>&1 &"
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
    run(f"su -c {shlex.quote(f'pkill -f frida-server >/dev/null 2>&1; pkill -f {SERVER_NAME} >/dev/null 2>&1')}", critical=False)
    print(c("[OK] frida-server stopped", "green"))
    return True


def health_check():
    print(c("\n[*] Frida health check", "yellow"))
    print(c(f"[+] Host: {FRIDA_HOST}", "cyan"))
    print(c(f"[+] Client version: {out(frida_env_cmd('frida --version'))}", "cyan"))
    print(c(f"[+] Python frida version: {get_installed_frida_version()}", "cyan"))
    print(c("[+] Server processes:", "cyan"))
    print(out("su -c 'ps -A | grep frida'"))
    print(c("[+] Port check:", "cyan"))
    print(out("su -c 'netstat -tnlp 2>/dev/null | grep 27042'"))

    if frida_server_ok():
        print(c("[OK] frida-server process listing works", "green"))
    else:
        print(c("[-] frida-server process listing failed", "red"))
        print(c("[-] Run option 2, then retry health check.", "yellow"))


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


def choose_run_mode():
    print(c("\nSelect run mode:", "cyan"))
    print(c("1. Attach by PID after launching package (recommended)", "green"))
    print(c("2. Attach running app by package name", "green"))
    print(c("3. Spawn app by package name", "green"))
    print(c("4. Attach frontmost app", "green"))

    selected = input(c("\nEnter mode [1]: ", "yellow")).strip()
    if not selected:
        selected = "1"

    if selected == "1":
        return "pid"
    if selected == "2":
        return "attach"
    if selected == "3":
        return "spawn"
    if selected == "4":
        return "frontmost"

    print(c("[-] Invalid mode", "red"))
    return ""


def launch_package(package_name):
    monkey_cmd = (
        f"monkey -p {shlex.quote(package_name)} "
        "-c android.intent.category.LAUNCHER 1 >/dev/null 2>&1"
    )
    run(f"su -c {shlex.quote(monkey_cmd)}", critical=False)
    time.sleep(2)


def package_pid(package_name):
    pid_cmd = f"pidof {shlex.quote(package_name)}"
    result = out(f"su -c {shlex.quote(pid_cmd)}")
    pids = [part for part in result.split() if part.isdigit()]
    if pids:
        return pids[0]
    return ""


def installed_packages():
    commands = [
        ["su", "-mm", "-c", "/system/bin/pm list packages"],
        ["su", "-mm", "-c", "/system/bin/cmd package list packages"],
        ["su", "-mm", "-c", "/system/bin/dumpsys package packages"],
        ["su", "-mm", "-c", "cat /data/system/packages.list"],
        ["/system/bin/pm", "list", "packages"],
        ["/system/bin/cmd", "package", "list", "packages"],
        ["/system/bin/dumpsys", "package", "packages"],
        ["pm", "list", "packages"],
        ["cmd", "package", "list", "packages"],
        ["su", "-c", "/system/bin/pm list packages"],
        ["su", "-c", "/system/bin/cmd package list packages"],
        ["su", "-c", "/system/bin/dumpsys package packages"],
        ["su", "-c", "cat /data/system/packages.list"],
        ["su", "0", "/system/bin/pm", "list", "packages"],
        ["su", "0", "/system/bin/cmd", "package", "list", "packages"],
        ["su", "0", "cat", "/data/system/packages.list"],
    ]

    raw = ""
    for args in commands:
        raw = out_args(args)
        if "package:" in raw or "Package [" in raw or raw.strip().startswith("android "):
            break

    packages = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.replace("package:", "", 1))
        elif line.startswith("Package [") and "]" in line:
            packages.append(line.split("[", 1)[1].split("]", 1)[0])
        elif line and " " in line and not line.startswith(("Error", "cmd:", "Exception")):
            first = line.split()[0]
            if "." in first or first == "android":
                packages.append(first)

    if packages:
        return sorted(set(packages))

    return frida_app_packages()


def frida_app_packages():
    raw = out(frida_env_cmd(f"frida-ps -H {FRIDA_HOST} -a"))
    packages = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        identifier = parts[-1]
        if "." in identifier and not identifier.startswith("-"):
            packages.append(identifier)
    return sorted(set(packages))


def package_label(package_name):
    dump_cmd = f"/system/bin/cmd package dump {shlex.quote(package_name)}"
    raw = out(dump_cmd)
    if "not found" in raw.lower() or not raw.strip():
        raw = out(f"su -c {shlex.quote(dump_cmd)}")
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("application-label:"):
            return line.split(":", 1)[1].strip()
    return ""


def choose_package():
    query = input(c("Filter package name (press Enter to show all): ", "yellow")).strip().lower()
    packages = installed_packages()
    if not packages:
        print(c("[-] Could not read installed packages with pm/cmd/frida-ps.", "red"))
        print(c("[-] Type the package manually from option 2.", "yellow"))
        return ""

    matches = []
    for pkg in packages:
        label = package_label(pkg)
        haystack = f"{pkg} {label}".lower()
        if not query or query in haystack:
            matches.append((pkg, label))

    if not matches:
        print(c("[-] No package found", "red"))
        return ""

    print(c("\nPackage results:", "cyan"))
    for idx, (pkg, label) in enumerate(matches, start=1):
        suffix = f" - {label}" if label else ""
        print(c(f"{idx}. {pkg}{suffix}", "green"))

    selected = input(c("\nSelect package number or type package: ", "yellow")).strip()
    if not selected:
        return ""
    if selected.isdigit():
        index = int(selected)
        if 1 <= index <= len(matches):
            return matches[index - 1][0]
        print(c("[-] Invalid package number", "red"))
        return ""
    return selected


def ask_package_name():
    print(c("\nPackage input:", "cyan"))
    print(c("1. Search installed packages", "green"))
    print(c("2. Type package manually", "green"))

    selected = input(c("\nSelect [1]: ", "yellow")).strip()
    if not selected:
        selected = "1"

    if selected == "1":
        return choose_package()
    if selected == "2":
        return input(c("Enter APK package name, example com.via: ", "yellow")).strip()

    print(c("[-] Invalid option", "red"))
    return ""


def run_frida_script():
    start_frida_server()

    script = choose_script()
    if not script:
        return False

    mode = choose_run_mode()
    if not mode:
        return False

    package_name = ""
    if mode in ["pid", "attach", "spawn"]:
        package_name = ask_package_name()
    if mode in ["pid", "attach", "spawn"] and not package_name:
        print(c("[-] Package name is required", "red"))
        return False

    script_name = os.path.basename(script)
    if os.path.abspath(script) != os.path.abspath(script_name):
        src = shlex.quote(os.path.abspath(script))
        dst = shlex.quote(f"{LOCAL_TMP}/{script_name}")
        run(f"su -c {shlex.quote(f'cp {src} {dst}; chmod 644 {dst}')}")

    print(c("\n[OK] Running Frida script", "green"))
    print(c(f"[+] Mode: {mode}", "cyan"))
    if package_name:
        print(c(f"[+] Package: {package_name}", "cyan"))
    print(c(f"[+] Script: {script_name}", "cyan"))

    if mode == "pid":
        launch_package(package_name)
        pid = package_pid(package_name)
        if not pid:
            print(c("[-] Could not find app PID. Open the app manually, then retry mode 1.", "red"))
            return False
        print(c(f"[+] PID: {pid}", "cyan"))
        command = f"cd {LOCAL_TMP} && ./frida -p {shlex.quote(pid)} -l {shlex.quote(script_name)}"
        return run(f"su -c {shlex.quote(command)}", critical=False)

    if mode == "attach":
        launch_package(package_name)
        pid = package_pid(package_name)
        if pid:
            print(c(f"[+] Detected PID: {pid}", "cyan"))
        command = f"cd {LOCAL_TMP} && ./frida -n {shlex.quote(package_name)} -l {shlex.quote(script_name)}"
        if run(f"su -c {shlex.quote(command)}", critical=False):
            return True
        if pid:
            print(c("[!] Package-name attach failed. Trying PID attach...", "yellow"))
            fallback = f"cd {LOCAL_TMP} && ./frida -p {shlex.quote(pid)} -l {shlex.quote(script_name)}"
            return run(f"su -c {shlex.quote(fallback)}", critical=False)
        return False

    if mode == "frontmost":
        command = f"cd {LOCAL_TMP} && ./frida -F -l {shlex.quote(script_name)}"
        return run(f"su -c {shlex.quote(command)}", critical=False)

    command = f"cd {LOCAL_TMP} && ./frida -f {shlex.quote(package_name)} -l {shlex.quote(script_name)}"
    if run(f"su -c {shlex.quote(command)}", critical=False):
        return True

    print(c("[!] Spawn failed. Trying attach mode after launching the app...", "yellow"))
    launch_package(package_name)
    pid = package_pid(package_name)
    if pid:
        fallback = f"cd {LOCAL_TMP} && ./frida -p {shlex.quote(pid)} -l {shlex.quote(script_name)}"
    else:
        fallback = f"cd {LOCAL_TMP} && ./frida -n {shlex.quote(package_name)} -l {shlex.quote(script_name)}"
    return run(f"su -c {shlex.quote(fallback)}", critical=False)


def menu():
    while True:
        banner()
        print(c("1. Install Frida", "green"))
        print(c("2. Start Frida Server", "green"))
        print(c("3. Stop Frida", "green"))
        print(c("4. Run Frida Script", "green"))
        print(c("5. Package Finder", "green"))
        print(c("6. Frida Health Check", "green"))
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
        elif choice == "5":
            package_name = choose_package()
            if package_name:
                print(c(f"[OK] Selected package: {package_name}", "green"))
        elif choice == "6":
            health_check()
        elif choice == "0":
            print(c("Bye", "cyan"))
            break
        else:
            print(c("[-] Invalid option", "red"))

        input(c("\nPress Enter to continue...", "yellow"))


if __name__ == "__main__":
    menu()
