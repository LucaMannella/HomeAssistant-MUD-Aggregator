# osMUD on LEDE/OpenWrt – Pre‑Test Checklist & Quickstart (for MUD Aggregator experiments)

This guide is meant to help you prepare an **OpenWrt/LEDE router running osMUD** before running tests with real MUD files generated/exposed by the aggregator.

It is written around a setup like:

- **LEDE 17.01.6** (or similar)  
- osMUD installed as a service (`/etc/init.d/osmud`)  
- dnsmasq as DHCP/DNS  
- OpenWrt firewall (iptables)

> References: osMUD README and deployment notes.  
> osMUD expects DHCP events in a text file (default `/var/log/dhcpmasq.txt`) and can integrate with dnsmasq using a `dhcp-script`.  
> See upstream documentation for background and limitations.


## 0) Assumptions

- Verify that the router is reachable (SSH/LuCI).
- You already have osMUD installed (e.g. `opkg list-installed | grep osmud` shows it).
- You will expose a **gateway-level MUD file** from Home Assistant (this repo) so osMUD can retrieve it.


## 1) Router health checks (do these first)

### 1.1 Time is correct (important for TLS and log debugging)
```sh
date
```

If time is wrong, enable NTP (LuCI: *System → System → Time Synchronization*), or via CLI:
```sh
/etc/init.d/sysntpd enable
/etc/init.d/sysntpd restart
```

### 1.2 Confirm osMUD is installed and enabled

```sh
opkg list-installed | grep -i osmud
ls -l /etc/init.d/osmud
ls -l /etc/rc.d | grep -i osmud
```

### 1.3 Confirm osMUD runtime directories exist

osMUD on OpenWrt typically uses `/var/state/osmud/*`, `/var/log/*`, `/var/run/*`.
```sh
ls -la /var/state/osmud 2>/dev/null || true
ls -la /var/log | grep -i osmud || true
```


## 2) Verify osMUD configuration used at startup

Open the init script:
```sh
cat /etc/init.d/osmud
```

Typical important variables/flags passed to `/usr/bin/osmud`:

- `-e /var/log/dhcpmasq.txt`  → DHCP events input file  
- `-b /var/state/osmud/mudfiles` → MUD file cache directory  
- `-l /var/log/osmud.log` → osMUD log file  
- `-x /var/run/osmud.pid` → PID file  

If your init script uses different paths, adjust the commands in this document accordingly.


## 3) dnsmasq integration (critical)

osMUD needs a stream of DHCP events. Upstream suggests configuring dnsmasq to run a DHCP hook:

### 3.1 Ensure the hook script exists
```sh
ls -la /etc/osmud
ls -la /etc/osmud/detect_new_device.sh
chmod +x /etc/osmud/detect_new_device.sh
```

### 3.2 Enable the hook in dnsmasq (recommended)
**Option A: edit `/etc/dnsmasq.conf`**
Add:
```conf
dhcp-script=/etc/osmud/detect_new_device.sh
```

Restart dnsmasq:
```sh
/etc/init.d/dnsmasq restart
```

**Option B: via UCI (preferred on OpenWrt)**
```sh
uci add_list dhcp.@dnsmasq[0].dhcp_script='/etc/osmud/detect_new_device.sh'
uci commit dhcp
/etc/init.d/dnsmasq restart
```

### 3.3 Confirm events are being written
osMUD will read the file configured with `-e` (often `/var/log/dhcpmasq.txt`):
```sh
ls -l /var/log/dhcpmasq.txt
tail -n 30 /var/log/dhcpmasq.txt
```

Trigger a DHCP event (reconnect a device or renew its lease) and confirm new lines appear.


## 4) Start/stop osMUD and watch logs

### 4.1 Restart osMUD
```sh
/etc/init.d/osmud restart
```

### 4.2 Verify it is running
```sh
ps w | grep -i '[o]smud'
cat /var/run/osmud.pid 2>/dev/null || true
```

### 4.3 Tail osMUD logs (most useful)
```sh
tail -f -n 100 /var/log/osmud.log
```

In another window, tail DHCP events:
```sh
tail -f -n 100 /var/log/dhcpmasq.txt
```

