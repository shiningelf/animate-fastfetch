#!/usr/bin/env python3
"""Render a bordered, two-column Fastfetch panel with live module data."""
import base64, json, subprocess, sys, os, re, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESC = "\x1b["
COL = {
    "pink": "\x1b[38;2;255;46;166m", "pink2": "\x1b[38;2;255;46;166m",
    "green": "\x1b[38;2;0;245;212m", "blue": "\x1b[38;2;0;217;255m",
    "muted": "\x1b[38;2;118;128;151m", "text": "\x1b[38;2;220;224;236m",
    "red": "\x1b[38;2;226;49;75m", "reset": "\x1b[0m", "bold": "\x1b[1m"
}

def collect():
    p = subprocess.run(["fastfetch", "--format", "json", "--config", str(HERE / "data.jsonc")], capture_output=True, text=True)
    if p.returncode:
        print("Fastfetch data collection failed: " + p.stderr.strip(), file=sys.stderr)
        return {}
    try:
        return {x["type"].lower(): x.get("result") for x in json.loads(p.stdout) if "result" in x}
    except Exception:
        return {}

def human(n):
    n = float(n or 0); units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024

def uptime(sec):
    sec = int(sec or 0); d, sec = divmod(sec,86400); h, sec = divmod(sec,3600); m = sec//60
    return f"{d}d {h:02}h {m:02}m" if d else f"{h}h {m}m"

def module(data, name, fallback="—"):
    return data.get(name.lower(), fallback) if data.get(name.lower()) is not None else fallback

def result_text(value, *keys, default="—"):
    if not isinstance(value, dict): return default
    for key in keys:
        v=value.get(key)
        if v: return str(v)
    return default

def data_error_for(kind):
    # Network collection can be denied in restricted environments; show a clear value.
    return "Unavailable" if kind not in info else "—"

info = collect()
osinfo=module(info,"os",{}); kernel=module(info,"kernel",{}); de=module(info,"de",{}); shell=module(info,"shell",{}); up=module(info,"uptime",{})
cpu=module(info,"cpu",{}); mem=module(info,"memory",{}); swap=module(info,"swap",[]); gpus=module(info,"gpu",[]); disks=module(info,"disk",[])
wifi=module(info,"wifi",{}); local=module(info,"localip",{})
if not isinstance(swap,list): swap=[]
if not isinstance(gpus,list): gpus=[]
if not isinstance(disks,list): disks=[]

def val(obj,*keys,default="—"):
    return result_text(obj,*keys,default=default)

def dim_bar(used,total,n=16):
    pct=0 if not total else max(0,min(1,used/total))
    return COL['pink2']+"█"*round(n*pct)+COL['muted']+"░"*(n-round(n*pct))+COL['reset']

def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W","F") else 1 for c in str(s))

def fit(s,n):
    s=str(s).replace("\n"," ")
    out=""
    for c in s:
        if width(out+c)>n:
            return out+"…" if width(out+"…")<=n else out
        out+=c
    return out+" "*(n-width(out))

def trim(s,n):
    return fit(s,n).rstrip()

def border_line(left, mid, right, width, color):
    return color+left+mid*width+right+COL['reset']

def titled_border(total_width, title, color):
    label=" "+title+" "
    remaining=max(0,total_width-2-width(label))
    left=0
    right=remaining
    return color+"╭"+"─"*left+COL['bold']+label+COL['reset']+color+"─"*right+"╮"+COL['reset']

def content(left, right, total_width, lc, rc, leftw):
    inner_right=total_width-leftw-4
    right=trim(right,inner_right)
    return lc+"│"+COL['reset']+" "+lc+fit(left,leftw)+COL['reset']+" "+rc+fit(right,inner_right)+lc+"│"+COL['reset']

# Dynamic values from Fastfetch JSON
osval=val(osinfo,"prettyName","name")
os_signature=(str(osinfo.get("id", ""))+" "+osval).lower() if isinstance(osinfo,dict) else osval.lower()
os_icon="" if "manjaro" in os_signature else ""
kval=val(kernel,"release")
dval=val(de,"prettyName","name")+((" "+str(de.get("version"))) if de.get("version") else "")
sval=os.path.basename(os.environ.get("SHELL", val(shell,"prettyName","exeName")))+((" "+str(shell.get("version"))) if shell.get("version") else "")
uval=uptime(up.get("uptime",0)/1000) if up else "—"
cpuname=val(cpu,"cpu")
mem_used=mem.get("used",0) if isinstance(mem,dict) else 0; mem_total=mem.get("total",0) if isinstance(mem,dict) else 0
swap_used=sum(x.get("used",0) for x in swap); swap_total=sum(x.get("total",0) for x in swap)
gpu_names=[trim(x.get("name","GPU"),32) for x in gpus if isinstance(x,dict)] or ["—"]
disk=next((d for d in disks if d.get("mountpoint")=="/"), disks[0] if disks else {})
disk_used=max(0,disk.get("bytes",{}).get("total",0)-disk.get("bytes",{}).get("free",0)); disk_total=disk.get("bytes",{}).get("total",0)
def run_text(args, timeout=3):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        return p.stdout.strip() if p.returncode==0 else ""
    except (OSError,subprocess.TimeoutExpired):
        return ""

