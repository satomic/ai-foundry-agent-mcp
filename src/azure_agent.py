"""
Azure AI Foundry Agent Manager

This module provides a wrapper around Azure AI Foundry Agent functionality
for use in the MCP server.
"""

import asyncio
import json
import logging
import os
import hashlib
import threading
from typing import Optional, Dict
from dotenv import load_dotenv

from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential
from azure.ai.agents.models import ListSortOrder

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AzureAgentManager:
    """Manages interactions with Azure AI Foundry Agents."""
    
    def __init__(self, test_mode=False):
        """Initialize the Azure Agent Manager with credentials from environment variables."""
        # Get Azure credentials from environment
        tenant_id = os.getenv('AZURE_TENANT_ID')
        client_id = os.getenv('AZURE_CLIENT_ID') 
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        endpoint = os.getenv('AZURE_ENDPOINT')
        agent_id = os.getenv('AZURE_AGENT_ID')
        
        # Check if running in test mode
        self.test_mode = test_mode or os.getenv('TEST_MODE', '').lower() == 'true'
        
        # Validate required environment variables
        if not all([tenant_id, client_id, client_secret, endpoint, agent_id]):
            missing = [var for var, val in {
                'AZURE_TENANT_ID': tenant_id,
                'AZURE_CLIENT_ID': client_id,
                'AZURE_CLIENT_SECRET': client_secret,
                'AZURE_ENDPOINT': endpoint,
                'AZURE_AGENT_ID': agent_id
            }.items() if not val]
            
            if not self.test_mode:
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
            else:
                logger.warning(f"Missing environment variables in test mode: {', '.join(missing)}")
                # Set dummy values for testing
                tenant_id = tenant_id or "12345678-1234-1234-1234-123456789abc"
                client_id = client_id or "test_client_id"
                client_secret = client_secret or "test_client_secret"
                endpoint = endpoint or "https://test.endpoint.com"
                agent_id = agent_id or "test_agent_id"
        
        try:
            # Initialize Azure credentials
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Initialize AI Project Client
            self.project = AIProjectClient(
                credential=self.credential,
                endpoint=endpoint
            )
            
        except Exception as e:
            if not self.test_mode:
                raise
            else:
                logger.warning(f"Failed to initialize Azure clients in test mode: {e}")
                self.credential = None
                self.project = None
        
        # Agent ID
        self.agent_id = agent_id
        self._agent = None
        
        # User-thread mapping storage
        self.mapping_file = "user_thread_mapping.json"
        self.user_threads: Dict[str, str] = self._load_user_thread_mapping()
        
        # Thread safety lock for user-thread mapping operations
        self._mapping_lock = threading.Lock()
        
        # Current user context (will be set per request)
        self._current_user_id: Optional[str] = None
        
        logger.info(f"Initialized Azure Agent Manager for agent {agent_id} (test_mode: {self.test_mode})")
    
    async def _get_agent(self):
        """Get the agent instance, loading it if necessary."""
        if self.test_mode:
            # Return a mock agent in test mode
            class MockAgent:
                def __init__(self):
                    self.id = "test_agent_id"
                    self.name = "Test Agent"
                    self.model = "test-model"
                    self.instructions = "This is a test agent"
            
            self._agent = MockAgent()
            return self._agent
            
        if self._agent is None:
            self._agent = await asyncio.to_thread(
                self.project.agents.get_agent, self.agent_id
            )
        return self._agent
    
    def _load_user_thread_mapping(self) -> Dict[str, str]:
        """Load user-thread mapping from JSON file."""
        try:
            if os.path.exists(self.mapping_file):
                with open(self.mapping_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load user thread mapping: {e}")
        return {}
    
    def _save_user_thread_mapping_locked(self):
        """Save user-thread mapping to JSON file. Must be called with lock held."""
        try:
            with open(self.mapping_file, 'w') as f:
                json.dump(self.user_threads, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user thread mapping: {e}")
    
    async def clear_conversation(self, user_id: str) -> str:
        """
        Clear/reset the conversation for a user by creating a new thread.
        
        Args:
            user_id: User identifier
            
        Returns:
            str: Success message with new thread info
        """
        try:
            with self._mapping_lock:
                old_thread_id = self.user_threads.get(user_id, "None")
                
                # Remove old thread mapping
                if user_id in self.user_threads:
                    del self.user_threads[user_id]
                    self._save_user_thread_mapping_locked()
                    logger.info(f"Cleared old thread {old_thread_id} for user {user_id}")
            
            # Create new thread for user
            new_thread_id = await self._ensure_user_thread(user_id)
            
            return f"Conversation cleared successfully. Old thread: {old_thread_id}, New thread: {new_thread_id}"
            
        except Exception as e:
            error_msg = f"Failed to clear conversation: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def set_user_context(self, user_id: str):
        """Set the current user context for this request."""
        self._current_user_id = user_id
    
    def _get_user_id_hash(self) -> str:
        """Generate a unique user ID based on connection context.
        
        This method is kept for backward compatibility but is no longer used
        as user IDs are now generated per connection in the main server.
        """
        import time
        process_id = os.getpid()
        # Use a combination of process ID and current time for uniqueness
        unique_string = f"{process_id}_{int(time.time())}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    async def _ensure_user_thread(self, user_id: str) -> str:
        """Ensure user has a thread, create one if needed.
        
        Thread-safe implementation to prevent concurrent thread creation
        for the same user.
        """
        if not user_id:
            raise ValueError("User ID is required.")
        
        # Thread-safe check and creation
        with self._mapping_lock:
            # Double-check pattern: check again inside lock
            if user_id in self.user_threads:
                thread_id = self.user_threads[user_id]
                logger.info(f"Using existing thread {thread_id} for user {user_id}")
                return thread_id
            
            # If we reach here, user definitely doesn't have a thread
            logger.info(f"Creating new thread for user {user_id}")
        
        # Create new thread outside of lock to avoid blocking other operations
        try:
            if self.test_mode:
                # Mock thread creation
                import time
                thread_id = f"test_thread_{user_id}_{int(time.time())}"
            else:
                thread = await asyncio.to_thread(self.project.agents.threads.create)
                thread_id = thread.id
            
            # Save mapping with lock
            with self._mapping_lock:
                # Double-check again in case another request created thread concurrently
                if user_id not in self.user_threads:
                    self.user_threads[user_id] = thread_id
                    self._save_user_thread_mapping_locked()
                    logger.info(f"Created new thread {thread_id} for user {user_id}")
                    return thread_id
                else:
                    # Another request beat us to it, use their thread
                    existing_thread_id = self.user_threads[user_id]
                    logger.info(f"Race condition detected: using existing thread {existing_thread_id} for user {user_id}")
                    return existing_thread_id
            
        except Exception as e:
            logger.error(f"Failed to create thread for user {user_id}: {str(e)}")
            raise
    
    async def create_thread(self) -> str:
        """Create a new conversation thread."""
        try:
            thread = await asyncio.to_thread(self.project.agents.threads.create)
            self._current_thread_id = thread.id
            logger.info(f"Created thread: {thread.id}")
            return thread.id
        except Exception as e:
            logger.error(f"Failed to create thread: {str(e)}")
            raise
    
    async def send_message(self, message: str, user_id: str) -> str:
        """
        Send a message to the agent and get the response.
        Automatically uses the user's dedicated thread.
        
        Args:
            message: The message to send
            user_id: User identifier for thread isolation
        
        Returns:
            The agent's response
        """
        try:
            # Get user's dedicated thread
            thread_id = await self._ensure_user_thread(user_id)
            
            # Get agent
            agent = await self._get_agent()
            
            if self.test_mode:
                # Mock response in test mode
                return f"Mock response from {agent.name} for message: '{message}'"
            
            # Create message
            await asyncio.to_thread(
                self.project.agents.messages.create,
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Create and process run
            run = await asyncio.to_thread(
                self.project.agents.runs.create_and_process,
                thread_id=thread_id,
                agent_id=agent.id
            )
            
            if run.status == "failed":
                error_msg = f"Agent run failed: {run.last_error}"
                logger.error(error_msg)
                return error_msg
            
            # Get the latest messages
            messages = await asyncio.to_thread(
                self.project.agents.messages.list,
                thread_id=thread_id,
                order=ListSortOrder.DESCENDING
            )
            
            # Find the latest assistant message
            for msg in messages:
                if msg.role == "assistant" and msg.text_messages:
                    response = msg.text_messages[-1].text.value
                    logger.info(f"Agent response: {response[:100]}...")
                    return response
            
            return "No response received from agent."
            
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def list_messages(self, user_id: str) -> str:
        """
        List all messages in the user's thread.
        
        Args:
            user_id: User identifier for thread isolation
        
        Returns:
            Formatted string of all messages
        """
        try:
            # Check if user has a thread
            if user_id not in self.user_threads:
                return "No messages found. User has no active thread."
            
            thread_id = self.user_threads[user_id]
            
            if self.test_mode:
                # Mock messages in test mode
                return f"Mock messages for user {user_id} in thread {thread_id}:\nuser: Hello\nassistant: Mock response"
            
            messages = await asyncio.to_thread(
                self.project.agents.messages.list,
                thread_id=thread_id,
                order=ListSortOrder.ASCENDING
            )
            
            formatted_messages = []
            for message in messages:
                if message.text_messages:
                    content = message.text_messages[-1].text.value
                    formatted_messages.append(f"{message.role}: {content}")
            
            return "\n\n".join(formatted_messages) if formatted_messages else "No messages found in thread."
            
        except Exception as e:
            error_msg = f"Failed to list messages: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def get_agent_info(self) -> str:
        """Get information about the current agent."""
        try:
            agent = await self._get_agent()
            info = f"Agent ID: {agent.id}\n"
            info += f"Agent Name: {getattr(agent, 'name', 'N/A')}\n"
            info += f"Agent Model: {getattr(agent, 'model', 'N/A')}\n"
            if hasattr(agent, 'instructions') and agent.instructions:
                info += f"Instructions: {agent.instructions[:200]}...\n"
            return info
        except Exception as e:
            error_msg = f"Failed to get agent info: {str(e)}"
            logger.error(error_msg)
            return error_msg