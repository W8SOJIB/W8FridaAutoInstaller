/*
 * HideRoot.js
 * Frida root-detection bypass helper for authorized testing.
 */

Java.perform(function () {
    var rootNames = [
        "su", "magisk", "magiskinit", "busybox", "supersu", "superuser",
        "zygisk", "riru", "xposed", "lsposed", "frida-server"
    ];

    var rootPaths = [
        "/system/bin/su",
        "/system/xbin/su",
        "/sbin/su",
        "/su/bin/su",
        "/vendor/bin/su",
        "/system/app/Superuser.apk",
        "/system/app/Magisk.apk",
        "/data/adb/magisk",
        "/data/adb/modules",
        "/data/local/tmp/frida-server",
        "/data/local/tmp/re.frida.server"
    ];

    var rootPackages = [
        "com.topjohnwu.magisk",
        "eu.chainfire.supersu",
        "com.noshufou.android.su",
        "com.koushikdutta.superuser",
        "com.thirdparty.superuser",
        "de.robv.android.xposed.installer",
        "org.lsposed.manager"
    ];

    function lower(value) {
        return value ? value.toString().toLowerCase() : "";
    }

    function isRootPath(path) {
        var p = lower(path);
        for (var i = 0; i < rootPaths.length; i++) {
            if (p.indexOf(rootPaths[i].toLowerCase()) >= 0) {
                return true;
            }
        }
        for (var j = 0; j < rootNames.length; j++) {
            if (p.endsWith("/" + rootNames[j]) || p.indexOf("/" + rootNames[j] + "/") >= 0) {
                return true;
            }
        }
        return false;
    }

    function isRootCommand(cmd) {
        var c = lower(cmd);
        return c === "su" ||
            c.indexOf("which su") >= 0 ||
            c.indexOf("whereis su") >= 0 ||
            c.indexOf("getprop ro.debuggable") >= 0 ||
            c.indexOf("getprop ro.secure") >= 0 ||
            c.indexOf("mount") >= 0 && c.indexOf("magisk") >= 0;
    }

    function fakeCommand(cmd) {
        console.log("[HideRoot] blocked command: " + cmd);
        return "echo";
    }

    try {
        var File = Java.use("java.io.File");

        File.exists.implementation = function () {
            var path = this.getAbsolutePath();
            if (isRootPath(path)) {
                console.log("[HideRoot] File.exists false: " + path);
                return false;
            }
            return this.exists();
        };

        File.canExecute.implementation = function () {
            var path = this.getAbsolutePath();
            if (isRootPath(path)) {
                console.log("[HideRoot] File.canExecute false: " + path);
                return false;
            }
            return this.canExecute();
        };
    } catch (e) {
        console.log("[HideRoot] File hook failed: " + e);
    }

    try {
        var Runtime = Java.use("java.lang.Runtime");

        Runtime.exec.overload("java.lang.String").implementation = function (cmd) {
            if (isRootCommand(cmd)) {
                return this.exec(fakeCommand(cmd));
            }
            return this.exec(cmd);
        };

        Runtime.exec.overload("[Ljava.lang.String;").implementation = function (cmdArray) {
            var joined = "";
            for (var i = 0; i < cmdArray.length; i++) {
                joined += cmdArray[i] + " ";
            }
            if (isRootCommand(joined)) {
                return this.exec(["echo"]);
            }
            return this.exec(cmdArray);
        };
    } catch (e) {
        console.log("[HideRoot] Runtime hook failed: " + e);
    }

    try {
        var ProcessBuilder = Java.use("java.lang.ProcessBuilder");
        ProcessBuilder.start.implementation = function () {
            var commands = this.command();
            var joined = commands.toString();
            if (isRootCommand(joined)) {
                console.log("[HideRoot] ProcessBuilder blocked: " + joined);
                this.command(Java.use("java.util.Arrays").asList(["echo"]));
            }
            return this.start();
        };
    } catch (e) {
        console.log("[HideRoot] ProcessBuilder hook failed: " + e);
    }

    try {
        var PackageManager = Java.use("android.app.ApplicationPackageManager");
        PackageManager.getPackageInfo.overload("java.lang.String", "int").implementation = function (pkg, flags) {
            if (rootPackages.indexOf(pkg) >= 0) {
                console.log("[HideRoot] hidden package: " + pkg);
                pkg = "com.android.vending.missing";
            }
            return this.getPackageInfo(pkg, flags);
        };
    } catch (e) {
        console.log("[HideRoot] PackageManager hook failed: " + e);
    }

    try {
        var SystemProperties = Java.use("android.os.SystemProperties");
        SystemProperties.get.overload("java.lang.String").implementation = function (key) {
            if (key === "ro.build.tags") return "release-keys";
            if (key === "ro.debuggable") return "0";
            if (key === "ro.secure") return "1";
            return this.get(key);
        };
        SystemProperties.get.overload("java.lang.String", "java.lang.String").implementation = function (key, defValue) {
            if (key === "ro.build.tags") return "release-keys";
            if (key === "ro.debuggable") return "0";
            if (key === "ro.secure") return "1";
            return this.get(key, defValue);
        };
    } catch (e) {
        console.log("[HideRoot] SystemProperties hook failed: " + e);
    }

    try {
        var Build = Java.use("android.os.Build");
        Build.TAGS.value = "release-keys";
        Build.TYPE.value = "user";
    } catch (e) {
        console.log("[HideRoot] Build hook failed: " + e);
    }

    console.log("[HideRoot] hooks loaded");
});

try {
    ["access", "stat", "lstat", "faccessat"].forEach(function (name) {
        var ptr = Module.findExportByName("libc.so", name);
        if (!ptr) return;
        Interceptor.attach(ptr, {
            onEnter: function (args) {
                this.path = args[0].readCString();
            },
            onLeave: function (retval) {
                if (!this.path) return;
                var p = this.path.toLowerCase();
                if (p.indexOf("/su") >= 0 || p.indexOf("magisk") >= 0 || p.indexOf("frida-server") >= 0) {
                    console.log("[HideRoot] native hide: " + this.path);
                    retval.replace(-1);
                }
            }
        });
    });
} catch (e) {
    console.log("[HideRoot] native hooks failed: " + e);
}
