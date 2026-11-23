#!/usr/bin/env python3
"""Render Muichiro's mist themed panel from live Fastfetch data."""
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = "\033["
R = E + "0m"
B = E + "1m"
C = {
    "mist": E + "38;2;133;220;205m",
    "bright": E + "38;2;193;244;230m",
    "white": E + "38;2;226;239;235m",
    "dim": E + "38;2;111;143;140m",
    "blue": E + "38;2;132;193;212m",
    "gold": E + "38;2;217;195;135m",
    "light_mint": E + "38;2;190;239;222m",
    "warn": E + "38;2;244;204;85m",
    "critical": E + "38;2;242;111;82m",
}
BG = E + "48;2;35;82;78m"
BLUE_BG = E + "48;2;38;70;82m"
GOLD_BG = E + "48;2;78;70;48m"
PILL_FG = E + "38;2;35;82;78m"
BLUE_FG = E + "38;2;38;70;82m"
GOLD_FG = E + "38;2;78;70;48m"
MIST_GRADIENT = (
    E + "48;2;170;229;215m",
    E + "48;2;111;190;172m",
    E + "48;2;53;128;112m",
)
MIST_DARK_FG = E + "38;2;53;128;112m"
W = 58


def collect():
    try:
        p = subprocess.run(["fastfetch", "--format", "json", "--config", str(HERE / "data.jsonc")],
                           capture_output=True, text=True, timeout=8)
        if p.returncode:
            return {}
        return {x["type"].lower(): x.get("result") for x in json.loads(p.stdout)}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(s))


def fit(s, n):
    s = str(s or "—").replace("\n", " ")
    out = ""
    for ch in s:
        if width(out + ch) > n:
            return out + "…" + " " * max(0, n - width(out + "…"))
        out += ch
    return out + " " * max(0, n - width(out))