def active_wifi_device():
    rows=run_text(["nmcli","-t","--escape","yes","-f","DEVICE,TYPE,STATE","device","status"])
    for row in rows.splitlines():
        fields=row.split(":",2)
        if len(fields)==3 and fields[1].lower() in ("wifi","wireless") and fields[2].lower().startswith("connected"):
            return fields[0]
    for name in ("/sys/class/net/wlp6s0",):
        if Path(name).exists(): return Path(name).name
    for d in sorted(Path("/sys/class/net").glob("wl*")):
        return d.name
    return ""

def active_wifi_ssid(device=""):
    value=val(wifi,"ssid",default="")
    if value and value!="—": return value
    if device:
        connection=run_text(["nmcli","-g","GENERAL.CONNECTION","device","show",device])
        if connection:
            ssid=run_text(["nmcli","-g","802-11-wireless.ssid","connection","show",connection])
            if ssid: return ssid
    rows=run_text(["nmcli","-t","--escape","yes","-f","active,ssid","device","wifi"],timeout=8)
    for row in rows.splitlines():
        if row.startswith("yes:"):
            return row[4:].replace("\\:", ":").replace("\\\\", "\\") or "Unavailable"
    return "Unavailable"

def active_ethernet_device():
    rows=run_text(["nmcli","-t","--escape","yes","-f","DEVICE,TYPE,STATE","device","status"])
    for row in rows.splitlines():
        fields=row.split(":",2)
        if len(fields)==3 and fields[1].lower() in ("ethernet","802-3-ethernet") and fields[2].lower().startswith("connected"):
            return fields[0]
    return ""

def device_ipv4(device):
    if not device: return "Unavailable"
    out=run_text(["ip","-o","-4","addr","show","dev",device,"scope","global"])
    m=re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)",out)
    if m: return m.group(1)
    if isinstance(local,dict):
        for entry in local.get("ipv4",[]) or []:
            if isinstance(entry,dict) and entry.get("address"):
                return entry["address"]+(f"/{entry['prefix']}" if entry.get('prefix') else "")
    return "Unavailable"

def device_gateway(device):
    if not device: return "Unavailable"
    value=run_text(["nmcli","-g","IP4.GATEWAY","device","show",device])
    if value and value!="--": return value.splitlines()[0]
    routes=run_text(["ip","-4","route","show","default","dev",device])
    m=re.search(r"\bvia\s+(\d+\.\d+\.\d+\.\d+)",routes)
    return m.group(1) if m else "Unavailable"

wifi_device=active_wifi_device()
eth_device=active_ethernet_device()
ssid=active_wifi_ssid(wifi_device)
wifi_ip=device_ipv4(wifi_device)
wifi_gateway=device_gateway(wifi_device)
lan_ip=device_ipv4(eth_device) if eth_device else wifi_ip
lan_gateway=device_gateway(eth_device) if eth_device else wifi_gateway

# Right content is 88 terminal cells wide: 40 SYSTEM + 46 HARDWARE + 2 gap.
W=80; SW=36; HW=42
out=[]
# Quote frame
q1="幸せかどうかは自分で決める。"; q2="大切なのは”今”なんだよ"
quote=q1+" "+q2
out += [COL['pink']+"╭"+"─"*(W-2)+"╮"+COL['reset'],
        COL['pink']+"│"+COL['reset']+"  "+COL['text']+quote+" "*max(0,W-4-width(quote))+COL['pink']+"│"+COL['reset'],
        COL['pink']+"╰"+"─"*(W-2)+"╯"+COL['reset']]
