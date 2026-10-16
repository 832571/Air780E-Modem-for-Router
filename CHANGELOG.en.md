# Changelog

[简体中文](CHANGELOG.md) | **English**

## V1.3 / 1.3.6 (2026-10-15)

- Includes the 1.3.5 SMTP timestamp and Unicode support changes below. Upgrade through LuCI System → Software after updating this signed feed.
- Validation: 61 automated tests, normal connectivity/autostart and three-language UI verified on GL-MT3000. Firmware progress/completion tested with simulation.
- Auto-detect supported USB companion devices and start ECM/DHCP with Air780E first and wired WAN second; preserve explicit manual Stop.
- After three consecutive failed checks, verify WAN before fallback; retain 9-second traffic sampling.
- Explain temporary firmware cache and reboot cleanup; add actual stage progress, verified 100% completion and explicit completion acknowledgement.
- Open Tasks & diagnostics by default with submission/completion timestamps to the second in browser local time.
- Show current-egress public IPv4 below USB Internet, refreshed every 60 seconds, including Tailscale exit use.

## V1.3 / 1.3.5 (development build, shipped with 1.3.6)

- Add automatic python3-codecs dependency and an Install support package button after Refresh forwarding history, with installation and Unicode codec verification.
- Prefix email-forwarding records with SMTP submission date and time down to seconds in the browser local timezone; refresh preserves the original timestamp.
- Migrate existing databases without losing history; legacy records show an unknown submission time instead of a fabricated refresh time.

## V1.3 / 1.3.4 (2026-10-10)

- Add 30-second cellular Internet checks bound to Air780E, with status, timestamps and failure details.
- Add 9-second upload/download bytes, packet counts and rate displays.
- Restart once on failure and retest; fall back to WAN if it still fails. Continue checking without repeated restarts in fallback.
- Manual Stop pauses recovery; manual Start restores 4G priority. Persist policy across service restarts.
- Serialize checks with device operations and use two HTTPS endpoints to reduce false failures. Monitoring runs independently of the browser.
- Pass 41 automated tests and verify the three-language panel and GL-MT3000 live workflow.

## V1.3 / 1.3.3 (2026-10-09)

Adds multilingual UI and bilingual documentation on top of 1.3.2; existing SMS deletion, restoration and network functions remain available.

- Add Stock code: 832571 immediately after DJ Networking in the footer and About information.
- Add Simplified Chinese, English and Traditional Chinese UI; default to Simplified Chinese and remember explicit browser choices.
- Translate interface text, statuses, confirmations and service messages while preserving SMS bodies, form input and protocol confirmation tokens.
- Provide English README, network policy, troubleshooting, release maintenance, third-party notices and changelog; add English descriptions to existing GitHub Releases.

- Validation: 33 automated tests passed. GL-MT3000 LuCI checks cover all three languages, email and firmware prompts, and preservation of drafts, message bodies and selections.
- Upgrade: with this feed configured, update LuCI System → Software lists and upgrade `luci-app-air780e` to 1.3.3. Existing SMS history and settings are retained.
- Compatibility: verified GL-MT3000 / GL4.11.0 / Air780EHV_A11 companion firmware; other models require separate verification.

## V1.3 / 1.3.2

- Add per-record deletion to Sent, select-all for the displayed page and bulk deletion below the list.
- Move deleted sent records into Trash, supporting restoration and preserving send outcomes. Migrate existing databases without losing history.
- Clear selections on tab changes; support indeterminate selection and disabled controls for empty lists.
- Pass 31 automated tests and real LuCI single/bulk deletion and restoration checks.

## V1.3 / 1.3.1

- Use a static GitHub feed compatible with GL's native downloader, retaining usign signatures and TLS validation.
- Update the current GitHub account name to DJ-cn-832571.
- Continue installation after unrelated vendor-feed failures only if this project's verified index was successfully stored.

## V1.3 / 1.3.0

- First public router release with full project source under MIT.
- Provide IPK, signed opkg feed, installer and documentation.
- Port module status, SMS management, forwarding and firmware tools from Mac 0.9.3.
- Fix USB re-enumeration Errno 19, system-DNS curl 6 and unsupported browser prompt dialogs.
- Compile firmware scripts using an isolated GNU loader and check them before entering download mode.
- Prefer Air780E with WAN backup, wait for DHCP at startup and provide LAN NAT.
- Verify actual MT3000 flashing and three start/stop/fallback cycles; pass 29 regression tests.
