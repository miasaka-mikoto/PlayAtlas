# PlayAtlas 局域网协议（v1）

这是 PlayAtlas 的离线局域网适配层，服务于同一局域网中的同屏/多设备聚会房间。它不需要账号、云端服务器或互联网匹配。

## 权威模型

- 由房主运行规则引擎，房主是唯一的状态权威。
- 客户端只发送动作，不发送“我已经赢了”之类的结果。
- 房主先用游戏模块的规则 API 验证动作，再递增 `server_seq` 并广播状态。
- 隐藏信息游戏使用 `get_observation(player_id)`；客户端收到自己的手牌，其他人的手牌只收到数量。不会把完整牌局广播后再靠 UI 遮挡。
- 服务器拒绝未知游戏、非法玩家身份、非法动作和超大消息。

## 消息顺序

```text
hello → welcome → lobby ↔ ready → started → snapshot
                                      ↑
                                 action → action_result → snapshot
```

所有消息是 UTF-8 JSON，每行一条，`protocol` 必须为 `1`，单条最大 256 KiB。

### hello

```json
{"protocol":1,"type":"hello","client_id":"stable-id","player_name":"小明"}
```

### welcome / lobby

`welcome` 分配稳定的 `player_id`（房主为 0，客户端从 1 开始），并返回 `game_id`、`ruleset_id` 和房间阶段。客户端发送 `ready: true` 后，房主可在所有已加入玩家准备完毕时开始。

### action

```json
{
  "protocol":1,
  "type":"action",
  "client_seq":4,
  "request_id":"retry-safe-id",
  "action":{"type":"play","card":["red","7"]}
}
```

`client_seq` 必须严格递增；重复的 `request_id` 会重放原来的 `action_result`，不会重复执行。断线重连时复用原 `client_id`，在房间仍保留时恢复同一座位。

### snapshot

```json
{
  "protocol":1,
  "type":"snapshot",
  "server_seq":19,
  "player_id":2,
  "observation":{}
}
```

`observation` 是当前玩家视角，不是内部完整存档。实时游戏可使用快照；回合制游戏还应记录规则版本和动作序列。

## 安全与故障

- 限制消息长度、JSON 类型和玩家身份；路径、脚本和资源不通过 LAN 执行。
- 主机断开时客户端显示断线提示；当前 v1 不伪造自动迁移主机。
- 断线重连是“同一 `client_id` 恢复座位 + 获取新的 player-scoped snapshot”，不是把客户端本地状态当权威。
- Python 适配器提供 `LanHost` / `LanClient` 与 localhost 集成测试；Godot `LanService` 使用 ENet。当前工作区没有 Godot 可执行文件，因此 Godot 多设备和真实路由器发现仍标为待验证。

## 当前支持范围

已接入协议工厂：五子棋、黑白棋、疯狂八（若模块可用）、坦克大战、UNO、升级扑克、21点。首批 party pack 的规则引擎和 localhost 协议可以自动测试；真实 Windows 多机、Wi-Fi 隔离网络、断线重连人工验收仍未完成。

