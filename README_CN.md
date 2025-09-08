# Azure AI Foundry Agent MCP Server

*[English](README.md) | 中文*

Azure AI Foundry Agent MCP 服务器，支持用户隔离和会话管理。

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
创建 `.env` 文件：
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 Azure 配置
```

### 3. 启动服务器
```bash
# HTTP MCP 模式 (推荐用于 VSCode GitHub Copilot)
python start_server.py --mode http

# 其他模式
python start_server.py --mode stdio  # stdio MCP
python start_server.py --mode api    # RESTful API
```

### 4. 配置 Claude Code/MCP 客户端

#### 选项 1: HTTP MCP (推荐)
在 Claude Code 或 VSCode GitHub Copilot 的 MCP 服务器配置中添加：
```json
{
  "servers": {
    "ai-foundry-agent": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8000/mcp/",
      "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_token_here"
      }
    }
  }
}
```

#### 选项 2: stdio MCP
对于基于 stdio 的 MCP 客户端，需配置环境变量和客户端配置：

**环境变量:**
```bash
export MCP_STDIO_TOKEN="your_token_here"
# Windows 下:
set MCP_STDIO_TOKEN=your_token_here
```

**MCP 客户端配置:**
```json
{
  "servers": {
    "ai-foundry-agent": {
      "type": "stdio",
      "command": "python",
      "args": ["start_server.py", "--mode", "stdio"],
      "cwd": "/path/to/ai-foundry-agent-mcp",
      "env": {
        "MCP_STDIO_TOKEN": "your_token_here"
      }
    }
  }
}
```

## 项目概述

这是一个 Model Context Protocol (MCP) 服务器，为开发者提供通过 VSCode GitHub Copilot 访问 Azure AI Foundry Agents 的能力。项目核心设计理念是通过标准化的 MCP 协议，让开发者能够在 VSCode 中无缝集成 Azure AI 服务到他们的开发工作流中。

### 核心特性

- **🔐 Token-based 认证**: 使用 Authorization header 中的 Bearer token 区分用户
- **👥 用户隔离**: 每个 token 对应独立的 Azure AI Agent 线程，确保数据安全
- **💬 会话管理**: 支持清空会话和新建会话，灵活控制对话上下文
- **🚀 多种部署模式**: HTTP MCP、stdio MCP 和 RESTful API 三种启动方式
- **🛠️ 完整 MCP 支持**: 实现标准 MCP 协议的所有核心功能
- **🧪 测试模式**: 内置 Mock 功能，支持无 Azure 凭据的开发测试

## 环境要求

- **Python 3.8+**
- **Azure AI Foundry 账户**：需要创建 Azure AI Project 和 Agent
- **Azure 应用注册**：用于服务认证的应用凭据

## 详细配置

### Azure 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `AZURE_TENANT_ID` | Azure 租户 ID | `12345678-1234-1234-1234-123456789012` |
| `AZURE_CLIENT_ID` | Azure 应用客户端 ID | `87654321-4321-4321-4321-210987654321` |
| `AZURE_CLIENT_SECRET` | Azure 应用客户端密钥 | `your_client_secret_here` |
| `AZURE_ENDPOINT` | Azure AI Project 端点 | `https://your-project.services.ai.azure.com/api/projects/your-project` |
| `AZURE_AGENT_ID` | Azure AI Agent ID | `asst_xxxxxxxxxxxxxxxxx` |
| `MCP_STDIO_TOKEN` | stdio 模式认证 token (可选) | `your_stdio_token_here` |

### 启动参数

```bash
python start_server.py [选项]

选项:
  --mode {http,stdio,api}  服务器模式 (默认: http)
  --port PORT              HTTP 端口 (默认: 8000)
  --log-level LEVEL        日志级别 (默认: INFO)
  --help                   显示帮助信息
```

## API 参考

### 可用工具 (MCP Tools)

#### 1. send_message
发送消息给 Azure AI Agent 并获取回复。

**参数:**
- `message` (string): 要发送的消息内容

**示例:**
```json
{
  "name": "send_message",
  "arguments": {
    "message": "你好，请介绍一下你自己"
  }
}
```

#### 2. list_messages
列出当前对话线程中的所有消息。

**示例:**
```json
{
  "name": "list_messages",
  "arguments": {}
}
```

#### 3. clear_conversation
清空当前对话并开始新的线程。

**示例:**
```json
{
  "name": "clear_conversation", 
  "arguments": {}
}
```

#### 4. new_conversation
开始新的对话线程（等同于 clear_conversation）。

**示例:**
```json
{
  "name": "new_conversation",
  "arguments": {}
}
```

### HTTP 端点

#### MCP 协议端点 (HTTP 模式)
- **POST** `/mcp/` - MCP 协议消息处理
- **GET** `/mcp/` - 服务健康检查

#### RESTful API 端点 (API 模式)
- **POST** `/api/send_message` - 发送消息
- **GET** `/api/list_messages` - 列出消息历史
- **POST** `/api/clear_conversation` - 清空对话
- **POST** `/api/new_conversation` - 新建对话

### RESTful API 使用指南

