# 网络优先级与恢复

**简体中文** | [English](NETWORK.en.md)
Air780E 接口名为 `air780e`，插件启动设置默认路由 metric 5、DNS metric 5，加入名为 wan 的既有防火墙区域。网线 WAN 常见 metric 10。低 metric 优先，同一优先级不保证固定顺序。

先备份 `/etc/config/network`、`firewall`、`kmwan`、`tailscale`、`glipv6`。不要把这些备份发布到 GitHub。

```sh
uci set network.wan.metric=10
uci set network.wan.dns_metric=10
uci commit network
ubus call network reload
```

GL kmwan 启用时还需在该策略中设置优先级。已验证 MT3000 示例（其他固件需检查接口和原生检测能力）：

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

模块 DHCP 正常并不保证 SIM 可上网。GL 健康检测是额外的故障转移机制；普通路由 metric 只保证接口可用时的选择顺序。使用本地可达的检测地址。

Tailscale exit node、OpenVPN、WireGuard 和其他策略可能优先于 main 表。如果要公共互联网直接经 Air780E，可在 VPN 设置取消默认出口，但保留内网访问。不要直接停用 VPN 服务，以免切断远程管理。MT3000 原生 Tailscale 可用 `tailscale set --exit-node=`，还需同步 GL 设置，避免重启重新启用。

当前模块提供 IPv4。若 WAN 同时发布 IPv6，客户端的 IPv6 连接会优先经 WAN，违背全部公网流量优先 4G 的要求。需要在 GL IPv6 页面关闭 IPv6 或另行实现 IPv6 故障转移。插件安装不会自动替用户修改这一选项。

检查：`ip route`、`ip rule`、`ubus call network.interface.air780e status`，再做「验证 4G 出口」。停止模块后应使用 WAN；重新启动恢复 Air780E。模块与 LAN 的子网不可冲突（模块通常使用 192.168.10.0/24）。

恢复：停止 Air780E，恢复此前备份的配置，重新加载网络与防火墙及 GL kmwan。卸载程序保留用户数据与网络配置；恢复出口策略须单独完成，避免误改其他服务。

## Tailscale 公共出口与 WAN IPv6

可显式配置 Tailscale 公共出口，让公网 IPv4、IPv6 经该节点上网，底层连接仍以 Air780E 为第一、WAN 为第二。需把出口节点同步到 GL 原生 Tailscale 配置，允许本地 LAN 访问，并配置 LAN 到隧道的转发与 NAT。不要发布设备地址及账号状态。

WAN IPv6 隧道可能绕过 Air780E 的 IPv4 优先级。开发路由器通过专用 hotplug 策略处理：Air780E metric 5 默认路由存在时，只对带 Tailscale 标记的外层 IPv6 隧道流量设为不可达，促使其回退 IPv4 并走 Air780E；内层 IPv6 仍可经公共出口访问。停止 4G 后移除该策略，允许 WAN IPv4/IPv6 承载隧道。这是设备专用配置，插件安装不会自动添加。4G 运营商 NAT 可能需要 DERP 中继；WAN IPv6 可实现节点直连。切换底层接口时，现有连接可能短暂中断。

## 自动检测与 WAN 回退（1.3.6）

30 秒是常规检测间隔；检测与短信／固件操作串行，长任务与恢复期间不会叠加检查。每次测试绑定模块 IPv4 源地址和独立路由表，不能用 WAN 或 VPN 的成功替代 4G。一个 HTTPS 端点失败后尝试另一个；失败后停止并重新启动上网，再复测。

连续 3 次检测失败（重启后的复测也计数）且绑定 WAN 的外网验证通过后，把 Air780E 路由 metric 调为 50、停用模块 DNS，在已配置 GL kmwan 时暂时禁用 Air780E 成员，让 metric 10 的 WAN 接管。保留 ECM 接口供后续检测。回退后不自动重新夺回优先级；点击启动上网恢复 metric 5、模块 DNS 和此前 kmwan 状态。安装不会自动配置用户的 Tailscale 公共出口或 WAN IPv6。
