# Code Forge - 管理后台 API 设计

> 本文档定义 Code Forge 管理后台（Vue 3）与后端（FastAPI）之间的 HTTP 接口。
> 资源模型与决策见 [design.md](./design.md)；需求见 [spec.md](./spec.md) F3.7 / F3.8 / F3.10。
> 飞书侧交互（WebSocket 推送、富卡片）不走本 API，由接入层独立承担。

---

## 1. 通用约定

### 1.1 路径前缀

- **管理后台接口**：统一前缀 `/api/admin`（下文表格中省略该前缀，仅写相对路径，如 `/workspaces` 实际为 `/api/admin/workspaces`）
- **鉴权接口**：前缀 `/api/auth`（表格中写完整路径）

### 1.2 鉴权

- **自建账号密码**（design D32）：`POST /api/auth/login`（username + password）→ 校验密码 → 下发 **HttpOnly Cookie**（session）；未登录返回 `401`
- 后续请求自动带 Cookie；敏感操作再做 owner 校验
- 账号准入（§5.1）：账号由管理员开通创建，用户首次登录可改密

### 1.3 统一响应

- 成功：直接返回资源 JSON，HTTP `200` / `201`（创建）/ `204`（删除，无 body）
- 列表：`{ items: [...], total, page, page_size }`
- 错误：HTTP 4xx/5xx + `{ error: { code, message, details? } }`

### 1.4 错误码

| HTTP | code | 含义 |
|---|---|---|
| 400 | bad_request | 参数错误 |
| 401 | unauthorized | 未登录 |
| 403 | forbidden | 无权限（非 owner） |
| 404 | not_found | 资源不存在 |
| 409 | conflict | 唯一约束冲突（如 FeishuChat 已绑别 WS） |
| 422 | validation_failed | 业务校验失败（如机器人不在群、Skill name 重复） |
| 500 | internal_error | 服务端错误 |

### 1.5 分页 / 筛选 / 排序

- 分页：`?page=1&page_size=20`（默认 20，最大 100）
- 筛选：`?status=&from=&to=&feishu_chat_id=&q=` 等，见各接口
- 排序：`?sort=-created_at`（`-` 表示降序）

### 1.6 多租户与权限

- **ws_id 一律放路径**（`/workspaces/{ws_id}/...`），后端校验当前用户对该 WS 的权限
- WS 配置 / Memory 管理 / trace 查看等读写操作均需 **owner 校验**（spec F3.8.2、design D31）
- 广场浏览（Skill/MCP 列表）登录即可
- 资源编辑（如自己上传的 Skill）需 resource owner 校验

### 1.7 异步任务

- 长操作（git clone、WS 级联删除）返回 `202 Accepted` + `{ task_id }`
- 客户端轮询 `GET /api/admin/tasks/{task_id}` 获取状态（pending / running / done / failed + result / error）

### 1.8 权限标注

- 🔑 **owner**：需 WS owner
- 🔑 **res**：需资源 owner（如上传者）
- 👤 **user**：登录用户即可

---

## 2. 鉴权与用户

### 2.1 鉴权

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| POST | /api/auth/login | 账号密码登录，下发 Cookie session | 公开 |
| POST | /api/auth/logout | 登出，清 Cookie | user |
| GET | /api/auth/me | 当前用户信息 + 可访问的 WS 列表 | user |
| POST | /api/auth/change-password | 修改自己的密码 | user |

### 2.2 用户管理

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /users | 用户列表 | 管理员 |
| POST | /users | 创建账号（含初始密码，管理员开通） | 管理员 |
| PATCH | /users/{id} | 改角色 / 停用启用 | 管理员 |
| POST | /users/{id}:reset-password | 重置密码 | 管理员 |

---

## 3. 飞书 App 管理

> 录入企业自建应用（`app_id` + `app_secret`），每个 App 启动一个独立 WebSocket 长连接（D7）。

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /feishu-apps | 列表（secret 脱敏） | user |
| POST | /feishu-apps | 注册（app_id, app_secret, name） | user |
| GET | /feishu-apps/{id} | 详情 | res |
| PATCH | /feishu-apps/{id} | 更新 name / secret / 连接状态 | res |
| DELETE | /feishu-apps/{id} | 删除（需先解绑所有 FeishuChat） | res |

> **脱敏**：列表 / 详情返回的 `app_secret` 只显示前后各 4 位、中间省略；完整 secret 仅创建时返回一次。

---

## 4. 工作空间

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces | 当前用户的 WS 列表 | user |
| POST | /workspaces | 创建 | user |
| GET | /workspaces/{ws_id} | 详情（含 repos / chats / mounts 概览） | owner |
| PATCH | /workspaces/{ws_id} | 改名 / 配置（含上下文管理策略 `context_config`，D34） | owner |
| DELETE | /workspaces/{ws_id} | 删除（需先解绑所有 FeishuChat + 解除广场引用，D11 / F3.2.5）→ 异步级联清理 | owner |

