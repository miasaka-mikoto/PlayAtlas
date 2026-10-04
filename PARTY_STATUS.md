# Party Pack 1 / 局域网状态

更新时间：2026-10-05

| 内容 | 当前状态 | 证据 | 未完成 |
|---|---|---|---|
| 坦克大战规则层 | 已自动测试 | `tests/test_party_games.py`：网格移动、子弹 tick、命中、复位、存档 | Godot 画面、音效、Windows/触屏人工验收 |
| UNO 规则层 | 已自动测试 | 108 张守恒、隐藏手牌视角、Wild 选色、合法/非法动作 | Godot 发牌/动画、Windows/多设备验收 |
| 升级扑克 | 已自动测试 | 两副牌 108 张守恒、跟牌、25 墩与队伍计分 | 规则研究复核、叫主/变体、Godot/多设备验收 |
| 21点 | 已自动测试 | 庄家暗牌隔离、要牌/停牌、软 17、结算 | Godot 场景、音效、多人流程验收 |
| 奖品转盘机 / 幸运积分轮 | 已自动测试 | 固定种子、积分、次数上限；不含现金/下注/兑换 | Godot 表现和聚会可用性人工验收 |
| Python LAN v1 | 已自动测试（localhost） | `tests/test_lan.py`：hello、ready、start、snapshot、隐藏信息、request-id 重试 | 真实 Wi-Fi、Windows 防火墙、路由器发现、断线重连人工验收 |
| Godot `LanService` | 已实现（静态检查范围） | ENet autoload、主机权威 RPC、client sequence、player-scoped snapshot | 当前环境无 Godot 可执行文件，未启动/未联机验证 |

## 统计边界

Party Pack 1 是独立扩展，当前不加到 `content/GAME_CATALOG.json` 的首发 36 款，也不把“规则层 ready”写成“正式可玩”。只有完成 Godot 视觉、教程、存档、音效、真实流程、Windows 和联机人工证据后，才可以单项转入正式目录。

## 受限环境记录

普通沙箱禁止 Python 创建 TCP socket，因此常规 `pytest` 会将 LAN 集成用例标记为跳过；在允许 localhost 的受控执行中该用例通过（`1 passed`）。这两种结果分别记录，不能互相冒充真实多设备验收。

