#!/usr/bin/env python3
"""
Azure AI Foundry Agent MCP Server

This server provides access to Azure AI Foundry Agents through the Model Context Protocol (MCP).
"""

import asyncio
import logging
import hashlib
import os
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException, Header
import json
import uvicorn
from dotenv import load_dotenv

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from azure_agent import AzureAgentManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("azure-foundry-agent-mcp")

# MCP Server instance
server = Server("azure-foundry-agent-mcp")

# Initialize the Azure Agent Manager
test_mode = os.getenv('TEST_MODE', '').lower() == 'true'
agent_manager = AzureAgentManager(test_mode=test_mode)

# FastAPI app for HTTP MCP server
app = FastAPI(title="Azure AI Foundry Agent MCP Server")


def validate_token(token: str) -> bool:
    """
    Mock token validation function.
    Always returns True for now - implement real validation logic here later.
    
    Args:
        token: The bearer token from Authorization header
        
    Returns:
        bool: Always True (mock validation)
    """
    if not token:
        return False
    # Mock validation - always return True for any non-empty token
    return True


def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    """
    Extract token from Authorization header.
    
    Args:
        authorization: The Authorization header value (e.g., "Bearer your_token")
        
    Returns:
        str: The extracted token, or None if invalid format
    """
    if not authorization:
        return None
    
    # Check if it starts with "Bearer "
    if not authorization.startswith("Bearer "):
        return None
    
    # Extract token after "Bearer "
    token = authorization[7:]  # len("Bearer ") = 7
    return token if token else None


def get_user_id_from_token(token: str) -> str:
    """
    Generate user ID from token.
    Uses the token itself as the user identifier.
    
    Args:
        token: The bearer token
        
    Returns:
        str: User ID derived from token
    """
    # Use first 16 chars of token hash as user ID for consistency
    return hashlib.sha256(token.encode()).hexdigest()[:16]


@server.list_tools()
async def handle_list_tools():
    """
    List available tools for Azure AI Foundry Agent interaction.
    """
    return [
        {
            "name": "send_message",
            "description": "Send a message to the Azure AI agent and get a response. Uses your personal thread automatically.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message content to send to the agent"
                    }
                },
                "required": ["message"],
                "additionalProperties": False
            }
        },
        {
            "name": "list_messages",
            "description": "List all messages in your conversation thread",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "clear_conversation",
            "description": "Clear/reset the current conversation and start a new thread",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "new_conversation", 
            "description": "Start a new conversation thread (alias for clear_conversation)",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    ]


# Global variable to store current request token for MCP handlers
_current_token: Optional[str] = None


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Handle tool calls to the Azure AI Foundry Agent.
    Uses the token from current HTTP request context to identify user.
    """
    if arguments is None:
        arguments = {}

    # Get token from current HTTP request context
    global _current_token
    if not _current_token:
        return [{"type": "text", "text": "Error: No authentication token found"}]

    # Generate user ID from token
    user_id = get_user_id_from_token(_current_token)
    logger.info(f"Handling tool call '{name}' for user {user_id} (token: {_current_token[:8]}...)")

    try:
        if name == "send_message":
            message = arguments.get("message")
            
            if not message:
                return [{"type": "text", "text": "Error: message is required"}]
            
            response = await agent_manager.send_message(message, user_id)
            return [{"type": "text", "text": response}]

        elif name == "list_messages":
            messages = await agent_manager.list_messages(user_id)
            return [{"type": "text", "text": messages}]
        
        elif name == "clear_conversation" or name == "new_conversation":
            result = await agent_manager.clear_conversation(user_id)
            return [{"type": "text", "text": result}]

        else:
            return [{"type": "text", "text": f"Unknown tool: {name}"}]

    except Exception as e:
        logger.error(f"Error handling tool call {name} for user {user_id}: {str(e)}")
        return [{"type": "text", "text": f"Error: {str(e)}"}]


@app.get("/mcp/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "azure-foundry-agent-mcp"}


@app.post("/mcp/")
async def handle_mcp_request(request: Request, authorization: Optional[str] = Header(None)):
    """
    Handle MCP requests over HTTP with token-based authentication.
    """
    global _current_token
    
    # Extract token from Authorization header
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    # Validate token
    if not validate_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")
    
    # Set current token for MCP handlers
    _current_token = token
    user_id = get_user_id_from_token(token)
    logger.info(f"Processing MCP request for user {user_id} (token: {token[:8]}...)")
    
    try:
        # Get request body
        body = await request.body()
        
        # Parse JSON-RPC request
        try:
            rpc_request = json.loads(body.decode())
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        # Handle different MCP methods
        method = rpc_request.get("method")
        params = rpc_request.get("params", {})
        request_id = rpc_request.get("id")
        
        logger.info(f"MCP method: {method}, params: {params}")
        
        # Handle MCP protocol methods
        if method == "initialize":
            # MCP initialization handshake
            client_info = params.get("clientInfo", {})
            protocol_version = params.get("protocolVersion", "2024-11-05")
            capabilities = params.get("capabilities", {})
            
            logger.info(f"Initializing MCP for client: {client_info}")
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "logging": {}
                    },
                    "serverInfo": {
                        "name": "azure-foundry-agent-mcp",
                        "version": "0.1.0"
                    }
                }
            }
            
        elif method == "initialized":
            # Notification that initialization is complete
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {}
            }
            
        elif method == "tools/list":
            tools = await handle_list_tools()
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = await handle_call_tool(tool_name, arguments)
            response = {
                "jsonrpc": "2.0", 
                "id": request_id,
                "result": {"content": result}
            }
            
        elif method == "logging/setLevel":
            # Handle logging level setting
            level = params.get("level", "info")
            logger.info(f"Setting log level to: {level}")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {}
            }
            
        else:
            # Unknown method
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                    "data": {"method": method}
                }
            }
        
        logger.info(f"Sending response: {json.dumps(response)[:200]}...")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing MCP request: {str(e)}")
        error_response = {
            "jsonrpc": "2.0",
            "id": rpc_request.get("id") if 'rpc_request' in locals() else None,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }
        return error_response
    finally:
        # Clear current token after request
        _current_token = None


async def main():
    """Main entry point for the HTTP MCP server."""
    # Start FastAPI server on port 8000
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


async def stdio_main():
    """Entry point for stdio-based MCP server (legacy).""" 
    # Use stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="azure-foundry-agent-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())