当服务器运行在 API 模式（`--mode api`）时，你可以通过标准的 HTTP 请求使用 curl 或任何 HTTP 客户端与 Azure AI Foundry Agent 进行交互。

#### 身份验证
所有 API 请求都需要在 Authorization header 中提供 Bearer token 进行身份验证：
```bash
Authorization: Bearer your_token_here
```

#### API 端点与 curl 示例

##### 1. 发送消息
向 Azure AI Agent 发送消息并接收回复。

**端点:** `POST /api/send_message`

**请求体:**
```json
{
  "message": "你好，请介绍一下你自己"
}
```

**curl 示例:**
```bash
curl -X POST http://localhost:8000/api/send_message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token_here" \
  -d '{
    "message": "你好，请介绍一下你自己"
  }'
```

**响应:**
```json
{
  "success": true,
  "response": "你好！我是由 Azure AI Foundry 提供支持的 AI 助手...",
  "message_id": "msg_abc123"
}
```

##### 2. 列出消息
获取当前对话线程中的所有消息。

**端点:** `GET /api/list_messages`

**curl 示例:**
```bash
curl -X GET http://localhost:8000/api/list_messages \
  -H "Authorization: Bearer your_token_here"
```

**响应:**
```json
{
  "success": true,
  "messages": [
    {
      "id": "msg_abc123",
      "role": "user",
      "content": "你好，请介绍一下你自己",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "msg_def456",
      "role": "assistant", 
      "content": "你好！我是一个 AI 助手...",
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ],
  "thread_id": "thread_xyz789"
}
```

##### 3. 清空对话
清空当前对话并开始新的线程。

**端点:** `POST /api/clear_conversation`

**curl 示例:**
```bash
curl -X POST http://localhost:8000/api/clear_conversation \
  -H "Authorization: Bearer your_token_here"
```

**响应:**
```json
{
  "success": true,
  "message": "对话已成功清空",
  "new_thread_id": "thread_new123"
}
```

##### 4. 新建对话
开始新的对话线程（等同于 clear_conversation）。

**端点:** `POST /api/new_conversation`

**curl 示例:**
```bash
curl -X POST http://localhost:8000/api/new_conversation \
  -H "Authorization: Bearer your_token_here"
```

**响应:**
```json
{
  "success": true,
  "message": "新对话已开始",
  "thread_id": "thread_new456"
}
```

#### 错误处理

**身份验证错误:**
```bash
# 缺失或无效的 token
curl -X POST http://localhost:8000/api/send_message \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

**响应:**
```json
{
  "success": false,
  "error": "未授权：无效或缺失的 token",
  "code": 401
}
```

**验证错误:**
```bash
# 缺失必需字段
curl -X POST http://localhost:8000/api/send_message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token_here" \
  -d '{}'
```

**响应:**
```json
{
  "success": false,
  "error": "缺失必需字段：message",
  "code": 400
}
```

#### 完整示例工作流
```bash
# 1. 开始新对话
curl -X POST http://localhost:8000/api/new_conversation \
  -H "Authorization: Bearer your_token_here"

# 2. 发送消息
curl -X POST http://localhost:8000/api/send_message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token_here" \
  -d '{
    "message": "什么是 Azure AI Foundry？"
  }'

# 3. 发送后续消息
curl -X POST http://localhost:8000/api/send_message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token_here" \
  -d '{
    "message": "能详细介绍一下它的功能特性吗？"
  }'

# 4. 列出对话中的所有消息
curl -X GET http://localhost:8000/api/list_messages \
  -H "Authorization: Bearer your_token_here"

# 5. 完成后清空对话
curl -X POST http://localhost:8000/api/clear_conversation \
  -H "Authorization: Bearer your_token_here"
```

## 高级主题

### Token 认证与用户隔离

#### 认证机制
当前使用简化的 Token 验证（Mock 模式），生产环境中需要替换为真实的认证逻辑：

```python
def validate_token(token: str) -> bool:
    # 实现真实的 token 验证逻辑
    # 例如：JWT 验证、数据库查询等
    return verify_jwt_token(token)  # 示例
```

#### 用户隔离策略

**数据安全关键**: 确保用户间完全数据分离，防止信息泄露并满足隐私合规要求 (GDPR、HIPAA、SOC 2)。

**实现方式:**
- **用户 ID 生成**: 基于 token 的 SHA256 哈希（前16位）确保确定性但安全的映射
- **线程隔离**: 每个用户 ID 获得专用的 Azure AI Agent 线程，具有独立的对话上下文
- **数据持久化**: 用户-线程映射保存在 `user_thread_mapping.json` 中，确保重启后的一致性
- **并发安全**: 使用线程锁防止并发访问场景中的竞争条件

**安全考虑**: 生产部署应实现适当的 token 验证、轮换机制、审计日志和每用户速率限制。

### 测试与验证

#### 快速验证
```bash
# 运行手动测试验证核心功能
python manual_test.py
```

#### 测试模式
项目支持无需 Azure 凭据的测试模式，使用环境变量 `TEST_MODE=true` 启用。


#### 调试技巧

**启用详细日志:**
```bash
python start_server.py --mode http --log-level debug
```

**使用测试模式:**
```bash
export TEST_MODE=true
python start_server.py --mode http
```


### 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
