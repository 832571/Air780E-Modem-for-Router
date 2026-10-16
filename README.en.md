# Air780E Modem for Router V1.3

[简体中文](README.md) | **English**

A GL.iNet / OpenWrt LuCI plugin for USB cellular Internet, SMS management and email forwarding.

**Fully open source under the MIT license. Free to use, copy, modify, redistribute and use commercially, provided the copyright and license notices are retained.** See [LICENSE](LICENSE). No subscriptions, activation keys or telemetry. Third-party dependencies and module core firmware have separate licenses; see [Third-party components](THIRD_PARTY.en.md).

Product name: **V1.3**. OpenWrt package version: **1.3.7**. Package: `luci-app-air780e`.

## Verified hardware

| Component | Verified configuration | Other devices |
|---|---|---|
| Router | GL-MT3000, GL 4.11.0, OpenWrt 21.02, ARM64 | Models with USB Host, opkg, LuCI Lua compatibility and Python 3.9+ need separate verification |
| Module | Air780EHV_A11 / EC718HM | Standard Air780E, other models and standard AT firmware are not considered compatible |
| Core firmware | LuatOS V2052 Air780EHV | Must match the board |
| Companion scripts | AIR780E_DEMO 0.2.3 / JSON protocol 1 | Other protocols are unsupported |
| On-router flashing | ARM64 | Other architectures require a compatible external flashing tool |

`Architecture: all` describes platform-independent plugin source; **it does not mean all router models have been tested**. This package is unsuitable for firmware without USB Host, sufficient storage or LuCI Lua support, and for firmware using apk instead of opkg.

## Installation

Configure the third-party feed once, then update lists under LuCI **System → Software**, search for `luci-app-air780e` or `Air780E`, and click Install. This is not a package included in the official GL.iNet feed; it does not automatically appear on other routers.

Download and review the script before running it:

```sh
curl -4 --retry 3 -fL https://github.com/832571/Air780E-Modem-for-Router/releases/latest/download/install-feed.sh -o /tmp/install-air780e.sh
sh /tmp/install-air780e.sh
```

The script checks the feed public-key fingerprint and signed index, preserves official feeds, updates lists and installs the plugin. Public-key fingerprint: `af5c2a6ce4ab8132`. To configure only the feed: `sh /tmp/install-air780e.sh --feed-only`.

