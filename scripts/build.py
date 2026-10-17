#!/usr/bin/env python3
"""Build an architecture-independent opkg package from the reviewed file tree."""
import hashlib
import io
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.3.9'
CONTROL = f'''Package: luci-app-air780e
Version: {VERSION}
Architecture: all
Maintainer: 点击网络
Section: net
Priority: optional
Depends: lua, luci-base, luci-compat, luci-lib-nixio, kmod-usb-acm, kmod-usb-net-cdc-ether, python3-light, python3-codecs, python3-sqlite3, python3-email, python3-openssl, python3-urllib, python3-lzma, ca-bundle, curl, ip-full, zstd
Description: Air780E Modem for Router V1.3 - USB ECM, SMS and SMTP forwarding (MIT)
'''

def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, content, mode in entries:
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.uid, item.gid, item.mtime = len(content or b''), mode, 0, 0, int(time.time())
            if content is None:
                item.type = tarfile.DIRTYPE
                tar.addfile(item)
            else:
                tar.addfile(item, io.BytesIO(content))
    return output.getvalue()

files = []
for path in sorted((ROOT / 'files').rglob('*')):
    relative = path.relative_to(ROOT / 'files').as_posix()
    if path.is_dir():
        files.append(('./' + relative, None, 0o755))
    elif path.is_file():
        if '__pycache__' in path.parts or path.suffix=='.pyc':
            continue
        files.append(('./' + relative, path.read_bytes(), 0o755 if relative in ('usr/bin/air780e','etc/init.d/air780e') else 0o644))
postinst = b'''#!/bin/sh
if [ -z "$IPKG_INSTROOT" ]; then
    rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.lua /tmp/luci-indexcache.*.json
    rm -f /tmp/luci-modulecache/*air780e*
    rm -f /tmp/luci-modulecache/6C7563692E636F6E74726F6C6C65722E61697237383065 /tmp/luci-modulecache/636C69656E74
    /etc/init.d/air780e enable
    /etc/init.d/air780e stop >/dev/null 2>&1
    /etc/init.d/air780e start
fi
exit 0
'''
prerm=b'''#!/bin/sh
if [ -z "$IPKG_INSTROOT" ]; then
    /etc/init.d/air780e stop
    /etc/init.d/air780e disable
fi
exit 0
'''
control = archive([('./control', CONTROL.encode(), 0o644), ('./postinst', postinst, 0o755), ('./prerm',prerm,0o755)])
data = archive(files)
package = archive([('./debian-binary', b'2.0\n', 0o644), ('./control.tar.gz', control, 0o644), ('./data.tar.gz', data, 0o644)])
dist = ROOT / 'dist'
dist.mkdir(exist_ok=True)
path = dist / f'luci-app-air780e_{VERSION}_all.ipk'
path.write_bytes(package)
(dist / 'SHA256SUMS').write_text(hashlib.sha256(package).hexdigest() + '  ' + path.name + '\n')
print(path)