# Info cards
out.append(titled_border(SW,"霊魂",COL['green'])+"  "+titled_border(HW,"義体",COL['pink']))
left_rows=[(os_icon+" OS",osval),(" KERNEL",kval),(" DE",dval),(" SHELL",sval),("󰔚 UPTIME",uval)]
right_rows=[(" CPU",cpuname),(" MEMORY",f"{human(mem_used)} / {human(mem_total)}"),("󰓡 SWAP",f"{human(swap_used)} / {human(swap_total)}")] + [("󰢮 GPU",name) for name in gpu_names] + [("󰋊 DISK /",f"{human(disk_used)} / {human(disk_total)}")]
rows=max(len(left_rows),len(right_rows))+2
for i in range(rows):
    if i==0 or i==rows-1:
        l=COL['green']+"│"+COL['reset']+" "*(SW-2)+COL['green']+"│"+COL['reset']
        r=COL['pink']+"│"+COL['reset']+" "*(HW-2)+COL['pink']+"│"+COL['reset']
    else:
        a=left_rows[i-1] if i-1<len(left_rows) else ("","")
        b=right_rows[i-1] if i-1<len(right_rows) else ("","")
        l=content(a[0],a[1],SW,COL['green'],COL['text'],9)
        valstr=b[1]
        if b[0]: r=content(b[0],valstr,HW,COL['pink'],COL['text'],8)
        else:
            r=COL['pink']+"│"+COL['reset']+"  "+valstr+" "*(HW-20)+COL['pink']+"│"+COL['reset']
    out.append(l+"  "+r)
out.append(border_line("╰","─","╯",SW-2,COL['green'])+"  "+border_line("╰","─","╯",HW-2,COL['pink']))
# 神経: Wireless (Wi-Fi) and Wired (Ethernet), aligned IP and router rows.
net_left=38; net_right=39
out.append(titled_border(W,"神経",COL['blue']))
def network_cell(label,value,n,bold=False):
    label_width=min(width(label),n)
    style=COL['blue']+(COL['bold'] if bold else "")
    return style+fit(label,label_width)+COL['reset']+COL['text']+fit(value,n-label_width)+COL['reset']
out.append(COL['blue']+"│"+COL['reset']+network_cell("󰖩 Wireless ",ssid,net_left,True)+COL['blue']+"│"+COL['reset']+network_cell("󰈀 Wired","",net_right,True)+COL['blue']+"│"+COL['reset'])
def network_row(left_label,left_value,right_label="",right_value=""):
    return COL['blue']+"│"+COL['reset']+network_cell(left_label,left_value,net_left)+COL['blue']+"│"+COL['reset']+network_cell(right_label,right_value,net_right)+COL['blue']+"│"+COL['reset']
out.append(network_row("󰩟 IP: ",wifi_ip,"󰩟 IP: ",lan_ip))
out.append(network_row("󰑩 Router: ",wifi_gateway,"󰑩 Router: ",lan_gateway))
out.append(border_line("╰","─","╯",W-2,COL['blue']))
# Unframed, five-row ASCII NEZUKO title; the small PNG stays beside it.
logo=HERE/"kimetsunoyaiba-footer.png"
if logo.exists():
    payload=base64.b64encode(logo.read_bytes()).decode()
    chunks=[payload[i:i+4096] for i in range(0,len(payload),4096)]
    apc=[]
    for i,ch in enumerate(chunks):
        start="a=T,f=100,c=6,r=3,C=1,q=2," if i==0 else ""
        more=1 if i<len(chunks)-1 else 0
        apc.append(f"\x1b_G{start}m={more};{ch}\x1b\\")
    im="".join(apc)
else: im=""
letters={
 "N":["##   ##","###  ##","## # ##","##  ###","##   ##"],
 "E":["#######","##     ","###### ","##     ","#######"],
 "Z":["#######","    ## ","   ##  "," ##    ","#######"],
 "U":["##   ##","##   ##","##   ##","##   ##"," ##### "],
 "K":["##  ## ","## ##  ","####   ","## ##  ","##  ## "],
 "O":[" ##### ","##   ##","##   ##","##   ##"," ##### "],
}
word_rows=[" ".join(letters[ch][i] for ch in "NEZUKO") for i in range(5)]
for i,row in enumerate(word_rows):
    image=im if i==1 else ""
    out.append(image+ESC+"8C"+COL['bold']+COL['pink2']+row+COL['reset']+" "*(W-55))
out.append("")
out.append(COL['muted']+"  ● "+COL['pink']+"● "+COL['text']+"● "+COL['green']+"● "+"\x1b[38;2;231;125;104m● "+COL['blue']+"●"+COL['reset'])
print("\n".join("\r"+ESC+"40C"+line for line in out))