def human(n):
    n = float(n or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024


def run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=3)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def connection_info():
    """Read the active Wi-Fi SSID and wired IPv4/router from NetworkManager."""
    devices = run(["nmcli", "-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    connected = []
    for entry in devices.splitlines():
        fields = entry.split(":", 2)
        if len(fields) == 3 and fields[2].lower().startswith("connected"):
            connected.append((fields[0], fields[1].lower()))

    ssid = ""
    wired = None
    for device, kind in connected:
        if kind in ("wifi", "wireless"):
            connection = run(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", device])
            ssid = run(["nmcli", "-g", "802-11-wireless.ssid", "connection", "show", connection]) if connection else ""
            if not ssid:
                ssid = run(["iwgetid", "-r", device])
        elif kind in ("ethernet", "802-3-ethernet"):
            output = run(["ip", "-o", "-4", "addr", "show", "dev", device, "scope", "global"])
            match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", output)
            address = match.group(1) if match else "Unavailable"
            router = run(["nmcli", "-g", "IP4.GATEWAY", "device", "show", device])
            if not router or router == "--":
                route = run(["ip", "-4", "route", "show", "default", "dev", device])
                gateway = re.search(r"\bvia\s+(\d+\.\d+\.\d+\.\d+)", route)
                router = gateway.group(1) if gateway else "Unavailable"
            wired = f"IP {address}  ·  ROUTER {router}"
    return ssid, wired


def os_icon(osinfo):
    signature = " ".join(str(osinfo.get(k, "")) for k in ("id", "name", "prettyName")).lower()
    icons = (
        (("arch",), ""), (("manjaro",), ""), (("ubuntu",), ""),
        (("debian",), ""), (("fedora",), ""), (("nixos",), ""),
        (("opensuse", "suse"), ""), (("gentoo",), ""),
        (("alpine",), ""), (("mint",), "󰣭"), (("pop!_os", "pop os"), ""),
        (("void",), ""), (("centos",), ""), (("red hat", "rhel"), ""),
    )
    return next((icon for needles, icon in icons if any(n in signature for n in needles)), "")


def filesystem_usage(mountpoint):
    output = run(["df", "-P", "-B1", "--", mountpoint])
    rows = output.splitlines()
    if len(rows) < 2:
        return None
    fields = rows[-1].split()
    try:
        return int(fields[1]), int(fields[2])
    except (IndexError, ValueError):
        return None


def disk_info(ff_disks):
    """Aggregate mounted filesystem usage under each physical disk."""
    try:
        raw = run(["lsblk", "-J", "-b", "-e", "7", "-o", "NAME,TYPE,SIZE,MOUNTPOINT"])
        roots = json.loads(raw).get("blockdevices", []) if raw else []
    except (json.JSONDecodeError, AttributeError):
        roots = []

    result = []
    for device in (x for x in roots if x.get("type") == "disk"):
        volumes = []

        def visit(node):
            mount = node.get("mountpoint")
            if mount and not str(mount).startswith("["):
                usage = filesystem_usage(mount)
                if usage:
                    volumes.append((mount, *usage))
            for child in node.get("children", []) or []:
                visit(child)

        visit(device)
        if not volumes:
            names = set()

            def collect_names(node):
                names.add(node.get("name", ""))
                for child in node.get("children", []) or []:
                    collect_names(child)

            collect_names(device)
            for item in ff_disks:
                source = os.path.basename(str(item.get("mountFrom", "")))
                if source in names:
                    b = item.get("bytes", {})
                    total = int(b.get("total", 0) or 0)
                    used = int(b.get("used", max(0, total - int(b.get("free", 0) or 0))) or 0)
                    if total:
                        volumes.append((item.get("mountpoint", "/"), total, used))
        if volumes:
            total = sum(v[1] for v in volumes)
            used = sum(v[2] for v in volumes)
            result.append((device.get("name", "disk"), total, used))
        elif device.get("size"):
            result.append((device.get("name", "disk"), int(device["size"]), 0))
    return result


def meter(segments, size=38):
    total = sum(max(0, float(amount)) for amount, _ in segments)
    if total <= 0:
        counts = [0] * len(segments)
        counts[-1] = size
    else:
        counts = []
        remaining = size
        for amount, _ in segments[:-1]:
            cells = min(remaining, round(size * max(0, float(amount)) / total))
            counts.append(cells)
            remaining -= cells
        counts.append(remaining)
    return "                  " + "".join(f"{color}{'█' * count}{R}" for count, (_, color) in zip(counts, segments))


def usage_segments(used, total):
    """Split the filled portion at 50% and 80%; the last segment is unused."""
    total = max(0, float(total or 0))
    ratio = min(1.0, max(0.0, float(used or 0) / total)) if total else 0.0
    green = min(ratio, 0.50) * total
    yellow = max(0.0, min(ratio, 0.80) - 0.50) * total
    orange = max(0.0, ratio - 0.80) * total
    remaining = max(0.0, 1.0 - ratio) * total
    return ((green, C["mist"]), (yellow, C["warn"]), (orange, C["critical"]), (remaining, C["light_mint"]))


def line(text=""):
    print("\r" + E + "32C" + text)


def mist_divider(title):
    label = f" {title} "
    left = "〰╴"
    right = "╶〰"
    fill = max(0, W - width(left) - width(label) - width(right))
    return f"{C['dim']}{left}{C['mist']}{B}{label}{R}{C['mist']}{'·' * fill}{C['dim']}{right}{R}"


def row(key, value, color=None):
    color = color or C["white"]
    bg, cap = (BLUE_BG, BLUE_FG) if color == C["blue"] else (GOLD_BG, GOLD_FG) if color == C["gold"] else (BG, PILL_FG)
    # Give the rounded end caps and pill body one shared background color.
    capsule = f"{cap}{bg}{color}{B} {key:<10} {R}{cap}{R}"
    return f"  {capsule}  {fit(value, W - 19)}"


def main():
    d = collect()
    osinfo = d.get("os") or {}
    kernel = d.get("kernel") or {}
    de = d.get("de") or {}
    shell = d.get("shell") or {}
    up = int(((d.get("uptime") or {}).get("uptime", 0)) / 1000)
    cpu = d.get("cpu") or {}
    mem = d.get("memory") or {}
    swaps = d.get("swap") or []
    gpus = d.get("gpu") or []
    disks = d.get("disk") or []
    hours, mins = divmod(up // 60, 60)
    days, hours = divmod(hours, 24)
    uptime = f"{days}d {hours:02}h {mins:02}m" if days else f"{hours}h {mins:02}m"
    shell_name = os.path.basename(os.environ.get("SHELL", "")) or (shell.get("prettyName", "—"))

    line()
    title = " 霞柱 · MIST HASHIRA "
    gradient = "".join(f"{shade}  " for shade in MIST_GRADIENT)
    line(f"{gradient}{MIST_GRADIENT[-1]}{C['bright']}{B}{title}{R}{MIST_DARK_FG}{R}")
    line(f"{C['dim']}霞の呼吸  ·  静寂の中に刃{R}")
    line(mist_divider("01  SYSTEM"))
    line(row(f"OS {os_icon(osinfo)}", osinfo.get("prettyName", "—"), C["mist"]))
    line(row("KERNEL", kernel.get("release", "—")))
    line(row("DESKTOP", f"{de.get('prettyName', '—')} {de.get('version', '')}".strip()))
    line(row("SHELL", f"{shell_name} {shell.get('version', '')}".strip()))
    line(row("UPTIME", uptime, C["dim"]))
    line(mist_divider("02  HASHIRA PROFILE"))
    line(row("CPU", cpu.get("cpu", "—"), C["blue"]))
    gpu = ", ".join(x.get("name", "GPU") for x in gpus if isinstance(x, dict)) or "—"
    line(row("GPU", gpu, C["blue"]))
    line(mist_divider("03  MIST FLOW"))
    mem_used = int(mem.get("used", 0) or 0)
    mem_total = int(mem.get("total", 0) or 0)
    su = sum(x.get("used", 0) for x in swaps if isinstance(x, dict))
    st = sum(x.get("total", 0) for x in swaps if isinstance(x, dict))
    line(row("RAM", f"{human(mem_used)} / {human(mem_total)}", C["bright"]))
    line(row("SWAP", f"{human(su)} / {human(st)}", C["blue"]))
    line(meter(usage_segments(mem_used, mem_total)))
    for name, total, used in disk_info(disks):
        line(row(name, f"{human(used)} / {human(total)}", C["gold"]))
        line(meter(usage_segments(used, total)))
    line(mist_divider("04  CONNECTION"))
    ssid, wired = connection_info()
    line(row("WI-FI", ssid or "Not connected", C["blue"]))
    line(row("WIRED", wired or "Not connected", C["blue"]))
    pattern = "〰░·░〰·░·░〰░·░〰"
    line(f"{C['dim']}{pattern}{'·' * max(0, W - width(pattern))}{R}")
    line(f"  {C['bright']}肆之型 · 移流斬り{R}  {C['dim']}░·〰·░〰·░{R}  {C['mist']}MIST // CLEAR{R}")


if __name__ == "__main__":
    main()