---

## 5. WS 内资源

### 5.1 Git Repo（F3.2.2 / D6）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/repos | 列表 | owner |
| POST | /workspaces/{ws_id}/repos | 挂载（url + 可选 token）→ git clone（异步 202） | owner |
| GET | /workspaces/{ws_id}/repos/{repo_id} | 详情（clone 状态 / cwd） | owner |
| POST | /workspaces/{ws_id}/repos/{repo_id}:sync | 重新 git pull（异步 202） | owner |
| DELETE | /workspaces/{ws_id}/repos/{repo_id} | 移除 | owner |

### 5.2 FeishuChat 绑定（F3.2.3~5 / D8）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/chats | 已绑 FeishuChat 列表 | owner |
| POST | /workspaces/{ws_id}/chats:check | 预校验（app_id + chat_id 合法性 + 机器人在群） | owner |
| POST | /workspaces/{ws_id}/chats | 绑定（app_id + chat_id → feishu_chat_id，唯一约束） | owner |
| DELETE | /workspaces/{ws_id}/chats/{feishu_chat_id} | 解绑 | owner |

> **ID 区分**：路径参数 `{feishu_chat_id}` 是 DB 内部主键（列表 / 绑定响应返回，后续操作用它）；绑定 / 预校验入参 body 里的 `chat_id` 是飞书原始群 ID（`oc_xxx`），与 `app_id` 组成 FeishuChat 唯一键。下文路径中的 `{feishu_chat_id}` 均指 DB 内部主键。

### 5.3 Skill / MCP 挂载（F3.2 / D11）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/skills | 已挂载 Skill 列表 | owner |
| POST | /workspaces/{ws_id}/skills | 挂载广场 Skill（skill_id） | owner |
| DELETE | /workspaces/{ws_id}/skills/{skill_id} | 解挂 | owner |
| GET | /workspaces/{ws_id}/mcps | 已挂载 MCP 列表 | owner |
| POST | /workspaces/{ws_id}/mcps | 挂载 | owner |
| DELETE | /workspaces/{ws_id}/mcps/{mcp_id} | 解挂 | owner |

> **上限校验**：单 WS 最多 50 个 Skill（F3.5.6），超限返回 422。

### 5.4 AGENT.md（F3.9 / D24）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/agent-md | WS 级 AGENT.md 内容 | owner |
| PUT | /workspaces/{ws_id}/agent-md | 编辑 WS 级 | owner |
| GET | /workspaces/{ws_id}/repos/{repo_id}/agent-md | Repo 级 AGENT.md（只读，随 git 同步） | owner |

---

## 6. 广场（Skill / MCP）

### 6.1 Skill 广场（F3.5 / D11 / D15）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /skills | 广场列表（我的 + 全员可见，支持可见性 / 搜索筛选） | user |
| POST | /skills | 上传（multipart：SKILL.md + resources + scripts） | user |
| GET | /skills/{skill_id} | 详情 + 引用数 | user |
| PATCH | /skills/{skill_id} | 改可见性 / 描述 | res |
| DELETE | /skills/{skill_id} | 删除（被引用时禁删，F3.5.5） | res |

### 6.2 MCP 广场（F3.5 / D11）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /mcps | 列表 | user |
| POST | /mcps | 注册（stdio 命令 / http endpoint） | user |
| GET | /mcps/{mcp_id} | 详情 | user |
| PATCH | /mcps/{mcp_id} | 改配置 / 可见性 | res |
| DELETE | /mcps/{mcp_id} | 删除（被引用禁删） | res |

---

## 7. 会话历史（F3.7.5 / D23）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/chats/{feishu_chat_id}/sessions | 某 FeishuChat 的 session 列表 | owner |
| GET | /workspaces/{ws_id}/sessions/{session_id} | 单 session 的 JSONL 内容（分页 / 分片） | owner |

---

## 8. Memory 管理（F3.7.6 / D18 / D19）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/chats/{feishu_chat_id}/memory | 某 FeishuChat 的 memory 文件列表 | owner |
| GET | /workspaces/{ws_id}/chats/{feishu_chat_id}/memory/{filename} | 文件内容 | owner |
| PUT | /workspaces/{ws_id}/chats/{feishu_chat_id}/memory/{filename} | 编辑文件 | owner |
| DELETE | /workspaces/{ws_id}/chats/{feishu_chat_id}/memory/{filename} | 删除文件 | owner |

