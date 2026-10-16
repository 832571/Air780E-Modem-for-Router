# Air780E Modem for Router V1.3

**简体中文** | [English](README.en.md)
USB 蜂窝上网、短信管理与邮件转发的 GL.iNet / OpenWrt LuCI 插件。

**采用 MIT 协议，完整项目源码开放。可免费使用、复制、修改、再分发及商业使用，须保留版权和许可证声明。** 查看 [LICENSE](LICENSE)。本项目没有订阅、授权码或遥测；第三方依赖与模块核心固件的许可独立于本项目，见 [第三方说明](THIRD_PARTY.md)。

产品名称 **V1.3**，OpenWrt 软件包版本 **1.3.6**，软件包名 `luci-app-air780e`。

## 已支持的设备

| 项目 | 已验证 | 其他设备 |
|---|---|---|
| 路由器 | GL-MT3000，GL 4.11.0，OpenWrt 21.02，ARM64 | 有 USB Host、opkg、LuCI Lua 兼容层与 Python 3.9+ 的型号需另行验证 |
| 模块 | Air780EHV_A11 / EC718HM | 普通 Air780E、其他型号及标准 AT 固件不能视为兼容 |
| 模块核心 | LuatOS V2052 Air780EHV | 必须匹配开发板 |
| 配套脚本 | AIR780E_DEMO 0.2.3 / JSON protocol 1 | 不识别其他协议 |
| 路由器内烧录 | ARM64 | 其他架构可研究日常功能，烧录需兼容的外部工具 |

`Architecture: all` 表示插件源码与平台无关，**不代表全部路由器型号已测试**。无 USB Host、空间不足、apk 包管理器或缺少 LuCI Lua 支持的固件不适用本发布包。

## 安装

安装第三方软件源一次后，LuCI「系统 → 软件包」中更新列表、搜索 `luci-app-air780e` 或 `Air780E`，点击安装即可。它不是 GL.iNet 官方收录软件包，不会自动出现在未配置软件源的其他路由器上。

推荐先下载并阅读脚本，再执行：

```sh
curl -4 --retry 3 -fL https://github.com/832571/Air780E-Modem-for-Router/releases/latest/download/install-feed.sh -o /tmp/install-air780e.sh
sh /tmp/install-air780e.sh
```

脚本核验软件源公钥指纹和索引签名，保留官方软件源，更新列表并安装插件。公钥指纹：`af5c2a6ce4ab8132`。仅配置源而不安装：`sh /tmp/install-air780e.sh --feed-only`。

