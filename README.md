# Azure AI Foundry Agent MCP Server

*English | [中文](README_CN.md)*

Azure AI Foundry Agent MCP Server with user isolation and session management.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create `.env` file:
```bash
cp .env.example .env
# Edit .env file with your Azure configuration
```

### 3. Start Server
```bash
# HTTP MCP mode (Recommended for VSCode GitHub Copilot)
python start_server.py --mode http

# Other modes
python start_server.py --mode stdio  # stdio MCP
python start_server.py --mode api    # RESTful API
```

### 4. Configure VSCode GitHub Copilot
Add MCP server configuration in VSCode:
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

## Project Overview

This is a Model Context Protocol (MCP) server that enables developers to access Azure AI Foundry Agents through VSCode GitHub Copilot. The core design philosophy is to provide seamless integration of Azure AI services into VSCode development workflows through standardized MCP protocol.

### Core Features

- **🔐 Token-based Authentication**: Uses Bearer token in Authorization header for user identification
- **👥 User Isolation**: Each token corresponds to independent Azure AI Agent threads, ensuring data security
- **💬 Session Management**: Support for clearing conversations and creating new sessions with flexible context control
- **🚀 Multiple Deployment Modes**: HTTP MCP, stdio MCP, and RESTful API deployment options
- **🛠️ Complete MCP Support**: Full implementation of standard MCP protocol core features
- **🧪 Test Mode**: Built-in mock functionality for development without Azure credentials

## System Requirements

- **Python 3.8+**
- **Azure AI Foundry Account**: Requires Azure AI Project and Agent setup
- **Azure App Registration**: Application credentials for service authentication

## Detailed Configuration

### Azure Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_TENANT_ID` | Azure Tenant ID | `12345678-1234-1234-1234-123456789012` |
| `AZURE_CLIENT_ID` | Azure Application Client ID | `87654321-4321-4321-4321-210987654321` |
| `AZURE_CLIENT_SECRET` | Azure Application Client Secret | `your_client_secret_here` |
| `AZURE_ENDPOINT` | Azure AI Project Endpoint | `https://your-project.services.ai.azure.com/api/projects/your-project` |
| `AZURE_AGENT_ID` | Azure AI Agent ID | `asst_xxxxxxxxxxxxxxxxx` |

### Launch Parameters

```bash
python start_server.py [options]

Options:
  --mode {http,stdio,api}  Server mode (default: http)
  --port PORT              HTTP port (default: 8000)
  --log-level LEVEL        Log level (default: INFO)
  --help                   Show help information
```

## API Reference

### Available Tools (MCP Tools)

#### 1. send_message
Send message to Azure AI Agent and receive response.

**Parameters:**
- `message` (string): Message content to send

**Example:**
```json
{
  "name": "send_message",
  "arguments": {
    "message": "Hello, please introduce yourself"
  }
}
```

#### 2. list_messages
List all messages in current conversation thread.

**Example:**
```json
{
  "name": "list_messages",
  "arguments": {}
}
```

#### 3. clear_conversation
Clear current conversation and start new thread.

**Example:**
```json
{
  "name": "clear_conversation", 
  "arguments": {}
}
```

#### 4. new_conversation
Start new conversation thread (equivalent to clear_conversation).

**Example:**
```json
{
  "name": "new_conversation",
  "arguments": {}
}
```

### HTTP Endpoints

#### MCP Protocol Endpoints (HTTP Mode)
- **POST** `/mcp/` - MCP protocol message handling
- **GET** `/mcp/` - Service health check

#### RESTful API Endpoints (API Mode)
- **POST** `/api/send_message` - Send message
- **GET** `/api/list_messages` - List message history
- **POST** `/api/clear_conversation` - Clear conversation
- **POST** `/api/new_conversation` - Create new conversation

## Advanced Topics

### Token Authentication & User Isolation

#### Authentication Mechanism
Currently uses simplified Token validation (Mock mode). Production deployment requires replacing with real authentication logic:

```python
def validate_token(token: str) -> bool:
    # Implement real token validation logic
    # e.g., JWT validation, database query, etc.
    return verify_jwt_token(token)  # example
```

#### User Isolation Strategy

**Critical for Data Security**: Ensures complete data separation between users to prevent information leakage and maintain privacy compliance (GDPR, HIPAA, SOC 2).

**Implementation:**
- **User ID Generation**: SHA256 hash of token (first 16 chars) ensures deterministic but secure mapping
- **Thread Isolation**: Each user ID gets dedicated Azure AI Agent thread with separate conversation contexts  
- **Data Persistence**: User-thread mapping saved in `user_thread_mapping.json` for consistency across restarts
- **Concurrency Safety**: Thread locks prevent race conditions in concurrent access scenarios

**Security Considerations**: Production deployments should implement proper token validation, rotation mechanisms, audit logging, and per-user rate limiting.

### Testing & Validation

#### Quick Validation
```bash
# Run manual test to verify core functionality
python manual_test.py
```

#### Test Mode
Project supports test mode without Azure credentials, enable with environment variable `TEST_MODE=true`.

#### Debugging Tips

**Enable verbose logging:**
```bash
python start_server.py --mode http --log-level debug
```

**Use test mode:**
```bash
export TEST_MODE=true
python start_server.py --mode http
```


### License

MIT License - See [LICENSE](LICENSE) file for details
