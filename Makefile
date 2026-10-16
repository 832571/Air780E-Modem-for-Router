include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-air780e
PKG_VERSION:=1.3.6
PKG_RELEASE:=1
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-air780e
  SECTION:=net
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=Air780E Modem for Router V1.3
  DEPENDS:=+lua +luci-base +luci-compat +luci-lib-nixio +kmod-usb-acm +kmod-usb-net-cdc-ether +python3-light +python3-codecs +python3-sqlite3 +python3-email +python3-openssl +python3-urllib +python3-lzma +ca-bundle +curl +ip-full +zstd
endef

define Build/Compile
endef

define Package/luci-app-air780e/install
	$(CP) ./files/* $(1)/
endef

define Package/luci-app-air780e/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
rm -f /tmp/luci-indexcache*
/etc/init.d/air780e enable
/etc/init.d/air780e restart
exit 0
endef

define Package/luci-app-air780e/prerm
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
/etc/init.d/air780e stop
/etc/init.d/air780e disable
exit 0
endef

$(eval $(call BuildPackage,luci-app-air780e))
