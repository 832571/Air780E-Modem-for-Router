#!/usr/bin/env python3
import gzip,hashlib,io,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
dist=root/'dist'
package=dist/'luci-app-air780e_1.3.9_all.ipk'
with tarfile.open(package,'r:gz') as outer:
    raw=outer.extractfile('./control.tar.gz').read()
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as inner:
    control=inner.extractfile('./control').read().decode().rstrip()
index=control+'\nFilename: '+package.name+'\nSize: '+str(package.stat().st_size)+'\nSHA256sum: '+hashlib.sha256(package.read_bytes()).hexdigest()+'\n\n'
(dist/'Packages').write_text(index)
(dist/'Packages.gz').write_bytes(gzip.compress(index.encode(),mtime=0))
shutil.copyfile(root/'feed.pub',dist/'feed.pub')
shutil.copyfile(root/'scripts/install-feed.sh',dist/'install-feed.sh')
print(dist)
