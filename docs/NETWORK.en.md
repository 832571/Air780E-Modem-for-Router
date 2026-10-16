# Network priority and recovery

[简体中文](NETWORK.md) | **English**

The plugin interface is `air780e`. Starting sets default-route and DNS metric 5 and joins the existing `wan` firewall zone. Wired WAN commonly uses metric 10. Lower metrics are preferred; equal metrics do not guarantee a fixed order.

Back up `/etc/config/network`, `firewall`, `kmwan`, `tailscale` and `glipv6` first. Do not publish these backups on GitHub.

```sh
uci set network.wan.metric=10
uci set network.wan.dns_metric=10
uci commit network
ubus call network reload
```

If GL kmwan is enabled, configure its priority too. This MT3000 example was verified; check interfaces and native health-check capabilities on other firmware:

```sh
uci set kmwan.air780e=member
uci set kmwan.air780e.interface=air780e
uci set kmwan.air780e.metric=5
uci set kmwan.air780e.weight=1
uci set kmwan.air780e.track_mode=force
uci set kmwan.air780e.addr_type=4
uci set kmwan.air780e.disabled=0
uci set kmwan.air780e.check=1
uci add_list kmwan.air780e.tracks='ping,223.5.5.5'
uci add_list kmwan.air780e.tracks='ping,119.29.29.29'
uci commit kmwan
/etc/init.d/kmwan restart
```

Successful DHCP does not guarantee SIM Internet access. GL health checks provide additional failover; ordinary route metrics determine order while interfaces are available. Use locally reachable probe addresses.

Tailscale exit nodes, OpenVPN, WireGuard and other policies can precede the main table. To route public traffic directly over Air780E, deselect the VPN exit node while preserving private-network access. Do not stop VPN services blindly and lose remote management. On MT3000, `tailscale set --exit-node=` must also be reflected in GL settings so GL does not re-enable it.

The verified module supplies IPv4. If WAN advertises IPv6, IPv6 traffic may use WAN even when Air780E has the lower IPv4 metric. Disable IPv6 in GL settings if all public traffic must use 4G, or implement an explicit IPv6 policy. Installation does not change this setting automatically.

## Tailscale exit node with WAN IPv6

An explicitly configured Tailscale exit node can provide public IPv4 and IPv6 Internet while the underlying uplink prefers Air780E and falls back to WAN. Save the node selection in GL's native Tailscale configuration as well as Tailscale preferences, allow local LAN access, and configure LAN forwarding/NAT to the tunnel. Do not publish device-specific addresses or account state.

WAN IPv6 transport can otherwise bypass Air780E's IPv4 priority. The development router uses a separate hotplug policy: while the Air780E metric-5 route exists, only marked outer Tailscale IPv6 transport is made unreachable so Tailscale falls back to IPv4 over Air780E. Inner IPv6 traffic still traverses the exit node. When Air780E stops, that policy is removed and WAN IPv4/IPv6 can carry the tunnel. This is a router-specific configuration, not a policy installed automatically by the package. Carrier NAT may require DERP relay over 4G; WAN IPv6 can permit direct peer connectivity. A change of uplink can briefly interrupt existing connections.

Check `ip route`, `ip rule` and `ubus call network.interface.air780e status`, then run **Verify 4G connection**. Stopping the module should use WAN; restarting should restore Air780E. Module and LAN subnets must not conflict; the module commonly uses 192.168.10.0/24.

To restore prior policy, stop Air780E, restore backed-up configuration and reload networking, firewall and GL kmwan. Uninstall retains data and network settings; restore routing separately to avoid changing unrelated services.

## Automatic checking and WAN fallback (1.3.6)

30 seconds is the normal check interval. Checks are serialized with SMS/firmware operations; long tasks and recovery do not overlap checks. Probes bind the module IPv4 source and a dedicated routing table, so WAN/VPN success cannot substitute for 4G success. Try a second HTTPS endpoint if the first fails; stop and restart Internet once, then retest.

After three consecutive failed checks (including the post-restart retest), verify Internet bound to WAN first. Only if WAN succeeds, set Air780E route metric 50, disable module DNS and temporarily disable its GL kmwan member when configured, allowing metric-10 WAN to take over. Keep ECM available for subsequent checks. Fallback does not automatically reclaim priority; click Start Internet to restore metric 5, module DNS and prior kmwan state. Installation does not automatically configure a Tailscale exit node or WAN IPv6.
