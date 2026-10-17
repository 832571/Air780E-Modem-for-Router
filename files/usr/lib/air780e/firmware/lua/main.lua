PROJECT = "AIR780E_DEMO"
VERSION = "0.2.4"
local function initialize()
sys = require("sys")
-- Keep the control channel alive so task failures can be diagnosed instead of reboot looping.
_G.COROUTINE_ERROR_RESTART = false
_G.COROUTINE_ERROR_ROLL_BACK = false
sysplus = require("sysplus")
local port = uart.VUART_0
local buffer, ready, busy, enabled = "", false, false, false
fskv.init()
local requested = fskv.get("air780e_demo_usb") == true
local roamingAllowed = fskv.get("air780e_demo_roaming") == true
local policy = require("roaming_policy")
local registration = mobile.status()
local policyAllowed = false
enabled = false
local function configureUsb(target)
    -- Official sequence: never yield while USB is powered off.
    pm.power(pm.USB,false)
    local ok = mobile.config(mobile.CONF_USB_ETHERNET,target and 7 or 6)
    mobile.flymode(0,true)
    mobile.flymode(0,false)
    pm.power(pm.USB,true)
    return ok
end
configureUsb(false)
local messages, sequence = {}, 0
local initialized = false
local phoneNumber = ""
local function reply(event, data, rid)
    data = data or {}
    data.app, data.protocol, data.event, data.request_id = PROJECT, 1, event, rid
    uart.write(port, json.encode(data).."\n")
end
local function status(rid)
    registration = mobile.status()
    reply("status", {version=VERSION, smsReady=ready, usbEnabled=enabled, usbMode="ECM", rsrp=mobile.rsrp(), phoneNumber=phoneNumber, roamingControlSupported=true, registrationStatus=registration, roaming=policy.isRoaming(registration,mobile), dataRoamingAllowed=roamingAllowed, roamingBlocked=requested and not policyAllowed, usbRequested=requested}, rid)
end
local function handle(line)
    local c = json.decode(line)
    if type(c)~="table" or c.app~=PROJECT or c.protocol~=1 then return end
    local rid = c.request_id
    if c.action=="status" then status(rid)
    elseif c.action=="inbox" then reply("inbox", {messages=messages}, rid)
    elseif c.action=="start" or c.action=="stop" then
        if not initialized then reply("error",{message="usb_initializing"},rid) return end
        if busy then reply("error",{message="device_busy"},rid) return end
        local target = c.action=="start"
        busy=true
        sys.taskInit(function()
            local ok, err = pcall(function()
                reply("network",{usbEnabled=target,reconfiguring=true},rid)
                sys.wait(700)
                requested=target
                policyAllowed=policy.allow(requested,roamingAllowed,mobile.status(),policyAllowed,mobile)
                local effective=requested and policyAllowed
                if not configureUsb(effective) then error("usb_config_failed") end
                fskv.set("air780e_demo_usb",target)
                enabled=effective
                busy=false
            end)
            if not ok then
                mobile.flymode(0,false)
                busy=false
                reply("error",{message="network_config_failed",detail=tostring(err)},rid)
            end
        end)
    elseif c.action=="set_roaming" then
        if type(c.enabled)~="boolean" then reply("error",{message="invalid_roaming"},rid) return end
        if busy then reply("error",{message="device_busy"},rid) return end
        if not fskv.set("air780e_demo_roaming",c.enabled) then reply("error",{message="roaming_save_failed"},rid) return end
        roamingAllowed=c.enabled
        -- ACK is sent before a possible USB re-enumeration. Status confirms the stored policy.
        reply("roaming_policy",{dataRoamingAllowed=roamingAllowed},rid)
    elseif c.action=="send_sms" then
        if not ready then reply("error",{message="sms_not_ready"},rid) return end
        if busy then reply("error",{message="device_busy"},rid) return end
        if type(c.number)~="string" or not c.number:match("^%+?%d+$") or #c.number>21 or type(c.message)~="string" or #c.message==0 or #c.message>2000 then
            reply("error",{message="invalid_sms"},rid) return
        end
        busy=true
        sys.taskInit(function()
            local fixChinaNumber = c.number:sub(1,3)=="+86"
            local ok, result = pcall(function() return sms.sendLong(c.number,c.message,fixChinaNumber).wait() end)
            reply("sms_sent",{success=ok and result==true,apiOk=ok,resultType=type(result),detail=ok and (result==true and "" or "短信接口返回 "..tostring(result)) or tostring(result)},rid)
            busy=false
        end)
    else reply("error",{message="unknown_action"},rid) end
end
uart.setup(port,115200,8,1)
uart.on(port,"receive",function(id,len)
    buffer=buffer..uart.read(id,len)
    if #buffer>8192 then buffer="" return end
    while true do
        local pos=buffer:find("\n",1,true)
        if not pos then break end
        local line=buffer:sub(1,pos-1); buffer=buffer:sub(pos+1)
        local ok=pcall(handle,line)
        if not ok then reply("error",{message="command_error"}) end
    end
end)
sys.subscribe("SMS_READY",function() ready=true end)
sys.subscribe("SMS_INC",function(number,message)
    sequence=sequence+1
    local item={app=PROJECT,protocol=1,event="sms_received",sms_id=tostring(os.time())..":"..sequence,number=number,message=message,received=os.date("%Y-%m-%d %H:%M:%S")}
    messages[#messages+1]=item
    if #messages>100 then table.remove(messages,1) end
    reply("sms_received",item)
end)
sys.taskInit(function()
    -- Core initializes cellular automatically; don't toggle radio/USB during app boot.
    sys.wait(1000)
    initialized=true
end)
sys.taskInit(function()
    while true do
        if initialized and not busy then
            policyAllowed=policy.allow(requested,roamingAllowed,mobile.status(),policyAllowed,mobile)
            local target=requested and policyAllowed
            if target~=enabled then
                busy=true
                local ok,result=pcall(configureUsb,target)
                if ok and result then enabled=target end
                busy=false
            end
        end
        sys.wait(1000)
    end
end)
sys.timerLoopStart(function()
    local ok, err = pcall(status)
    if not ok then reply("error",{message="status_failed",detail=tostring(err)}) end
end,1000)
sys.taskInit(function()
    sys.wait(15000)
    while not mobile.simPin() do sys.wait(2000) end
    local ok, number = pcall(mobile.number)
    if ok and type(number)=="string" then phoneNumber=number end
end)
end
local bootOk, bootError = pcall(initialize)
if not bootOk then
    sys = sys or require("sys")
    uart.setup(uart.VUART_0,115200,8,1)
    local text = tostring(bootError):gsub('["\\%c]', ' ')
    sys.timerLoopStart(function()
        uart.write(uart.VUART_0,'{"app":"AIR780E_DEMO","protocol":1,"event":"boot_error","message":"'..text..'"}\n')
    end,1000)
end
sys.run()
