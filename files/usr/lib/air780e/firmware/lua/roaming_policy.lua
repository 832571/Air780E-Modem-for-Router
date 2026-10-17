-- USB data policy only. It does not activate a SIM roaming plan.
local M={}
function M.isRoaming(state,mobile)
    if state==5 or state==7 then return true end
    local extra=mobile.CSFB_NOT_PREFERRED_REGISTERED_ROAMING
    return type(extra)=="number" and state==extra
end
function M.allow(requested,allowed,state,previous,mobile)
    if not requested then return false end
    if allowed then return true end
    if M.isRoaming(state,mobile) then return false end
    if state==1 or state==6 or (type(mobile.CSFB_NOT_PREFERRED_REGISTERED)=="number" and state==mobile.CSFB_NOT_PREFERRED_REGISTERED) then return true end
    -- Start closed. Retain the last decision during radio re-registration to avoid USB reset loops.
    return previous==true
end
return M
