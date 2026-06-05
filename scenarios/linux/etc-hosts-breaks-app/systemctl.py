#!/usr/bin/env python3
"""
systemctl replacement for Docker containers.
Wraps SysV init scripts (/etc/init.d/*) to provide systemctl-like interface.
Supports: start, stop, restart, status, enable, disable, list-units
"""
import subprocess, sys, os, glob

def get_service_script(name):
    p = f"/etc/init.d/{name}"
    if os.path.isfile(p):
        return p
    return None

def is_running(name):
    try:
        r = subprocess.run(["pgrep", "-x", name], capture_output=True)
        return r.returncode == 0
    except:
        return False

def do_action(name, action):
    script = get_service_script(name)
    if script:
        r = subprocess.run([script, action])
        return r.returncode
    # Fallback: try common binary locations
    for b in [f"/usr/sbin/{name}", f"/usr/bin/{name}", f"/sbin/{name}"]:
        if os.path.isfile(b):
            if action == "start":
                subprocess.Popen([b])
                print(f"Started {name}")
                return 0
            elif action == "stop":
                subprocess.run(["pkill", "-x", name])
                print(f"Stopped {name}")
                return 0
    print(f"Failed to {action} {name}: service not found")
    return 1

def status(name):
    running = is_running(name)
    state = "active (running)" if running else "inactive (dead)"
    loaded = "loaded" if get_service_script(name) else "not-found"
    print(f"\u25cf {name}.service")
    print(f"   Loaded: {loaded}")
    print(f"   Active: {state}")
    if running:
        try:
            r = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True)
            pids = r.stdout.strip().replace("\n", ", ")
            print(f"   PID(s): {pids}")
        except:
            pass
    return 0 if running else 3

def list_services():
    print("UNIT                           STATE")
    for f in sorted(glob.glob("/etc/init.d/*")):
        name = os.path.basename(f)
        if name in ("rc", "rcS", "README", "skeleton"):
            continue
        r = "running" if is_running(name) else "dead"
        print(f"  {name:30s} {r}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print("Usage: systemctl {start|stop|restart|status|enable|disable|list-units} [service]")
        sys.exit(0)
    action = args[0]
    if action in ("list-units", "list", "--type=service"):
        list_services()
        sys.exit(0)
    if action == "daemon-reload":
        print("Reloaded.")
        sys.exit(0)
    if len(args) < 2:
        print("Usage: systemctl <action> <service>")
        sys.exit(1)
    name = args[1].replace(".service", "")
    if action == "status":
        sys.exit(status(name))
    elif action == "restart":
        do_action(name, "stop")
        sys.exit(do_action(name, "start"))
    elif action in ("enable", "disable"):
        print(f"{name}.service {action}d")
        sys.exit(0)
    elif action == "is-active":
        if is_running(name):
            print("active")
            sys.exit(0)
        else:
            print("inactive")
            sys.exit(3)
    else:
        sys.exit(do_action(name, action))
