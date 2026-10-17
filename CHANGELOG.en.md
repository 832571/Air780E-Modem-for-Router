# Changelog

[简体中文](CHANGELOG.md) | **English**

## V1.3 / 1.3.9 (2026-10-17)

- Add an off-by-default Allow USB Internet while roaming checkbox. Companion script 0.2.4 reports registration/roaming state and confirms persistent policy changes.
- Block USB data after reported roaming while preserving SMS/control and explicit manual Stop. Initially unknown registration starts closed; re-registration retains the previous decision to avoid USB reset loops.
- Legacy scripts remain readable but cannot enable the control. Does not activate carrier roaming or guarantee zero traffic/charges before detection.
- 78 Python tests plus Lua policy/full-script simulation. Real roaming requires a suitable SIM and network for separate validation.

Upgrade note: the IPK does not flash the modem automatically. Roaming control requires companion script 0.2.4. Legacy 0.2.3 retains existing functions with the checkbox disabled. Explicitly confirm Install / repair firmware to upgrade the module; USB Internet is interrupted during flashing. The test router verified opt-in/out, retained off state, intact SMS history and Google HTTPS 200.

## V1.3 / 1.3.8 (2026-10-16)
- Default to 1.1.1.1 and 9.9.9.9 with persistent configuration on first startup. Edit primary and secondary IPv4 DNS in System settings.
- Apply saved DNS to the cellular interface and router-wide forwarding, overriding DHCP DNS. Preserve values across service restart and cellular reconnection.
- Address incorrect carrier DNS responses that prevent Google access. Preserve the existing Tailscale exit, WAN IPv6 and manual Stop policy; restore previous DNS configuration if apply fails.
- 71 automated tests cover validation, persistence and rollback. GL-MT3000 verified DNS changes/restoration, Google HTTPS 200 and preserved exit routing.


- Display the monitoring policy as a full sentence with configured intervals and failure threshold in all three languages.
- Confirm WAN fallback requires the failure threshold and successful WAN Internet verification. Add tests for no premature WAN probe and cancellation during WAN verification; 71 tests pass.

## V1.3 / 1.3.7 (2026-10-15)

- Forwarded emails include the receiving phone number captured when the SMS is stored, preventing later SIM changes from relabeling older messages. Legacy records without a number are explicitly marked unknown.
- System settings accept a persistent manual number in `+country-code-and-phone-number` format. Used only when the SIM does not supply a number, for subsequent SMS and the status display.
- Display “Loading content” during navigation, initial reads and settings saves; clear it on success or failure and ignore obsolete module responses during rapid navigation.
- Persist and apply configurable 4G checks (default 30 seconds, range 5–3600), consecutive failure threshold (default 3, range 1–20), and traffic sampling/refresh (default 9 seconds, range 1–3600).
- Restart once on initial failure. A failed recovery retest also counts. Fall back only after the threshold and successful WAN verification; preserve manual Stop, Air780E priority and existing Tailscale configuration.
- Update Simplified Chinese, English and Traditional Chinese interfaces. Full source remains MIT licensed.
- Validation: 65 automated tests. GL-MT3000 verified settings save, persistence across service restart, restored defaults, loading indicators and all three languages. Email bodies tested using mocked SMTP, without extra email delivery or firmware flashing.
- After configuring this signed project feed, update lists in LuCI System → Software and upgrade `luci-app-air780e`. This is a community feed, not an official GL.iNet/OpenWrt listing.

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