Alternatively, download the IPK from [Releases](https://github.com/832571/Air780E-Modem-for-Router/releases) and use **Upload Package** in LuCI. Dependencies must come from your router's firmware feed. Do not force-install USB drivers for another kernel or bulk-upgrade vendor packages.

Open **Services → Air780E Modem**. GL's management page and LuCI may use different ports; the development router uses port 8080 for LuCI. Connect the module, click **Start Internet**, wait for DHCP, then click **Verify 4G connection**.

## Features

- System settings persist configurable 4G checks (default 30 seconds, range 5–3600), failure threshold (default 3, range 1–20), and traffic refresh (default 9 seconds, range 1–3600). Failed recovery retests count toward the threshold.
- If the SIM supplies no phone number, save a manual receiving number such as `+8613800000000`. Emails use the number captured per SMS; unknown legacy numbers are not backfilled using the current SIM.
- Module reads and settings saves show a localized loading indicator in all three languages.

- Automatically detect supported USB companion devices and start ECM/DHCP with Air780E metric 5 and wired WAN metric 10; explicit Manual Stop pauses recovery.
- Open Tasks & diagnostics by default, with submission/completion timestamps. Show current-egress public IPv4 under USB Internet, refreshed every 60 seconds.
- Display actual firmware stage progress, verified 100% completion and explicit acknowledgement. Cache: `/tmp/air780e-firmware`; no scheduled cleanup, cleared on router reboot.
- Depend on `python3-codecs` automatically and provide Install support package for Unicode verification/repair. Forwarding history includes SMTP submission time; unavailable legacy timestamps remain unknown.
- This release passes 61 regression tests; firmware progress/completion use simulation, without repeating a live flash. and languages

- Check SIM cellular Internet through the Air780E interface every 30 seconds, showing state and last check time; use two independent HTTPS endpoints.
- Sample and display USB upload/download bytes, packets and rates every 9 seconds. Cumulative counters may reset on reconnection, include probes/tunnel traffic, and do not represent carrier billing.
- On failed connectivity, restart 4G once and retest; after three consecutive failed checks, verify WAN and switch only if it is usable. Continue checking in fallback without repeated restarts. Click Start Internet to restore 4G priority. Manual Stop pauses automatic recovery; closing the page does not stop monitoring.
- Checks share a serialized queue with SMS and firmware tasks to prevent concurrent USB control. Busy tasks, restart and timeout handling can defer checks.

- Simplified Chinese, English and Traditional Chinese UI. Simplified Chinese is the initial default; the browser remembers explicit language choices. Switching languages preserves SMS content and form input.
- USB ECM start/stop, hotplug reconnection, DHCP wait and independent 4G DNS/HTTPS verification.
- Cellular signal, RSRP, SMS readiness and the phone number provided by the SIM.
- Chinese SMS sending, inbox, sent history, replies and filling failed messages for a separately confirmed resend.
- Per-record sent-history deletion, select-all for the displayed page and bulk deletion below the list. Deleted records can be restored from Trash; send outcomes are preserved. Unknown outcomes are never automatically resent.
- Forward to up to three email addresses using SSL / STARTTLS with certificate validation. Background forwarding continues when the page is closed.
- ARM64 firmware resource preparation, model confirmation, core and companion script installation / repair.
- Redacted diagnostics and MIT information. Management API requires a LuCI session and CSRF validation.

SMS center acceptance does not guarantee recipient delivery. Cellular data and SMS are charged according to your carrier plan. SMTP testing checks the connection and authentication without sending a test email.

## Network priority

Starting Internet sets Air780E DHCP default-route metric 5, uses module DNS and adds the interface to the existing WAN firewall zone for NAT. Stopping disables module Internet and withdraws its interface. Wired WAN metric 10 produces **Air780E first, wired WAN second**.

VPN exit nodes, policy routing, IPv6 and GL kmwan can override ordinary default routing. Installation does not automatically disable VPNs or IPv6, or reconfigure other WANs. See [Network policy](docs/NETWORK.en.md) for configuration, backups and recovery, including Tailscale exit nodes with WAN IPv6.

## Firmware and privacy

Installing the plugin does not flash the module automatically. Enter `Air780EHV_A11` and explicitly confirm overwrite before flashing. Synchronize SMS first and maintain power. Tools and the official core are downloaded on demand from pinned URLs with SHA-256 checks. Isolated runtime libraries do not replace OpenWrt system libraries. Firmware preparation needs at least 40 MB free temporary storage; dependencies and runtime libraries require additional space.

SMS, settings and SMTP passwords are stored under `/etc/air780e/`, with directory mode 0700 and sensitive file mode 0600. **There is no application-level encryption; router root can read them.** Forwarding sends numbers, timestamps and message bodies, potentially including verification codes, to the configured SMTP server and recipients. Disabled forwarding does not deliver messages. No built-in recipient or remote-management endpoint is provided.

Uninstall with `opkg remove luci-app-air780e`; history and settings are retained. Removing the feed stops updates from this project. See [Troubleshooting](docs/TROUBLESHOOTING.en.md) for cleanup.

## Verification, source and feedback

Verified on the development MT3000: actual core/script flashing, USB reconnection, three start/stop cycles, WAN fallback, bound 4G HTTPS and HTTP 200 from a real LAN client. Sent-history deletion and restoration have been tested through LuCI. Other models, full power-cycle behavior and sustained stress testing still require verification.

```sh
PYTHONPATH=files/usr/lib/air780e python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

See [Release maintenance](docs/RELEASING.en.md) and [Changelog](CHANGELOG.en.md). Report [Issues](https://github.com/832571/Air780E-Modem-for-Router/issues) with router model, firmware version, module model and redacted diagnostics. Do not upload numbers, SMS, passwords, databases or signing keys.

Independent community project; not an official GL.iNet or AirM2M product. DJ Networking · **Stock code: 832571** · [www.DJ.cn](https://www.DJ.cn) · Cai Liwen · cailiwen@dj.cn.
