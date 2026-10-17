#!/usr/bin/python3
"""Single serial owner, persistent SMS history, local authenticated-UI RPC."""
import copy
import fcntl
import json
import ipaddress
import os
import platform
import queue
import re
import select
import socket
import socketserver
import struct
import subprocess
import threading
import time
import uuid
from pathlib import Path
import dns_settings
import email_forward
import support_packages
import firmware
import signal_level
import sms_store
from network_monitor import TrafficSampler
from serial_transport import ATSerial

VERSION = '1.3.9'
APP = 'AIR780E_DEMO'
STORE = Path(os.environ.get('AIR780E_DATA_DIR', '/etc/air780e'))
RUNTIME = Path(os.environ.get('AIR780E_RUN_DIR', '/var/run/air780e'))
SOCKET = RUNTIME / 'service.sock'

def run(args, timeout=15):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('命令执行失败：' + args[0])
    return result.stdout

def cellular_dns(host, source, servers):
    """Resolve A records over the same cellular source route as the HTTPS probe."""
    ident = os.urandom(2)
    question = b''.join(bytes([len(part)]) + part.encode('ascii') for part in host.split('.')) + b'\0\0\1\0\1'
    packet = ident + struct.pack('!5H', 0x100, 1, 0, 0, 0) + question
    def skip_name(data, offset):
        while data[offset]:
            size = data[offset]
            if size & 0xc0 == 0xc0: return offset + 2
            if size & 0xc0: raise ValueError('invalid DNS name')
            offset += size + 1
        return offset + 1
    for server in servers:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(3)
                client.bind((source, 0))
                client.connect((str(ipaddress.IPv4Address(server)), 53))
                client.send(packet)
                data = client.recv(4096)
            if data[:2] != ident or len(data) < 12: continue
            flags, questions, answers, _, _ = struct.unpack('!5H', data[2:12])
            if not flags & 0x8000 or flags & 0x20f: continue
            offset = 12
            for _ in range(questions): offset = skip_name(data, offset) + 4
            for _ in range(answers):
                offset = skip_name(data, offset)
                kind, klass, ttl, size = struct.unpack('!HHIH', data[offset:offset+10])
                offset += 10
                if kind == 1 and klass == 1 and size == 4:
                    return str(ipaddress.IPv4Address(data[offset:offset+4]))
                offset += size
        except (OSError, ValueError, IndexError, struct.error):
            continue
    raise RuntimeError('4G DNS 解析失败：已绑定模块出口，请检查 SIM 数据业务或模块 DNS')

def atomic(path, value):
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False)
    os.replace(temp, path)

def discover():
    found = []
    for item in Path('/sys/class/tty').glob('ttyACM*'):
        interface = (item / 'device').resolve()
        parent = interface.parent
        try:
            if ((interface / 'bInterfaceNumber').read_text().strip() == '06' and
                (parent / 'idVendor').read_text().strip() == '19d1' and
                (parent / 'idProduct').read_text().strip() == '0001'):
                networks = list(parent.glob('*/net/*'))
                found.append({'port':'/dev/' + item.name,
                    'signature':str(parent) + ':' + (parent / 'devnum').read_text().strip(),
                    'interface':networks[0].name if len(networks) == 1 else None})
        except OSError:
            continue
    if len(found) != 1:
        raise RuntimeError('请只连接一台配套 Air780EHV 设备；当前发现 %d 台' % len(found))
    return found[0]

