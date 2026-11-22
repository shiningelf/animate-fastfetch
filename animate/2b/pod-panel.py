#!/usr/bin/env python3
"""Render a color-coded POD scan panel from Fastfetch's live system data."""
import getpass
import json
import os
import re
import socket
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESC = "\x1b["
RESET = ESC + "0m"
BOLD = ESC + "1m"
COLORS = {
    "white": ESC + "38;2;230;230;225m",
    "muted": ESC + "38;2;132;139;145m",
    "cyan": ESC + "38;2;112;222;224m",
    "blue": ESC + "38;2;117;174;222m",
    "gold": ESC + "38;2;225;190;104m",
    "orange": ESC + "38;2;239;137;73m",
    "red": ESC + "38;2;220;86;87m",
    "green": ESC + "38;2;126;204;158m",
}
WIDTH = 63


def collect():
    try:
        proc = subprocess.run(
            ["fastfetch", "--format", "json", "--config", str(HERE / "data.jsonc")],
            capture_output=True, text=True, timeout=8,
        )
        if proc.returncode:
            return {}
        return {item["type"].lower(): item.get("result") for item in json.loads(proc.stdout)}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def run(args, timeout=3):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cell_width(value):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(value))


def fit(value, size):
    value = str(value or "—").replace("\n", " ")
    result = ""
    for char in value:
        if cell_width(result + char) > size:
            return result + "…"
        result += char
    return result + " " * max(0, size - cell_width(result))


def human(value):
    amount = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{amount:.0f} B"
        amount /= 1024


def duration(milliseconds):
    seconds = int((milliseconds or 0) / 1000)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return f"{days}d {hours:02}h {minutes:02}m" if days else f"{hours}h {minutes:02}m"


def bar(used, total, color, size=18):
    pct = 0 if not total else min(1, max(0, used / total))
    filled = round(pct * size)
    return f"{color}{'█' * filled}{COLORS['muted']}{'░' * (size - filled)}{RESET} {pct * 100:3.0f}%"


def section(title, color):
    label = f" {title} "
    return f"{color}╟{BOLD}{label}{RESET}{color}{'─' * max(0, WIDTH - 2 - cell_width(label))}╢{RESET}"


def row(label, value, color=COLORS["white"]):
    left = f"  {color}{BOLD}{label:<13}{RESET}"
    content_width = WIDTH - 2 - 15
    return f"{COLORS['muted']}║{RESET}{left}{fit(value, content_width)}{COLORS['muted']}║{RESET}"


def bar_row(label, used, total, color):
    text = f"{human(used)} / {human(total)}"
    left = f"  {color}{BOLD}{label:<13}{RESET}"
    content_width = WIDTH - 2 - 15
    text_width = cell_width(text)
    gap = " " * max(1, content_width - 18 - 5 - text_width)
    return f"{COLORS['muted']}║{RESET}{left}{color}{text}{RESET}{gap}{bar(used, total, color)}{COLORS['muted']}║{RESET}"


def frame_top(title):
    label = f" {title} "
    return f"{COLORS['white']}╭{BOLD}{label}{RESET}{COLORS['white']}{'─' * max(0, WIDTH - 2 - cell_width(label))}╮{RESET}"


def frame_bottom():
    return f"{COLORS['white']}╰{'─' * (WIDTH - 2)}╯{RESET}"