> Note: osMUD logs to its own file if started with `-l /var/log/osmud.log`, so you may not see it in `logread`.


## 5) Pre-test checklist for “real MUD file” trials

Before running your “real device + real MUD file” test, verify:

### 5.1 Router can reach the MUD URL endpoint
From the router, test HTTP/HTTPS connectivity to where you expose the gateway MUD file.

Examples:
```sh
# HTTP (simple for testing)
wget -O- 'http://<HA_IP>:<PORT>/<PATH_TO_MUD>.json' | head

# HTTPS (requires working CA trust on the router)
wget -O- 'https://<HOST>/<PATH_TO_MUD>.json' | head
```

### 5.2 If you use HTTPS, ensure CA certificates are present

Older OpenWrt/LEDE images may lack full CA bundles. If wget/curl fails with TLS errors, install CA certs:
```sh
opkg update
opkg install ca-bundle ca-certificates
```

For Let’s Encrypt or custom CAs, you may need to append intermediate/root certs into:
- `/etc/ssl/certs/ca-certificates.crt`

(Upstream osMUD docs provide examples for Let’s Encrypt chains.)

### 5.3 Ensure firewall rules can be modified by osMUD

osMUD enforces policy using the OpenWrt firewall (iptables). Ensure iptables exists:
```sh
iptables -L -n >/dev/null
```

Optionally check for osMUD-generated rules after you trigger device events:
```sh
iptables -S | grep -i osmud || true
iptables -L -n -v | grep -i osmud || true
```

### 5.4 Clear old test artifacts (optional but useful)

If you want a clean run:
```sh
rm -f /var/log/osmud.log
rm -f /var/log/dhcpmasq.txt
rm -rf /var/state/osmud/mudfiles/*
/etc/init.d/osmud restart
```


## 6) Running the test (suggested sequence)

1. **Start log tails**  
   - `tail -f -n 100 /var/log/dhcpmasq.txt`  
   - `tail -f -n 100 /var/log/osmud.log`

2. **Trigger a DHCP event** for the test device  
   - reconnect Wi‑Fi / unplug/plug ethernet / renew DHCP lease

3. **Confirm osMUD sees the device**  
   Look for lines similar to:
   - `NEW Device Action: IP: ... MAC: ...`
   - `MUD file declared` (for MUD-enabled devices)
   - or `LEGACY DEVICE -- no MUD file declared` (if no MUD URL is provided)

4. **Confirm MUD file download/cache**  
   Check for new files under:
   ```sh
   ls -la /var/state/osmud/mudfiles
   ```

5. **Validate enforcement**  
   - Observe firewall rule changes (iptables)  
   - Validate device connectivity matches policy


## 7) Known gotchas / limitations

- **Stock dnsmasq cannot read the DHCP MUD URL option (RFC 8520) without patches**.  
  Upstream notes that osMUD may require a modified “osmud-dnsmasq” to extract the MUD URL directly from DHCP options. If you do not have patched dnsmasq, osMUD may only treat devices as “legacy” unless your environment injects the MUD URL into the event log via another mechanism.

- Logs and state are typically under `/var` (tmpfs/volatile). They reset on reboot unless you configure persistence.

- **LEDE 17.01 is old**: TLS/cert handling, modern SSH defaults, and package availability can be quirky.


## 8) Handy commands (copy/paste)

### 8.1 One-shot status snapshot

```sh
echo "== date =="; date
echo "== osmud =="; ps w | grep -i '[o]smud' || true
echo "== pid =="; cat /var/run/osmud.pid 2>/dev/null || true
echo "== dhcp events file =="; ls -l /var/log/dhcpmasq.txt 2>/dev/null || true
echo "== last dhcp events =="; tail -n 10 /var/log/dhcpmasq.txt 2>/dev/null || true
echo "== last osmud log =="; tail -n 50 /var/log/osmud.log 2>/dev/null || true
```

### 8.2 Restart loop for quick iteration

```sh
/etc/init.d/osmud restart
/etc/init.d/dnsmasq restart
```


## 9) Pointers

- osMUD upstream docs / usage notes: see the osMUD repository README.
- This repository (HomeAssistant‑MUD‑Aggregator) explains how to generate/expose the gateway-level MUD file from Home Assistant.