class Modem:
    def __init__(self):
        self.serial = None
        self.device = None
        self.buffer = b''
        self.trusted = False
        self.state = {'connected':False, 'smsReady':False, 'signalBars':None}
        self.guard = threading.RLock()

    def close(self):
        if self.serial:
            self.serial.__exit__(None, None, None)
        self.serial, self.device, self.trusted, self.buffer = None, None, False, b''
        with self.guard:
            self.state.update(connected=False, signalBars=None, phoneNumber=None)

    def ensure(self):
        device = discover()
        if self.serial and device['signature'] == self.device['signature']:
            return
        self.close()
        self.device = device
        self.serial = ATSerial(device['port'])
        self.serial.__enter__()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.receive(.2)
            if self.trusted:
                return
        self.close()
        raise RuntimeError('未收到配套固件身份；没有发送控制命令')

    def accept(self, frame):
        if frame.get('app') != APP or frame.get('protocol') != 1:
            return False
        if frame.get('event') == 'status':
            if frame.get('version') not in ('0.2.3','0.2.4'):
                raise RuntimeError('设备脚本版本不兼容，请使用原版配套固件')
            self.trusted = True
            with self.guard:
                self.state = signal_level.enrich(dict(frame, connected=True, lastSeen=time.time(),
                    port=self.device['port'], interface=self.device['interface']))
        if frame.get('event') == 'sms_received' and self.trusted:
            sms_store.save(STORE, dict(frame,receiving_number=self.state.get('phoneNumber') or (self.manual_number() if hasattr(self,'manual_number') else '')))
        if frame.get('event') == 'inbox' and self.trusted:
            for message in frame.get('messages', []):
                if isinstance(message, dict):
                    sms_store.save(STORE, dict(message,receiving_number=self.state.get('phoneNumber') or (self.manual_number() if hasattr(self,'manual_number') else '')))
        return True

    def receive(self, seconds):
        result = []
        ready, _, _ = select.select([self.serial.fd], [], [], seconds)
        if not ready:
            return result
        data = os.read(self.serial.fd, 65536)
        if not data:
            raise RuntimeError('USB 串口连接已断开')
        self.buffer += data
        if len(self.buffer) > 1048576:
            self.buffer = b''
            raise RuntimeError('设备响应超过大小限制')
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                frame = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(frame, dict) and self.accept(frame):
                result.append(frame)
        return result

    def request(self, action, **params):
        self.ensure()
        rid = str(uuid.uuid4())
        payload = (json.dumps(dict(app=APP, protocol=1, action=action, request_id=rid, **params), ensure_ascii=False) + '\n').encode()
        deadline = time.monotonic() + 3
        while payload:
            if time.monotonic() > deadline:
                raise RuntimeError('串口写入超时，操作结果未知')
            _, writable, _ = select.select([], [self.serial.fd], [], .2)
            if writable:
                try:
                    payload = payload[os.write(self.serial.fd, payload):]
                except BlockingIOError:
                    pass
        deadline = time.monotonic() + (65 if action == 'send_sms' else 8)
        while time.monotonic() < deadline:
            for frame in self.receive(.2):
                if frame.get('request_id') == rid:
                    if frame.get('event') == 'error':
                        code=frame.get('message','设备拒绝请求')
                        raise DeviceRejected({'sms_not_ready':'短信尚未就绪，请等待 SIM 注册后重试',
                            'device_busy':'模块正在处理其他操作，请稍后重试','invalid_sms':'设备拒绝了号码或短信格式',
                            'usb_initializing':'USB 正在初始化，请稍后重试','command_error':'模块处理异常'}.get(code,code))
                    return frame
        raise RuntimeError('设备未确认，结果未知；请勿重复发送')

class DeviceRejected(RuntimeError):
    pass

