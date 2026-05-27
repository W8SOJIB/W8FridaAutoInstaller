# W8FridaAutoInstaller
**Automated Frida & SSL Unpinning Tool for Termux (Rooted)**

`W8FridaAutoInstaller` is a powerful, all-in-one utility designed for security researchers and penetration testers. It automates the complex process of installing Frida, deploying a root-level server, and running specialized SSL unpinning/bypass scripts in the Termux environment.

Created by: **W8SOJIB / W8Team**

---

## 🚀 Features

- **One-Click Installation**: Automatically detects your Android architecture (ARM64, x86, etc.) and installs the correct Frida version.
- **Smart Framework Detection**: Scans target APKs to identify if they were built with **Flutter, Unity, React Native, Xamarin, or Godot** and recommends the best scripts.
- **Stealth Mode**: Change the Frida server port and process name to bypass simple anti-Frida detections.
- **Multi-Script Support**: Comes with a library of advanced JS scripts for SSL unpinning, root hiding, and anti-debug bypass.
- **Root-Powered**: Leverages `su` to run a renamed, hidden Frida server (`.w8fs`) for deeper system access.
- **Clean Uninstallation**: Fully restores your Termux environment and removes all deployed files with one command.

---

## 📋 Prerequisites

1.  **Rooted Android Device**: This tool requires root access to inject scripts and run the server.
2.  **Termux**: Installed from [F-Droid](https://f-droid.org/en/packages/com.termux/) (Google Play version is outdated).
3.  **Internet Connection**: To download Frida binaries and dependencies.

---

## 📥 Installation

Copy and paste the following commands into your Termux terminal:

```bash
pkg update && pkg upgrade -y
pkg install python git -y
git clone https://github.com/W8SOJIB/W8FridaAutoInstaller.git
cd W8FridaAutoInstaller
pip install -r requirements.txt
python FridaAutoInstaller.py
```

---

## 🛠️ Usage Guide

### 1. Initial Setup
Run the tool and select **Option 1 (Install Frida)**. This will:
- Update Termux packages.
- Install `frida-python` and required wrappers.
- Download the matching `frida-server` for your device.

### 2. Running a Script (The "Pro" Workflow)
1.  Select **Option 4 (Run Frida Script)**.
2.  The tool will ensure the **Frida Server** is running in stealth mode.
3.  Choose a script (e.g., `sslunpinning.js` for general apps or `unissl.js` for Flutter).
4.  Select a **Run Mode** (Mode 1: PID Attach is recommended for stability).
5.  Search for your app or type the package name (e.g., `com.konasl.nagad`).
6.  **Framework Detection**: The tool will tell you if it's a Flutter/Unity app and suggest the right script!

### 3. Settings & Stealth
Use **Option 6 (Settings)** to:
- Change the **Frida Port** (Default: 37123).
- Change the **Server Name** (Default: .w8fs).
- Generate a **Random Stealth Name** to hide from security checks.

---

## 📂 Included Scripts

- `sslunpinning.js`: Standard SSL unpinning bypass.
- `frida_ssl_multiple.js`: Enhanced bypass for multiple network libraries.
- `unissl.js` / `unissl2.js`: Universal bypasses (highly effective for **Flutter**).
- `HideRoot.js`: Simple root detection bypass.
- `AntiDebug.js`: Bypasses common anti-debugging checks.
- ...and many more!

---

## 🗑️ Uninstallation

If you want to remove everything and restore Termux to its original state:
1.  Select **Option 7 (Uninstall Frida)** in the menu.
2.  The tool will restore original binaries, kill processes, and delete all temporary files.

---

## ⚠️ Disclaimer

This tool is for **educational and ethical security testing purposes only**. The developer is not responsible for any misuse or damage caused by this tool. Always obtain permission before testing applications you do not own.

---

### 👨‍💻 Credits
- **Developer**: W8SOJIB
- **Team**: W8Team
- **Support**: Join our community for updates and help.

**W8Team - Stay Secure, Stay Informed.**
