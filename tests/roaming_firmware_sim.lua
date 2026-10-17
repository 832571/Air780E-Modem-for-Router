package.path='/usr/lib/air780e/firmware/lua/?.lua;'..package.path
local tasks,timers,subscriptions={}, {}, {}
local sys={taskInit=function(fn)tasks[#tasks+1]=coroutine.create(fn)end,wait=function(ms)if ms~=700 then coroutine.yield() end end,subscribe=function(k,fn)subscriptions[k]=fn end,timerLoopStart=function(fn)timers[#timers+1]=fn end,run=function()end}
package.preload.sys=function()return sys end
package.preload.sysplus=function()return {} end
local storage={air780e_demo_usb=true};local reg=1;local ethernet=false;local receive;local command;local last
fskv={init=function()end,get=function(k)return storage[k]end,set=function(k,v)storage[k]=v;return true end}
mobile={CONF_USB_ETHERNET=1,status=function()return reg end,config=function(_,v)ethernet=v==7;return true end,flymode=function()end,rsrp=function()return -90 end,simPin=function()return true end,number=function()return '' end}
pm={USB=1,power=function()end}
uart={VUART_0=0,setup=function()end,on=function(_,_,fn)receive=fn end,write=function()end,read=function()return 'command\n'end}
json={encode=function(v)last=v;return '{}'end,decode=function()return command end}
dofile('/usr/lib/air780e/firmware/lua/main.lua')
local function tick(n)for j=1,n do for _,c in ipairs(tasks)do if coroutine.status(c)~='dead' then local ok,err=coroutine.resume(c);assert(ok,err)end end end end
local function status()timers[1]();assert(last.event=='status');return last end
local function send(action,enabled)command={app='AIR780E_DEMO',protocol=1,action=action,enabled=enabled,request_id='test'};receive(0,8)end
assert(ethernet==false)
tick(3);subscriptions.SMS_READY();assert(status().roamingControlSupported and ethernet)
reg=5;tick(1);assert(not ethernet and status().roamingBlocked and last.smsReady)
send('set_roaming',true);assert(last.event=='roaming_policy' and storage.air780e_demo_roaming==true)
tick(1);assert(ethernet and status().dataRoamingAllowed)
send('set_roaming',false);tick(1);assert(not ethernet and status().roamingBlocked)
send('stop');tick(3);assert(not ethernet and not status().usbRequested)
send('set_roaming',true);tick(1);assert(not ethernet)
reg=1;tick(1);assert(not ethernet)
send('set_roaming','invalid');assert(last.event=='error' and storage.air780e_demo_roaming==true)
print('Full firmware simulation: default-off, home/roaming, SMS, opt-in/out, manual-stop and invalid input passed')
