module('luci.controller.air780e', package.seeall)

function index()
    entry({'admin','services','air780e'},template('air780e/dashboard'),'Air780E Modem',60)
    entry({'admin','services','air780e','api'},call('api')).leaf=true
end

local function rpc(payload)
    local nixio=require('nixio')
    local socket=assert(nixio.socket('unix','stream'))
    socket:setopt('socket','sndtimeo',10)
    socket:setopt('socket','rcvtimeo',10)
    local ok,result=pcall(function()
        assert(socket:connect('/var/run/air780e/service.sock'),'后台服务尚未启动')
        local data=payload..'\n'
        while #data>0 do
            local n=assert(socket:write(data),'后台服务写入失败')
            if n==0 then error('后台服务写入中断') end
            data=data:sub(n+1)
        end
        local buffer=''
        while not buffer:find('\n',1,true) do
            local part=socket:read(65536)
            if not part or #part==0 then error('后台服务响应超时') end
            buffer=buffer..part
            if #buffer>2097152 then error('后台响应超过限制') end
        end
        return buffer:match('([^\n]+)')
    end)
    socket:close()
    if not ok then error(result) end
    return result
end

function api()
    local http=require('luci.http')
    local json=require('luci.jsonc')
    local payload
    if http.getenv('REQUEST_METHOD')=='POST' then
        if not require('luci.dispatcher').test_post_security() then return end
        payload=http.formvalue('payload')
    else
        local action=http.formvalue('action') or 'snapshot'
        if action~='system_settings' and action~='traffic' and action~='snapshot' and action~='diagnostics' and action~='email_config' and
           action~='email_history' and action~='firmware_capabilities' then
            http.status(405,'Method Not Allowed'); return
        end
        payload=json.stringify({action=action,kind=http.formvalue('kind') or 'inbox'})
    end
    http.header('Cache-Control','no-store')
    http.prepare_content('application/json')
    if type(payload)~='string' or #payload>65536 then
        http.write_json({ok=false,error='请求无效或过大'}); return
    end
    local ok,result=pcall(rpc,payload)
    if ok then http.write(result) else http.write_json({ok=false,error=tostring(result)}) end
end
