"""Install the fixed OpenWrt Unicode codec dependency through signed opkg feeds."""
import subprocess
import sys

PACKAGE = 'python3-codecs'

def command(args, timeout):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError('支持包安装超时，请检查网络后重试') from None

def install(progress):
    status = command(['opkg', 'status', PACKAGE], 15)
    installed = status.returncode == 0 and 'Status: install ok installed' in status.stdout
    # GL firmware may use "install user installed" for manually installed packages.
    installed = installed or (status.returncode == 0 and any(
        line.startswith('Status: ') and line.split()[-1:] == ['installed']
        for line in status.stdout.splitlines()))
    if not installed:
        progress('正在安装 python3-codecs Unicode 支持包')
        result = command(['opkg', 'install', PACKAGE], 180)
        if result.returncode:
            progress('正在刷新软件源并重试安装支持包')
            # Vendor feeds can fail independently; the final install is authoritative.
            command(['opkg', 'update'], 120)
            result = command(['opkg', 'install', PACKAGE], 180)
        if result.returncode:
            raise RuntimeError('支持包安装失败，请检查软件源、网络或 opkg 是否被占用')
    progress('正在验证 Unicode 编解码支持')
    result = command([sys.executable, '-c',
        "import codecs; [codecs.lookup(name) for name in ('unicode_escape','raw_unicode_escape','idna','utf-16','utf-32')]; assert '中文'.encode('unicode_escape').decode('unicode_escape') == '中文'"], 15)
    if result.returncode:
        raise RuntimeError('支持包已安装，但 Unicode 验证失败，请检查 Python 组件版本')
    return 'python3-codecs 已安装，Unicode 编解码验证通过'
