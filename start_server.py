#!/usr/bin/env python3
"""
Startup Script - Azure AI Foundry Agent MCP Server

Supports multiple startup modes:
1. HTTP MCP Server (recommended for Claude Code)
2. stdio MCP Server (for stdio clients)
3. RESTful API Server (for direct API calls)
"""

import sys
import os
import argparse
import asyncio
import logging
import signal
from typing import Optional
from dotenv import load_dotenv

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables
load_dotenv()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal. Stopping server...")
        # Get the current event loop and stop it
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        
        if loop and loop.is_running():
            # Cancel all tasks
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.stop()
        
        sys.exit(0)
    
    # Handle both SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def setup_logging(level: str = "info"):
    """Set logging level"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Disable verbose Azure HTTP logging
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


async def start_http_mcp_server(host: str = "127.0.0.1", port: int = 8000):
    """Start HTTP MCP Server"""
    from main import main as http_main
    print(f"Starting HTTP MCP Server at http://{host}:{port}")
    print("This mode is recommended for Claude Code integration")
    print("Configure Claude Code with:")
    print(f'  "url": "http://{host}:{port}/mcp/"')
    print("  Don't forget to add Authorization header!")
    print("=" * 60)
    
    try:
        await http_main()
    except asyncio.CancelledError:
        print("HTTP MCP Server cancelled")
    except Exception as e:
        print(f"HTTP MCP Server error: {e}")
        raise


async def start_stdio_mcp_server():
    """Start stdio MCP Server"""
    from main import stdio_main
    print("Starting stdio MCP Server")
    print("This mode is for stdio-based MCP clients")
    print("Server will use stdin/stdout for communication")
    print("=" * 60)
    
    try:
        await stdio_main()
    except asyncio.CancelledError:
        print("stdio MCP Server cancelled")
    except Exception as e:
        print(f"stdio MCP Server error: {e}")
        raise


async def start_restful_api_server(host: str = "127.0.0.1", port: int = 8000):
    """Start RESTful API Server"""
    import uvicorn
    import hashlib
    import json
    from fastapi import FastAPI, HTTPException, Header, Request
    from fastapi.responses import JSONResponse
    from azure_agent import AzureAgentManager
    
    # Configure FastAPI to handle UTF-8 properly
    app = FastAPI(title="Azure AI Foundry Agent REST API")
    agent_manager = AzureAgentManager()
    
    def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        return authorization[7:]  # len("Bearer ") = 7
    
    def get_user_id_from_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]
    
    @app.get("/")
    async def root():
        return {"message": "Azure AI Foundry Agent REST API", "version": "0.2.0"}
    
    @app.post("/api/send_message")
    async def api_send_message(
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        try:
            # Handle UTF-8 encoding properly
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            body = json.loads(body_str)
        except UnicodeDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid UTF-8 encoding: {str(e)}")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        
        message = body.get("message")
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        user_id = get_user_id_from_token(token)
        response = await agent_manager.send_message(message, user_id)
        return {"response": response, "user_id": user_id}
    
    @app.get("/api/list_messages")
    async def api_list_messages(authorization: Optional[str] = Header(None)):
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        user_id = get_user_id_from_token(token)
        messages = await agent_manager.list_messages(user_id)
        return {"messages": messages, "user_id": user_id}
    
    @app.post("/api/clear_conversation")
    async def api_clear_conversation(authorization: Optional[str] = Header(None)):
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        user_id = get_user_id_from_token(token)
        result = await agent_manager.clear_conversation(user_id)
        return {"result": result, "user_id": user_id}
    
    @app.post("/api/new_conversation")
    async def api_new_conversation(authorization: Optional[str] = Header(None)):
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        user_id = get_user_id_from_token(token)
        result = await agent_manager.clear_conversation(user_id)  # Same as clear
        return {"result": result, "user_id": user_id}
    
    print(f"Starting RESTful API Server at http://{host}:{port}")
    print("Available endpoints:")
    print(f"  GET  http://{host}:{port}/")
    print(f"  POST http://{host}:{port}/api/send_message")
    print(f"  GET  http://{host}:{port}/api/list_messages") 
    print(f"  POST http://{host}:{port}/api/clear_conversation")
    print(f"  POST http://{host}:{port}/api/new_conversation")
    print("All endpoints require Authorization: Bearer <token> header")
    print("=" * 60)
    
    config = uvicorn.Config(
        app, 
        host=host, 
        port=port, 
        log_level="info",
        # Ensure proper UTF-8 handling
        access_log=False,  # Reduce noise
    )
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except asyncio.CancelledError:
        print("RESTful API Server cancelled")
    except Exception as e:
        print(f"RESTful API Server error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Azure AI Foundry Agent MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Startup Mode Descriptions:
  http   - HTTP MCP Server (recommended for Claude Code)
  stdio  - stdio MCP Server (for stdio clients)  
  api    - RESTful API Server (for direct API calls)

Environment Variable Configuration:
  AZURE_TENANT_ID     - Azure Tenant ID
  AZURE_CLIENT_ID     - Azure Client ID
  AZURE_CLIENT_SECRET - Azure Client Secret
  AZURE_ENDPOINT      - Azure AI Project Endpoint
  AZURE_AGENT_ID      - Azure AI Agent ID

Examples:
  python start_server.py --mode http
  python start_server.py --mode stdio
  python start_server.py --mode api --host 0.0.0.0 --port 9000
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["http", "stdio", "api"],
        default="http",
        help="Server startup mode (default: http)"
    )
    
    parser.add_argument(
        "--host",
        default=os.getenv("SERVER_HOST", "0.0.0.0"),
        help="Server host address (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SERVER_PORT", "8000")),
        help="Server port (default: 8000)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=os.getenv("LOG_LEVEL", "info"),
        help="Log level (default: info)"
    )
    
    args = parser.parse_args()
    
    # Set up signal handlers first
    setup_signal_handlers()
    
    # Set up logging
    setup_logging(args.log_level)
    
    print("Azure AI Foundry Agent MCP Server")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Log Level: {args.log_level}")
    
    if args.mode in ["http", "api"]:
        print(f"Host: {args.host}")
        print(f"Port: {args.port}")
    
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        if args.mode == "http":
            asyncio.run(start_http_mcp_server(args.host, args.port))
        elif args.mode == "stdio":
            asyncio.run(start_stdio_mcp_server())
        elif args.mode == "api":
            asyncio.run(start_restful_api_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()