也可从 [Releases](https://github.com/832571/Air780E-Modem-for-Router/releases) 下载 IPK，在 LuCI 软件包页的「上传软件包」安装。依赖需要从路由器自己的固件源获取；不要强制安装其他内核版本的 USB 驱动，也不要批量升级厂商预装软件。

安装后在 LuCI「服务 → Air780E Modem」打开。GL 管理网页与 LuCI 可能使用不同端口；开发机 LuCI 使用 8080。插入模块、点击「启动上网」，等待 DHCP 完成，再点击「验证 4G 出口」。

## 功能

- 自动识别受支持的 USB 配套设备并启动 ECM/DHCP，Air780E metric 5、网线 WAN metric 10；手动停止暂停自动恢复。
- 默认打开任务与诊断，任务显示提交／完成时间；USB 上网卡片显示当前出口公网 IPv4，每 60 秒更新。
- 固件安装显示真实阶段进度，协议验证成功后显示 100%，由用户确认完成。缓存位于 `/tmp/air780e-firmware`，无定时清理，重启路由器后清空。
- 自动依赖 `python3-codecs`；邮件转发页提供“安装支持包”检查和修复 Unicode 支持。转发记录显示 SMTP 提交时间，旧记录无法追溯时明确标为未知。

- 每 30 秒检测绑定 Air780E 的 SIM 蜂窝外网连接，显示状态和上次检测时间；支持两个独立 HTTPS 测试端点。
- 每 9 秒采样并显示 USB 网卡上传／下载字节、数据包数和速率；网卡累计值可能在重连后重置，包含测试及隧道流量，不代表运营商账单。
- 首次联网检测失败时重启一次 4G 并复测，连续失败 3 次后先验证 WAN，WAN 可用才切换；回退后继续检测，不反复重启。点击启动上网恢复 4G 优先。手动停止会暂停自动恢复，关闭网页不停止后台检测。
- 检测与短信、固件任务共用串行队列，不并发控制 USB；任务忙碌、重启及超时时检测可能顺延。

- 简体中文、English、繁體中文三种界面语言；首次默认简体中文，可记住浏览器内的选择，不翻译短信正文或改动输入。

- USB ECM 启停、热插拔重连、DHCP 等待与独立 4G DNS/HTTPS 验证。
- 蜂窝信号、RSRP、短信就绪和 SIM 提供的本机号码。
- 中文短信发送、收件箱、已发送记录、回复、失败记录填入重发。
- 删除、恢复和清空已删除记录；发送结果未知时不自动重发。
- 最多三个邮箱自动转发，SSL / STARTTLS 与证书校验；后台常驻，关闭网页仍运行。
- ARM64 固件资源准备、型号确认与核心+配套脚本安装修复。
- 本地诊断与 MIT 开源说明；管理接口需要 LuCI 登录和 CSRF 校验。

短信中心接受不等于手机收到。短信和上网按运营商套餐计费。SMTP 测试只验证连接与认证，不主动发送测试邮件。

## 出口策略

启动会把 Air780E DHCP 默认路由设为 metric 5、使用模块 DNS，并加入既有 WAN 防火墙区提供 NAT。停止会关闭模块上网并撤下自身接口。网线 WAN 设为 metric 10 时形成「Air780E 第一、网线第二」。

VPN 默认出口、策略路由、IPv6 和 GL kmwan 可能覆盖普通默认路由。插件安装不会自动取消用户 VPN、关闭 IPv6或修改所有其他 WAN；详细配置、备份与恢复见 [网络策略](docs/NETWORK.md)。

## 固件与隐私

插件安装不会自动烧写模块。烧写前必须输入 `Air780EHV_A11` 并确认覆盖；先同步短信、保持供电。工具和官方核心在需要时按固定 URL 与 SHA-256 下载，使用隔离运行库，不替换 OpenWrt 系统库。固件缓存至少需 40 MB 临时空闲空间；完整依赖和运行库需要额外存储空间。

短信、设置、SMTP 密码位于 `/etc/air780e/`，目录 0700、敏感文件 0600。**没有应用层加密，路由器 root 可读。** 邮件转发会把号码、时间及正文发给用户配置的 SMTP 服务器与邮箱，可能包含验证码。关闭转发后不投递。本项目不内置收件人或远程管理入口。

卸载：`opkg remove luci-app-air780e`，保留历史和设置。删除软件源后不会继续收到本项目软件源更新；数据清理方法见 [故障排查](docs/TROUBLESHOOTING.md)。

## 验收、源码与反馈

已验证实际核心及脚本烧录、USB 重连、三轮启停、WAN 回退、绑定 4G HTTPS 和真实 LAN 客户端 HTTP 200。本次 61 项回归测试通过；v1.3.6 固件阶段进度及完成确认采用模拟验证，未重复执行实机刷写。其他型号、完整断电重启和长时间压力测试仍需验证。

```sh
PYTHONPATH=files/usr/lib/air780e python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

发布流程与软件源签名见 [发布说明](docs/RELEASING.md)。版本变化见 [CHANGELOG](CHANGELOG.md)。反馈请提交 [Issue](https://github.com/832571/Air780E-Modem-for-Router/issues)，包含路由器型号、固件版本、模块型号及脱敏诊断；不要上传号码、短信、密码、数据库或签名私钥。

独立社区项目，非 GL.iNet 或合宙官方产品。点击网络 · **股票代码：832571** · [www.DJ.cn](https://www.DJ.cn) · 蔡立文 · cailiwen@dj.cn。
