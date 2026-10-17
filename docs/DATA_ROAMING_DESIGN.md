# 数据漫游控制方案 / Data roaming control proposal

状态：用户已确认 USB 漫游策略及模块脚本升级；版本 1.3.9 / 脚本 0.2.4。
Status: USB roaming policy and module upgrade authorized; plugin 1.3.9 / script 0.2.4.

## 已核对 / Verified

- 测试设备当前插件 1.3.8、配套脚本 AIR780E_DEMO 0.2.3，支持 status/inbox/start/stop/send_sms。当前状态没有网络注册状态或漫游控制能力字段。
- The current companion script reports no registration/roaming status and exposes no roaming-control command.
- 官方 mobile.status() 提供已注册/已注册漫游状态；官方 FAQ 说明 LuatOS 没有单独开启漫游接口。能否漫游注册取决于 SIM 业务、运营商协议及频段覆盖。
- LuatOS exposes registration/roaming status, but no standalone roaming-enable API. Registration depends on SIM service, carrier agreements and supported radio bands.

## 建议范围 / Proposed scope

系统设置增加默认未勾选的“允许漫游时通过 USB 上网”。这是 USB 数据使用策略，不是为 SIM 开通漫游业务，也不是禁止模块注册到漫游网络。
Add an unchecked-by-default “Allow USB Internet while roaming” checkbox. This controls USB data use; it neither activates a carrier roaming plan nor prohibits roaming registration.

- 新模块协议明确上报 roamingControlSupported、registrationStatus、roaming、dataRoamingAllowed、roamingBlocked，并对设置命令确认实际应用结果。
- Explicit capability, registration, roaming and applied-policy fields with command acknowledgement.
- 不把“已勾选”当作已经生效；不兼容的 0.2.3 脚本禁用控件并提示需升级。
- Unsupported 0.2.3 scripts must keep the control disabled and show the upgrade requirement.
- 默认关闭；设置在模块及路由器持久保存。停止上网的用户意图优先，解除漫游限制不能擅自启动上网。
- Persist the default-off policy; explicit manual Stop takes priority over policy changes.
- 新脚本检测到漫游时关闭 USB 数据通路，保留短信及控制通道；恢复本地注册或允许漫游后，仅恢复原本请求开启的 USB 上网。
- Block USB data upon reported roaming while preserving SMS/control; resume only when Internet was already requested.
- 必须核对 ECM 重配置引起的飞行模式/重新枚举，避免状态未知时反复重启。不能宣称检测前零流量或保证不产生运营商费用。
- Account for radio restart/re-enumeration during ECM changes; avoid unknown-state restart loops. Do not promise zero pre-detection traffic or zero carrier charges.

## 验证要求 / Required validation

先用模拟注册状态验证本地/漫游/未知、默认关闭、勾选/取消、手动停止、设备重启及旧脚本拒绝。再做有限的配套脚本升级，核对短信记录、USB 恢复及网络出口。没有真实漫游 SIM/网络时，明确说明未做漫游联网实测。
Test home/roaming/unknown states, opt-in/out, manual Stop, restart and legacy rejection with simulation first. Then perform a bounded module-script upgrade and verify SMS retention, USB recovery and routing. Real roaming remains unverified without a suitable SIM/network.

## 官方资料 / Official references

- https://docs.openluat.com/osapi/core/mobile/
- https://docs.openluat.com/faq/2026-08-14/

## 实施记录 / Implementation record

已在授权测试路由器安装开发版 1.3.9 并升级脚本 0.2.4。模块确认支持策略；本地注册状态下勾选/取消已测试，默认恢复关闭。短信和已发送记录完整，Google HTTPS 200，加拿大出口保持。真实漫游环境尚未验证。
Installed on the authorized test router with companion script 0.2.4. Opt-in/out acknowledged under home registration, restored off. SMS history retained, Google HTTPS 200 and Canadian exit preserved. Real roaming network use remains unverified.