class Service:
    def __init__(self):
        STORE.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(STORE, 0o700)
        RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(RUNTIME, 0o700)
        self.modem = Modem()
        self.modem.manual_number=lambda:self.system_settings().get('receiving_number','')
        self.queue = queue.Queue(maxsize=32)
        self.jobs, self.guard, self.config_guard = {}, threading.RLock(), threading.RLock()
        self.last_error = ''
        self.mail_state = '邮件转发：未启用'
        self.network_check = {}
        self.stopping = threading.Event()
        policy=STORE/'network-policy.json'
        self.net_policy=json.loads(policy.read_text()) if policy.exists() else {'enabled':None,'fallback':False}
        self.health={'state':'waiting','checkedAt':None,'interval':30,'detail':'','error':''}
        self.settings_guard=threading.RLock()
        self.settings_changed=threading.Event()
        settings_path=STORE/'system-settings.json'
        self.settings={'health_interval':30,'failure_limit':3,'traffic_interval':9,'receiving_number':'','data_roaming':False,**dns_settings.DEFAULTS}
        if settings_path.exists():self.settings=self.validate_settings(json.loads(settings_path.read_text()))
        self.health['interval']=self.settings['health_interval']
        self.next_health=0
        self.traffic=TrafficSampler()
        self.traffic.latest['interval']=self.settings['traffic_interval']
        self.busy=False
        self.auto_signature=None
        self.auto_retry_at=0
        self.failure_count=0
        self.recovery_attempted=False
        self.public_ip={'address':None,'checkedAt':None,'error':''}
        with sms_store.connect(STORE) as db:
            db.execute("UPDATE outbox SET state='unknown',error='服务重启，发送结果未知；没有自动重发' WHERE state='sending'")

    @staticmethod
    def validate_settings(value):
        limits={'health_interval':(5,3600),'failure_limit':(1,20),'traffic_interval':(1,3600)}
        if not isinstance(value,dict) or not set(value)<=set(limits)|{'receiving_number','data_roaming',*dns_settings.DEFAULTS} or not set(limits)<=set(value):
            raise ValueError('系统设置参数无效')
        for key,(low,high) in limits.items():
            if type(value[key]) is not int or not low<=value[key]<=high:
                raise ValueError('系统设置参数超出范围')
        number=value.get('receiving_number','')
        if not isinstance(number,str) or (number and not re.fullmatch(r'\+[1-9][0-9]{6,14}',number)):
            raise ValueError('手机号格式须为 +国家代码和手机号码')
        roaming=value.get('data_roaming',False)
        if type(roaming) is not bool:raise ValueError('漫游设置必须为复选框值')
        return dict(value,receiving_number=number,data_roaming=roaming,**dns_settings.validate(value))

    def system_settings(self):
        with self.settings_guard:return dict(self.settings)

    def apply_dns(self,value=None):
        dns_settings.apply(value or self.system_settings(),run,STORE)

    def save_network_policy(self):
        with self.guard:atomic(STORE/'network-policy.json',self.net_policy)

    def password(self):
        path = STORE / 'smtp-secret.json'
        return json.loads(path.read_text()).get('password','') if path.exists() else ''

    def config(self):
        with self.config_guard:
            return dict(email_forward.load(STORE), passwordSaved=bool(self.password()))

    def network(self):
        try:
            info = json.loads(run(['ubus', 'call', 'network.interface.air780e', 'status'], 3))
        except Exception:
            info = {}
        with self.modem.guard:
            active=self.modem.state.get('connected') and self.modem.state.get('usbEnabled') and time.time()-self.modem.state.get('lastSeen',0)<30
        signature=(self.modem.device or {}).get('signature')
        return {'configured':bool(info), 'up':bool(info.get('up')),
            'interface':info.get('l3_device'), 'addresses':info.get('ipv4-address',[]),
            'internetVerified':bool(active and signature==self.network_check.get('signature') and info.get('up') and self.network_check.get('interface')==info.get('l3_device') and
                self.network_check.get('addresses')==info.get('ipv4-address',[]) and time.time()-self.network_check.get('time',0)<300),
            'verification':self.network_check,'health':copy.deepcopy(self.health),'traffic':copy.deepcopy(self.traffic.latest),'fallback':bool(self.net_policy.get('fallback')),'publicIP':copy.deepcopy(self.public_ip),
            'note':'取得地址不等于互联网可用；Air780E 优先级 5，网线 WAN 优先级 10'}

    def diagnostics(self):
        state = copy.deepcopy(self.modem.state)
        return {'version':VERSION, 'architecture':platform.machine(),
            'router':Path('/tmp/sysinfo/model').read_text().strip() if Path('/tmp/sysinfo/model').exists() else 'OpenWrt',
            'glFirmware':Path('/etc/glversion').read_text().strip() if Path('/etc/glversion').exists() else '',
            'kernel':platform.release(), 'connected':state.get('connected'), 'script':state.get('version'),
            'signalBars':state.get('signalBars'), 'usbEnabled':state.get('usbEnabled'),
            'network':self.network(), 'containsSMSOrCredentials':False}

    def enqueue(self, action, params):
        ident = params.get('client_id') or str(uuid.uuid4())
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', ident):
            raise ValueError('请求标识无效')
        with self.guard:
            if ident in self.jobs:
                return {'job':ident}
            if len(self.jobs) >= 200:
                finished = [key for key,value in self.jobs.items() if value['state'] in ('done','failed')]
                for key in finished[:100]:
                    self.jobs.pop(key, None)
            if action=='install_support':
                pending=next((v for v in self.jobs.values() if v['action']==action and v['state'] in ('queued','running')),None)
                if pending:return {'job':pending['id']}
                self.jobs[ident]={'id':ident,'action':action,'state':'queued','submittedAt':time.time(),'completedAt':None}
                threading.Thread(target=self.support_job,args=(ident,),daemon=True).start()
                return {'job':ident}
            if self.queue.full():
                raise RuntimeError('任务队列已满，请稍后重试')
            if action == 'send_sms':
                with sms_store.connect(STORE) as db:
                    existing = db.execute('SELECT * FROM outbox WHERE id=?',(ident,)).fetchone()
                    if existing:
                        return {'job':ident, 'previous':dict(existing)}
                sms_store.sending(STORE,ident,params['number'],params['message'])
            self.jobs[ident] = {'id':ident,'action':action,'state':'queued','submittedAt':time.time(),'completedAt':None}
            self.queue.put_nowait((ident,action,params))
        return {'job':ident}

    def support_job(self, ident):
        # Package maintenance does not need the modem's serial worker.
        with self.guard:self.jobs[ident]['state']='running'
        try:
            result=self.execute('install_support',{},ident)
            with self.guard:self.jobs[ident].update(state='done',result=result,completedAt=time.time())
        except Exception as error:
            with self.guard:self.jobs[ident].update(state='failed',error=str(error),completedAt=time.time())

    def rpc(self, value):
        action = value.get('action', 'snapshot')
        if action == 'system_settings':return self.system_settings()
        if action == 'system_settings_save':
            validated=self.validate_settings(value.get('settings'))
            with self.modem.guard:
                capable=self.modem.state.get('roamingControlSupported') is True and self.modem.state.get('connected') is True
            roaming_change=validated['data_roaming']!=self.system_settings()['data_roaming']
            if roaming_change and not capable:raise ValueError('当前模块脚本不支持漫游控制，请升级配套脚本')
            with self.guard:
                if any(j['action']=='set_roaming' and j['state'] in ('queued','running') for j in self.jobs.values()):raise ValueError('漫游设置正在应用，请等待任务完成')
            wanted_roaming=validated['data_roaming']
            if roaming_change:validated['data_roaming']=self.system_settings()['data_roaming']
            with self.settings_guard:
                previous=self.system_settings()
                changed=any(validated[k]!=previous[k] for k in dns_settings.DEFAULTS)
                if changed:self.apply_dns(validated)
                try:atomic(STORE/'system-settings.json',validated)
                except Exception:
                    if changed:self.apply_dns(previous)
                    raise
                self.settings=validated
                self.traffic.latest['interval']=validated['traffic_interval']
                self.health['interval']=validated['health_interval']
                self.next_health=0
                self.settings_changed.set()
            if roaming_change:
                self.enqueue('set_roaming',{'enabled':wanted_roaming})
                return dict(self.system_settings(),roamingPending=True)
            return self.system_settings()
        if action == 'snapshot':
            with self.modem.guard:
                state = copy.deepcopy(self.modem.state)
            state['manualPhoneNumber']=self.system_settings().get('receiving_number','')
            state['stale'] = time.time() - state.get('lastSeen',0) > 30
            with self.guard:
                jobs = copy.deepcopy(list(self.jobs.values()))[-30:]
            return {'settings':self.system_settings(),'version':VERSION,'status':state,'network':self.network(),'error':self.last_error,
                'messages':sms_store.rows(STORE,value.get('kind','inbox')),'jobs':jobs,'mailStatus':self.mail_state}
        if action == 'traffic':
            return copy.deepcopy(self.traffic.latest)
        if action == 'diagnostics':
            return self.diagnostics()
        if action == 'email_config':
            return self.config()
        if action == 'email_history':
            with self.config_guard:
                return email_forward.history(STORE)
        if action in ('delete_sms','restore_sms'):
            ids = value.get('ids')
            if not isinstance(ids,list) or not 1 <= len(ids) <= 500 or any(not isinstance(x,str) for x in ids):
                raise ValueError('请选择有效短信')
            sms_store.archive(STORE,ids,action=='restore_sms',value.get('kind','inbox'))
            return {'changed':len(ids)}
        if action == 'clear_trash':
            if value.get('confirmation') != '永久清空已删除短信':
                raise ValueError('需要明确确认永久删除')
            return {'removed':sms_store.clear_trash(STORE)}
        if action == 'email_save':
            config = value.get('config', {})
            if not isinstance(config,dict):
                raise ValueError('邮件配置无效')
            password = value.get('password','')
            if not isinstance(password,str) or len(password)>4096 or '\x00' in password:
                raise ValueError('密码无效')
            with self.config_guard:
                validated = email_forward.validate(config)
                if validated['enabled'] and not (password or self.password()):
                    raise ValueError('请填写 SMTP 密码或授权码')
                if password:
                    atomic(STORE / 'smtp-secret.json', {'password':password})
                email_forward.save(STORE,validated)
            return self.config()
        if action == 'send_sms':
            if value.get('confirmed') is not True:
                raise ValueError('请确认短信发送及可能产生的费用')
            number = sms_store.normalize_number(str(value.get('number','')))
            message = value.get('message')
            if not isinstance(message,str) or not 1<=len(message)<=500 or any(ord(c)>65535 or c=='\x00' for c in message):
                raise ValueError('短信须为 1–500 字符；不支持 emoji 等非 BMP 字符')
            value = dict(value, number=number, message=message)
        if action == 'install_firmware':
            if value.get('model')!='Air780EHV_A11' or value.get('confirmation')!='覆盖固件':
                raise ValueError('请核对 Air780EHV_A11 型号，并明确确认覆盖固件')
        if action in ('send_sms','start','stop','activate_network','sync','email_test','verify_network','prepare_firmware','install_firmware','install_support'):
            if action in ('start','stop'):
                self.net_policy['enabled']=action=='start'
                if action=='start':
                    self.net_policy['fallback']=False
                    self.failure_count=0;self.recovery_attempted=False
                self.save_network_policy()
                if action=='stop':self.health.update(state='disabled',detail='手动停止，自动恢复已暂停')
            return self.enqueue(action,value)
        if action == 'firmware_capabilities':
            supported=platform.machine() in ('aarch64','arm64')
            return {'supported':supported,'reason':'此 ARM64 路由器支持固件资源准备和安装/修复。烧录会覆盖模块核心与脚本，不自动备份原固件；请先核对型号并同步短信。' if supported else '此路由器架构暂无经验证的烧录工具，请使用原版 Mac 应用安装/修复。其他功能不受影响。',
                'model':'Air780EHV_A11','core':'V2052','script':'0.2.4','cachePath':str(firmware.CACHE),'cacheCleanup':'reboot','resourcesReady':(firmware.CACHE/'ready.json').exists()}
        raise ValueError('不支持的操作')

    def activate(self):
        device = discover()
        interface = device['interface']
        if not interface or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,32}',interface):
            raise RuntimeError('未安全识别 USB ECM 网卡')
        old=subprocess.run(['uci','-q','get','network.air780e_dev.device'],capture_output=True,text=True)
        if old.stdout.strip()==interface:
            subprocess.run(['ifdown','air780e_dev'],capture_output=True)
            run(['uci','delete','network.air780e_dev'])
        # Dedicated DHCP interface, lower metric means primary upstream.
        for assignment in ['network.air780e=interface','network.air780e.proto=dhcp',
                'network.air780e.device='+interface,'network.air780e.defaultroute=1','network.air780e.metric=5',
                'network.air780e.peerdns=0','network.air780e.dns_metric=5','network.air780e.delegate=0']:
            run(['uci','set',assignment])
        if subprocess.run(['uci','-q','get','network.wan'],capture_output=True,text=True).stdout.strip()=='interface':
            run(['uci','set','network.wan.metric=10'])
            run(['uci','set','network.wan.dns_metric=10'])
        run(['uci','commit','network'])
        self.apply_dns()
        # Join the existing WAN firewall zone so LAN clients receive NAT too.
        for index in range(32):
            zone='firewall.@zone['+str(index)+']'
            name=subprocess.run(['uci','-q','get',zone+'.name'],capture_output=True,text=True)
            if name.stdout.strip()!='wan':continue
            networks=subprocess.run(['uci','-q','get',zone+'.network'],capture_output=True,text=True).stdout.split()
            if 'air780e' not in networks:
                run(['uci','add_list',zone+'.network=air780e'])
                run(['uci','commit','firewall'])
                # Some vendor include scripts return nonzero although fw3 applied.
                subprocess.run(['/etc/init.d/firewall','reload'],capture_output=True,timeout=30)
            break
        else:
            raise RuntimeError('未找到 WAN 防火墙区域，请配置 LAN 转发与 NAT')
        run(['ubus','call','network','reload'])
        run(['ifup','air780e'])
        if 'kmwanOriginal' in self.net_policy:
            run(['uci','set','kmwan.air780e.disabled='+self.net_policy.pop('kmwanOriginal')])
            run(['uci','commit','kmwan'])
            subprocess.run(['/etc/init.d/kmwan','restart'],capture_output=True,timeout=15)
        return 'USB 网卡已激活：Air780E 优先级 5，网线 WAN 优先级 10'

    def wait_network(self, timeout=45):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                info=json.loads(run(['ubus','call','network.interface.air780e','status']))
                if info.get('up') and info.get('ipv4-address'):
                    return info
            except (RuntimeError, ValueError):
                pass
            time.sleep(.5)
        raise RuntimeError('USB 网卡 DHCP 等待超时；已保留网线 WAN 备用出口')

    def execute(self, action, params, ident):
        def progress(value):
            with self.guard:
                self.jobs[ident]['progress']=value
                if action=='install_firmware':
                    stages=[('正在下载',10),('正在验证官方',35),('正在编译',45),('资源已校验',60),('正在写入',70),('固件写入完成',95)]
                    percent=next((n for text,n in stages if value.startswith(text)),5)
                    self.jobs[ident]['percent']=max(self.jobs[ident].get('percent',0),percent)
        if action == 'install_support':
            return support_packages.install(progress)
        if action == 'health_check':
            return self.check_health(ident)
        if action == 'prepare_firmware':
            firmware.prepare(progress,core=True)
            return '官方核心固件、烧录工具与独立运行库已校验；工具版本及固件结构检查通过，没有改写模块'
        if action == 'install_firmware':
            try:
                self.modem.request('inbox')
            except Exception:
                # Repair must also work for missing/incompatible application firmware.
                pass
            firmware.install(params['model'],params['confirmation'],progress,self.modem.close)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                try:
                    verified=self.modem.request('status')
                    if verified.get('version')!='0.2.4' or verified.get('roamingControlSupported') is not True:raise RuntimeError('新脚本能力尚未验证')
                    with self.guard:self.jobs[ident]['percent']=100
                    return '固件写入完成，配套设备协议已验证；请按需点击启动上网'
                except Exception:
                    self.modem.close();time.sleep(1)
            raise RuntimeError('写入已完成，但设备协议尚未验证，请检查供电并重插设备')
        if action == 'email_test':
            with self.config_guard:
                return email_forward.test_connection(STORE,self.password())
        if action == 'activate_network':
            return self.activate()
        if action == 'verify_network':
            return self.verify_network()
        if action == 'set_roaming':
            state=self.modem.request('status')
            if state.get('roamingControlSupported') is not True:raise DeviceRejected('当前模块脚本不支持漫游控制，请升级配套脚本')
            response=self.modem.request('set_roaming',enabled=params['enabled'])
            if response.get('dataRoamingAllowed') is not params['enabled']:raise RuntimeError('模块未确认漫游设置')
            with self.modem.guard:self.modem.state['dataRoamingAllowed']=params['enabled']
            with self.settings_guard:
                updated=dict(self.settings,data_roaming=params['enabled'])
                atomic(STORE/'system-settings.json',updated);self.settings=updated
            return '漫游 USB 上网策略已由模块确认并保存'
        if action == 'sync':
            self.modem.request('status')
            self.modem.request('inbox')
            return '状态与收件箱已同步'
        if action == 'send_sms':
            try:
                try:
                    self.modem.ensure()
                except Exception as error:
                    raise DeviceRejected('未发送：'+str(error)) from None
                if not self.modem.state.get('smsReady'):
                    raise DeviceRejected('短信尚未就绪，本次未发送')
                response = self.modem.request(action,number=params['number'],message=params['message'])
                state = 'accepted' if response.get('success') else 'failed'
                detail = '' if state=='accepted' else response.get('detail','设备返回发送失败')
                sms_store.outcome(STORE,ident,state,detail)
                return '短信中心已接受，不代表收件人已收到' if state=='accepted' else '发送失败：'+detail
            except Exception as error:
                sms_store.outcome(STORE,ident,'failed' if isinstance(error,DeviceRejected) else 'unknown',str(error))
                raise
        target = action == 'start'
        self.network_check = {}
        deadline = time.monotonic() + 45
        commanded = False
        while time.monotonic() < deadline:
            try:
                result = self.modem.request('status')
                if target and result.get('roamingControlSupported') and result.get('roamingBlocked') and result.get('usbRequested'):
                    return '漫游数据已暂停，短信功能保持可用'
                if result.get('usbEnabled') == target and (target or result.get('usbRequested') is not True):
                    if target:
                        self.activate()
                        self.wait_network()
                        self.auto_signature=(self.modem.device or {}).get('signature')
                    else:
                        subprocess.run(['ifdown', 'air780e'], capture_output=True)
                    if not params.get('automatic'):
                        self.net_policy.update(enabled=target,fallback=False)
                        self.save_network_policy()
                        self.next_health=0
                    return '模块上网已开启；Air780E 为第一出口' if target else '模块上网已关闭；已回退网线 WAN'
                if not commanded:
                    self.modem.request('inbox')
                    # Once submitted, USB may disappear before the ACK arrives.
                    # Reconcile the final state; never retry a state-changing command blindly.
                    commanded = True
                    self.modem.request(action)
                    self.modem.close()
            except DeviceRejected:
                raise
            except (OSError, RuntimeError):
                self.modem.close()
            time.sleep(1)
        raise RuntimeError('USB 重新连接后未达到目标状态，请检查供电和模块连接')

    def verify_network(self, wait_timeout=45, probe_timeout=20, interface_name='air780e'):
        cellular=interface_name=='air780e'
        info=self.wait_network(wait_timeout) if cellular else json.loads(run(['ubus','call','network.interface.wan','status'],3))
        addresses=info.get('ipv4-address',[])
        if not info.get('up') or not addresses:
            raise RuntimeError('USB 网卡尚未取得地址，请先激活网卡')
        interface=info.get('l3_device')
        device=discover() if cellular else {'interface':interface,'signature':'wan'}
        if not interface or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,32}',interface):raise RuntimeError('网络接口不可用')
        if interface!=device['interface']:
            raise RuntimeError('网络接口与 USB 设备不匹配，已拒绝验证')
        source=str(ipaddress.IPv4Address(addresses[0]['address']))
        subnet=str(ipaddress.IPv4Network(source+'/'+str(addresses[0]['mask']),strict=False))
        routes=info.get('inactive',{}).get('route',[])+info.get('route',[])
        gateway=next((str(ipaddress.IPv4Address(r['nexthop'])) for r in routes if r.get('mask')==0 and r.get('nexthop')),None)
        if not gateway:
            raise RuntimeError('DHCP 未提供网关')
        # Use a dedicated source rule before GL/Tailscale routing; remove in finally.
        # A higher priority number can silently use the existing VPN instead.
        if subprocess.run(['ip','route','show','table','1781'],capture_output=True,text=True).stdout.strip():
            raise RuntimeError('开发验证路由表已被使用，拒绝覆盖')
        rule=False
        if cellular:self.network_check={}
        try:
            run(['ip','route','add',subnet,'dev',interface,'src',source,'table','1781'])
            run(['ip','route','add','default','via',gateway,'dev',interface,'table','1781'])
            run(['ip','rule','add','pref','0','from',source+'/32','table','1781'])
            rule=True
            route=run(['ip','route','get','1.1.1.1','from',source])
            if 'dev '+interface not in route or 'table 1781' not in route:
                raise RuntimeError('请求未安全绑定 USB 出口，取消验证')
            servers=list(dns_settings.validate(self.system_settings()).values()) if cellular else info.get('dns-server',[])+info.get('inactive',{}).get('dns-server',[])
            passed=False
            for host,path,marker in [('www.apple.com','/library/test/success.html','Success'),('www.cloudflare.com','/cdn-cgi/trace','ip=')]:
                try:
                    resolved=cellular_dns(host,source,servers or (list(dns_settings.DEFAULTS.values()) if cellular else ['1.1.1.1','8.8.8.8']))
                    result=subprocess.run(['curl','-4','--resolve',host+':443:'+resolved,'--noproxy','*','--interface',source,'--connect-timeout','5','--max-time',str(probe_timeout),
                        '-fsS','https://'+host+path],capture_output=True,text=True,timeout=probe_timeout+5)
                    if result.returncode==0 and marker in result.stdout:
                        passed=True;break
                    failure='curl '+str(result.returncode)
                except Exception as error:
                    failure=str(error)
            if not passed:
                raise RuntimeError('USB DHCP 正常，但绑定 4G 的 HTTPS 验证失败；请检查 SIM 数据业务、模块转发和路由策略（'+failure+'）')
            if not cellular:return 'WAN 外网验证通过'
            self.network_check={'time':time.time(),'interface':interface,'addresses':addresses,'signature':device['signature'],'verified':True}
            return '4G 互联网验证成功：HTTPS 请求已绑定 '+interface+'（'+source+'），Air780E 优先出口'
        finally:
            if rule:
                subprocess.run(['ip','rule','del','pref','0','from',source+'/32','table','1781'],capture_output=True)
            subprocess.run(['ip','route','flush','table','1781'],capture_output=True)

    def use_wan(self):
        # Keep ECM available for later cellular checks, but withdraw its preferred route/DNS.
        for assignment in ['network.air780e.metric=50','network.air780e.dns_metric=50','network.air780e.peerdns=0']:
            run(['uci','set',assignment])
        run(['uci','commit','network'])
        original=subprocess.run(['uci','-q','get','kmwan.air780e.disabled'],capture_output=True,text=True).stdout.strip()
        if original:
            self.net_policy.setdefault('kmwanOriginal',original)
            run(['uci','set','kmwan.air780e.disabled=1']);run(['uci','commit','kmwan'])
            subprocess.run(['/etc/init.d/kmwan','restart'],capture_output=True,timeout=15)
        self.net_policy['fallback']=True
        self.save_network_policy()
        run(['ifdown','air780e']);run(['ifup','air780e'])

    def auto_connect(self):
        with self.modem.guard:state=copy.deepcopy(self.modem.state)
        if state.get('roamingControlSupported') is True and state.get('dataRoamingAllowed') is not self.system_settings()['data_roaming']:
            self.enqueue('set_roaming',{'enabled':self.system_settings()['data_roaming']});return
        if state.get('roamingBlocked') is True:return
        if self.net_policy.get('enabled') is False or self.net_policy.get('fallback'):return
        if time.monotonic()<self.auto_retry_at:return
        with self.guard:
            if any(j['action']=='start' and j['state'] in ('queued','running') for j in self.jobs.values()):return
        try:
            device=discover()
            if device['signature']==self.auto_signature:return
            # Request verifies the exact companion app/protocol before any control.
            self.modem.request('status')
            self.auto_retry_at=time.monotonic()+60
            self.net_policy['enabled']=True
            self.save_network_policy()
            self.enqueue('start',{'automatic':True})
        except Exception:
            self.auto_retry_at=time.monotonic()+10

    def check_health(self, ident):
        def paused():
            stopped=self.net_policy.get('enabled') is False
            if stopped:self.health.update(state='disabled',detail='手动停止，自动恢复已暂停')
            return stopped
        def failed(error):
            self.failure_count+=1
            self.health.update(state='failed',checkedAt=time.time(),detail=str(error),error=str(error),failures=self.failure_count)
        def healthy(detail):
            self.failure_count=0;self.recovery_attempted=False
            self.health.update(state='healthy',checkedAt=time.time(),error='',detail=detail,failures=0)
            return detail
        if paused():
            self.health.update(state='disabled',detail='手动停止，自动恢复已暂停');return self.health['detail']
        if self.net_policy.get('enabled') is None:return '等待自动识别 USB 设备'
        self.health.update(state='checking',detail='正在检测 SIM 与 4G 外网连接')
        try:
            state=self.modem.request('status')
            if state and state.get('roamingControlSupported') is True and state.get('roamingBlocked') is True:
                self.health.update(state='disabled',checkedAt=time.time(),detail='漫游数据已暂停，短信功能保持可用')
                return self.health['detail']
            self.verify_network(wait_timeout=3,probe_timeout=8)
            if paused():return '手动停止，自动恢复已暂停'
            return healthy('SIM 蜂窝外网正常')
        except Exception as error:failed(error)
        if paused():return '手动停止，自动恢复已暂停'
        if self.net_policy.get('fallback'):
            self.health.update(state='wan',detail='4G 仍不可用，继续使用 WAN');return self.health['detail']
        if not self.recovery_attempted:
            self.recovery_attempted=True
            self.health.update(state='restarting',detail='4G 检测失败，正在重启上网')
            try:
                self.execute('stop',{'automatic':True},ident)
                if paused():return '手动停止，自动恢复已暂停'
                self.execute('start',{'automatic':True},ident)
                self.verify_network(wait_timeout=3,probe_timeout=8)
                if paused():return '手动停止，自动恢复已暂停'
                return healthy('重启后 4G 外网已恢复')
            except Exception as error:failed(error)
        if paused():return '手动停止，自动恢复已暂停'
        if self.failure_count<self.system_settings()['failure_limit']:
            self.health.update(state='failed',detail='等待下一轮检测，连续失败次数：'+str(self.failure_count));return self.health['detail']
        try:
            self.verify_network(wait_timeout=3,probe_timeout=8,interface_name='wan')
        except Exception as error:
            self.health.update(state='failed',detail='WAN 外网验证失败，未切换出口',wanError=str(error));return self.health['detail']
        if paused():return '手动停止，自动恢复已暂停'
        self.use_wan()
        self.health.update(state='wan',detail='4G 连续失败 '+str(self.failure_count)+' 次，WAN 验证通过，已切换 WAN')
        return self.health['detail']

    def public_ip_worker(self):
        while not self.stopping.is_set():
            try:
                result=run(['curl','-4','--noproxy','*','--connect-timeout','5','--max-time','10','-fsS','https://www.cloudflare.com/cdn-cgi/trace'],15)
                value=next(line[3:].strip() for line in result.splitlines() if line.startswith('ip='))
                address=ipaddress.ip_address(value)
                if not address.is_global:raise ValueError('Invalid public IP')
                self.public_ip={'address':str(address),'checkedAt':time.time(),'error':''}
            except Exception:
                self.public_ip={'address':None,'checkedAt':time.time(),'error':'公网 IP 获取失败'}
            self.stopping.wait(60)

    def traffic_worker(self):
        while not self.stopping.is_set():
            try:
                interface=(discover() or {}).get('interface')
                self.traffic.sample(interface)
                self.traffic.latest['interval']=self.system_settings()['traffic_interval']
            except Exception:
                self.traffic.latest={'available':False,'sampledAt':time.time(),'interval':self.system_settings()['traffic_interval']}
            self.settings_changed.wait(self.system_settings()['traffic_interval'])
            self.settings_changed.clear()

    def worker(self):
        last_sync = 0
        while not self.stopping.is_set():
            try:
                ident,action,params = self.queue.get(timeout=.2)
            except queue.Empty:
                self.auto_connect()
                if not self.queue.empty():continue
                if time.monotonic()>=self.next_health and self.net_policy.get('enabled') is not False:
                    self.next_health=time.monotonic()+self.system_settings()['health_interval']
                    self.enqueue('health_check',{})
                    continue
                try:
                    self.modem.ensure()
                    self.modem.receive(.2)
                    if time.monotonic()-last_sync>15:
                        self.modem.request('status')
                        self.modem.request('inbox')
                        last_sync=time.monotonic()
                    self.last_error=''
                except Exception as error:
                    self.last_error=str(error)
                    self.modem.close()
                    self.stopping.wait(2)
                continue
            with self.guard: self.jobs[ident]['state']='running'
            self.busy=True
            try:
                result=self.execute(action,params,ident)
                with self.guard: self.jobs[ident].update(state='done',result=result,completedAt=time.time())
            except Exception as error:
                with self.guard: self.jobs[ident].update(state='failed',error=str(error),completedAt=time.time())
                self.modem.close()
            finally:
                self.busy=False
                self.queue.task_done()

    def mail_worker(self):
        while not self.stopping.wait(15):
            try:
                with self.config_guard:
                    self.mail_state=email_forward.forward(STORE,self.password())
            except Exception:
                self.mail_state='邮件连接或认证失败；请检查设置，系统将按退避规则处理'

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            raw=self.rfile.readline(65537)
            if len(raw)>65536: raise ValueError('请求过大')
            value=json.loads(raw)
            if not isinstance(value,dict): raise ValueError('请求无效')
            response={'ok':True,'data':self.server.service.rpc(value)}
        except Exception as error:
            response={'ok':False,'error':str(error)}
        self.wfile.write((json.dumps(response,ensure_ascii=False)+'\n').encode())

class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True

def main():
    os.umask(0o077)
    service=Service()
    # Share lock path with the original 0.1.0 CLI; never allow two serial owners.
    lock=(RUNTIME/'device.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    SOCKET.unlink(missing_ok=True)
    with Server(str(SOCKET),Handler) as server:
        os.chmod(SOCKET,0o600)
        try:
            service.apply_dns()
            atomic(STORE/'system-settings.json',service.system_settings())
        except Exception as error:service.last_error=str(error)
        server.service=service
        threading.Thread(target=service.worker,daemon=True).start()
        threading.Thread(target=service.mail_worker,daemon=True).start()
        threading.Thread(target=service.traffic_worker,daemon=True).start()
        threading.Thread(target=service.public_ip_worker,daemon=True).start()
        try: server.serve_forever()
        finally: service.stopping.set(); service.modem.close()

if __name__=='__main__': main()