> **路径安全**：`filename` 仅允许 `[A-Za-z0-9_\-]+\.md`，后端 resolve 校验落在 `memory/` 子树（D17），防穿越。

---

## 9. 可观测性（F3.10 / design §7）

### 9.1 Trace（调试）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/traces | Run 列表（筛选 status / from / to / feishu_chat_id） | owner |
| GET | /workspaces/{ws_id}/traces/{run_id} | 单 Run 的 span 树（全量 span 元数据） | owner |
| GET | /workspaces/{ws_id}/traces/{run_id}/spans/{span_id}/payload | span 完整 payload（HTTP Range 分片流式） | owner |

> **多租户**（D31）：所有查询强制 `ws_id` = 路径里的 ws_id 且属当前用户；payload 读取先 PG 校验 run_id 归属再读文件，禁直接拼路径。

### 9.2 Insights（成本性能，F3.10.6）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/insights/cost | 成本聚合（token / cost 趋势，按时间段） | owner |
| GET | /workspaces/{ws_id}/insights/tools | 工具耗时 TopN / 调用次数 / 错误率 | owner |
| GET | /workspaces/{ws_id}/insights/models | 模型使用占比 | owner |

### 9.3 Monitoring（监控告警，F3.10.7）

| Method | Path | 说明 | 权限 |
|---|---|---|---|
| GET | /workspaces/{ws_id}/monitoring/anomalies | 异常 Run 列表（error / timeout / interrupted） | owner |
| GET | /workspaces/{ws_id}/monitoring/rules | 告警规则列表 | owner |
| POST | /workspaces/{ws_id}/monitoring/rules | 新建规则 | owner |
| PATCH | /workspaces/{ws_id}/monitoring/rules/{rule_id} | 改阈值 / 开关 | owner |
| DELETE | /workspaces/{ws_id}/monitoring/rules/{rule_id} | 删除规则 | owner |

---

## 10. 关键接口示例

### 10.1 绑定 FeishuChat（含校验）

预校验 `POST /api/admin/workspaces/{ws_id}/chats:check`：

```json
请求：{ "app_id": "cli_xxx", "chat_id": "oc_yyy" }
响应 200：
{
  "valid": true,
  "bot_in_chat": true,
  "chat_name": "前端开发群",
  "existing_binding": false
}
```

校验通过后绑定 `POST /api/admin/workspaces/{ws_id}/chats`：

```json
请求：{ "app_id": "cli_xxx", "chat_id": "oc_yyy" }
响应 201：{ "feishu_chat_id": 123, "app_id": "cli_xxx", "chat_id": "oc_yyy", "chat_name": "前端开发群" }
冲突 409：{ "error": { "code": "conflict", "message": "该 FeishuChat 已绑定其他 WS（D8 独占约束）" } }
```

### 10.2 上传 Skill

`POST /api/admin/skills`（multipart/form-data）：

- 字段：`file`（含 SKILL.md + resources/scripts 的 zip 或多文件）、`name`、`description`、`visibility`
- 后端：校验 frontmatter（name 全局唯一、description 必填，D15）→ 落 `/skills/{skill_id}/` → 建 DB 记录
- 响应 201：`{ "skill_id": "...", "name": "...", "mounted_count": 0 }`
- 失败 422：`{ "error": { "code": "validation_failed", "message": "Skill name 已存在" } }`

### 10.3 Trace payload 分片读取

`GET /api/admin/workspaces/{ws_id}/traces/{run_id}/spans/{span_id}/payload`：

- 大文件用 HTTP Range：`Range: bytes=0-1048575`
- 响应 `206 Partial Content` + `Content-Range: bytes 0-1048575/2300000`
- 后端：先 PG 查 run_id → ws_id 校验归属（D31），再读 `traces/{trace_id}/{span_id}.*` 文件

### 10.4 异步任务状态

`GET /api/admin/tasks/{task_id}`：

```json
{
  "task_id": "...",
  "type": "git_clone",
  "status": "running",
  "progress": 0.6,
  "result": null,
  "error": null
}
```

### 10.5 登录

`POST /api/auth/login`：

```json
请求：{ "username": "alice", "password": "******" }
响应 200：{ "user": { "id": 1, "username": "alice", "role": "admin" } }
响应头：Set-Cookie: session=...; HttpOnly; SameSite=Lax
失败 401：{ "error": { "code": "unauthorized", "message": "用户名或密码错误" } }
```

> 登录接口限流（如同 IP 5 次 / 分钟），防爆破。

---

## 11. 待定 / 后续

- **实时推送**：后台实时刷新 trace / 异常 Run，MVP 用轮询，后续考虑 WebSocket / SSE
- **批量操作**：批量挂载 / 解挂 Skill
- **API 版本化**：`/v1` 前缀，MVP 暂不加
