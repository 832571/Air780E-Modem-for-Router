"""Persistent plugin DNS policy; never accept hostnames or shell fragments."""
import ipaddress
import subprocess
from pathlib import Path

DEFAULTS={'dns_primary':'1.1.1.1','dns_secondary':'9.9.9.9'}

def validate(value):
    result={}
    for key,default in DEFAULTS.items():
        raw=value.get(key,default)
        if not isinstance(raw,str):raise ValueError('DNS 必须是有效的 IPv4 地址')
        try:address=ipaddress.IPv4Address(raw)
        except ValueError:raise ValueError('DNS 必须是有效的 IPv4 地址') from None
        if address.is_unspecified or address.is_multicast or address.is_loopback or str(address)=='255.255.255.255':
            raise ValueError('DNS 必须是有效的 IPv4 地址')
        result[key]=str(address)
    return result

def apply(value,run,store,config_root=Path('/etc/config')):
    servers=list(dict.fromkeys(validate(value).values()))
    def get(key):
        return subprocess.run(['uci','-q','get',key],capture_output=True,text=True,timeout=5).stdout.strip()
    cellular=get('network.air780e')=='interface'
    if get('dhcp.@dnsmasq[0].noresolv')=='1' and get('dhcp.@dnsmasq[0].server').split()==servers and (not cellular or (get('network.air780e.peerdns')=='0' and get('network.air780e.dns').split()==servers)):
        return
    backups={name:(config_root/name).read_bytes() for name in ('dhcp','network')}
    folder=store/'dns-backup';folder.mkdir(exist_ok=True,mode=0o700)
    for name,data in backups.items():
        path=folder/name
        if not path.exists():path.write_bytes(data);path.chmod(0o600)
    try:
        run(['uci','set','dhcp.@dnsmasq[0].noresolv=1'])
        subprocess.run(['uci','-q','delete','dhcp.@dnsmasq[0].server'],capture_output=True,timeout=5)
        for address in servers:run(['uci','add_list','dhcp.@dnsmasq[0].server='+address])
        if cellular:
            run(['uci','set','network.air780e.peerdns=0'])
            subprocess.run(['uci','-q','delete','network.air780e.dns'],capture_output=True,timeout=5)
            for address in servers:run(['uci','add_list','network.air780e.dns='+address])
            run(['uci','commit','network'])
        run(['uci','commit','dhcp'])
        run(['/etc/init.d/dnsmasq','restart'])
    except Exception:
        for name,data in backups.items():
            subprocess.run(['uci','-q','revert',name],capture_output=True,timeout=5)
            (config_root/name).write_bytes(data)
        subprocess.run(['/etc/init.d/dnsmasq','restart'],capture_output=True,timeout=15)
        raise RuntimeError('DNS 应用失败，已恢复原配置') from None