def network_info(data):
    wifi = data.get("wifi") or {}
    ssid = wifi.get("ssid", "") if isinstance(wifi, dict) else ""
    wireless_device = ""
    wired_device = ""
    devices = run(["nmcli", "-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    for line in devices.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or not fields[2].lower().startswith("connected"):
            continue
        device, kind = fields[0], fields[1].lower()
        if kind in ("wifi", "wireless"):
            wireless_device = device
        elif kind in ("ethernet", "802-3-ethernet"):
            wired_device = device

    if wireless_device and not ssid:
        connection = run(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", wireless_device])
        if connection:
            ssid = run(["nmcli", "-g", "802-11-wireless.ssid", "connection", "show", connection])

    def address(device):
        if not device:
            return None
        output = run(["ip", "-o", "-4", "addr", "show", "dev", device, "scope", "global"])
        match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", output)
        if match:
            return match.group(1)
        fallback = run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", device])
        return fallback.splitlines()[0] if fallback else "Unavailable"

    return ssid if wireless_device else "", address(wireless_device), address(wired_device)


def emit(line):
    # Fastfetch aligns only the first line of a command module beside its logo.
    # Reapply the image width (28 cells) and right padding (2 cells) per line.
    print("\r" + ESC + "30C" + line)


def main():
    data = collect()
    osinfo = data.get("os") or {}
    kernel = data.get("kernel") or {}
    desktop = data.get("de") or {}
    shell = data.get("shell") or {}
    cpu = data.get("cpu") or {}
    memory = data.get("memory") or {}
    swaps = data.get("swap") or []
    gpus = data.get("gpu") or []
    disks = data.get("disk") or []
    disk = next((item for item in disks if item.get("mountpoint") == "/"), disks[0] if disks else {})
    disk_bytes = disk.get("bytes", {})
    disk_used = disk_bytes.get("used", max(0, disk_bytes.get("total", 0) - disk_bytes.get("free", 0)))
    gpu_names = ", ".join(item.get("name", "GPU") for item in gpus if isinstance(item, dict)) or "Unavailable"
    ssid, wireless_ip, wired_ip = network_info(data)

    target = f"{getpass.getuser()}@{socket.gethostname()}"
    emit("")
    emit(frame_top("POD 042 // SCAN COMPLETE"))
    emit(row("TARGET", target, COLORS["cyan"]))
    signal = f"STABLE  //  {ssid}" if ssid else "STABLE"
    emit(row("SIGNAL", signal, COLORS["green"]))
    emit(section("01  SYSTEM IDENTIFICATION", COLORS["cyan"]))
    emit(row("OS", osinfo.get("prettyName", "—"), COLORS["cyan"]))
    emit(row("KERNEL", kernel.get("release", "—")))
    emit(row("INTERFACE", f"{desktop.get('prettyName', '—')} {desktop.get('version', '')}".strip()))
    shell_name = os.path.basename(os.environ.get('SHELL', '')) or shell.get('prettyName', '—')
    emit(row("SHELL", f"{shell_name} {shell.get('version', '')}".strip()))
    emit(row("UPTIME", duration((data.get("uptime") or {}).get("uptime", 0)), COLORS["muted"]))

    emit(section("02  TACTICAL UNIT", COLORS["gold"]))
    emit(row("CPU CORE", cpu.get("cpu", "—"), COLORS["gold"]))
    emit(row("GPU", gpu_names, COLORS["gold"]))

    emit(section("03  BLACK BOX // MEMORY", COLORS["red"]))
    mem_used, mem_total = memory.get("used", 0), memory.get("total", 0)
    emit(bar_row("MEMORY", mem_used, mem_total, COLORS["red"]))
    swap_used = sum(item.get("used", 0) for item in swaps if isinstance(item, dict))
    swap_total = sum(item.get("total", 0) for item in swaps if isinstance(item, dict))
    emit(bar_row("SWAP", swap_used, swap_total, COLORS["orange"]))

    emit(section("04  STORAGE // ARCHIVE", COLORS["blue"]))
    emit(row("ROOT VOLUME", f"{disk.get('filesystem', '—')}  ·  {disk.get('mountFrom', disk.get('mountpoint', '/'))}", COLORS["blue"]))
    emit(bar_row("DISK /", disk_used, disk_bytes.get("total", 0), COLORS["blue"]))

    emit(section("05  NETWORK // SIGNAL", COLORS["green"]))
    if wireless_ip:
        emit(row("WIRELESS", wireless_ip, COLORS["green"]))
    if wired_ip:
        emit(row("WIRED", wired_ip, COLORS["green"]))
    emit(frame_bottom())
    emit("")
    emit(f"  {COLORS['green']}{BOLD}POD LINK: ONLINE{RESET}{COLORS['muted']}  //  {COLORS['white']}GLORY TO MANKIND{RESET}")


if __name__ == "__main__":
    main()
