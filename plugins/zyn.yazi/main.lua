local get_target = ya.sync(function()
    local hovered = cx.active.current.hovered
    local selected = {}
    for _, u in pairs(cx.active.selected) do
        table.insert(selected, tostring(u))
    end
    return {
        hovered_path = hovered and tostring(hovered.url) or nil,
        hovered_is_dir = hovered and hovered.cha.is_dir or false,
        selected = selected,
    }
end)

return {
    entry = function()
        local t = get_target()

        if t.hovered_is_dir and #t.selected == 0 then
            ya.emit("enter", {})
            return
        end

        local paths = #t.selected > 0 and t.selected or { t.hovered_path }
        if not paths[1] then return end

        local probe = Command("zyn-probe"):arg(paths[1]):output()
        local has_session = probe and probe.status and probe.status.success

        local parts = { "zyn" }
        for _, p in ipairs(paths) do
            table.insert(parts, ya.quote(p))
        end

        ya.emit("shell", {
            table.concat(parts, " "),
            block = not has_session,
            orphan = has_session,
            confirm = false,
        })
    end,
}
