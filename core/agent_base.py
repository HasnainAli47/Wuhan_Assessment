"""
Agent Base Module - Foundation of the Agent-Based Architecture

EXPLANATION FOR VIVA:
=====================
This module defines the core Agent abstraction. In agent-based systems, an "agent" is an 
autonomous entity that:
1. Has its own state and behavior
2. Can communicate with other agents via messages
3. Can act independently and make decisions
4. Follows the Single Responsibility Principle (each agent handles one domain)

Key Concepts:
- AgentMessage: A structured message format for inter-agent communication
- MessageType: Enum defining the types of operations agents can perform
- Agent: Abstract base class that all specialized agents inherit from

This is similar to the Actor Model in concurrent computing, where actors (agents) 
communicate exclusively through asynchronous message passing.
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """
    Defines all possible message types in the system.
    
    EXPLANATION FOR VIVA:
    ====================
    Using an Enum ensures type safety and makes the code self-documenting.
    Each message type corresponds to a specific operation that agents can perform.
    This follows the Command Pattern - each message type represents a command.
    """
    
    # User Management Operations
    USER_REGISTER = "user_register"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_UPDATE_PROFILE = "user_update_profile"
    USER_GET_PROFILE = "user_get_profile"
    USER_DELETE = "user_delete"
    
    # Document Operations
    DOC_CREATE = "doc_create"
    DOC_READ = "doc_read"
    DOC_UPDATE = "doc_update"
    DOC_DELETE = "doc_delete"
    DOC_LIST = "doc_list"
    DOC_COLLABORATE = "doc_collaborate"
    DOC_TRACK_CHANGE = "doc_track_change"
    
    # Version Control Operations
    VERSION_CREATE = "version_create"
    VERSION_GET_HISTORY = "version_get_history"
    VERSION_REVERT = "version_revert"
    VERSION_COMPARE = "version_compare"
    VERSION_GET_CONTRIBUTIONS = "version_get_contributions"
    
    # System Messages
    RESPONSE = "response"
    ERROR = "error"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"


@dataclass
class AgentMessage:
    """
    Represents a message passed between agents.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a Data Transfer Object (DTO) that encapsulates all information 
    needed for inter-agent communication. Using @dataclass reduces boilerplate
    and provides automatic __init__, __repr__, and __eq__ methods.
    
    Fields:
    - id: Unique identifier for message tracking and correlation
    - type: The operation type (from MessageType enum)
    - sender: Which agent sent this message
    - recipient: Target agent (or "broadcast" for all)
    - payload: The actual data being transmitted
    - correlation_id: Links response to original request (for async communication)
    - timestamp: When the message was created (for ordering and debugging)
    - priority: Higher priority messages are processed first
    """
    
    type: MessageType
    sender: str
    recipient: str
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 0  # Higher = more important
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization (e.g., JSON)."""
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create message from dictionary (deserialization)."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data["type"]),
            sender=data["sender"],
            recipient=data["recipient"],
            payload=data["payload"],
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
            priority=data.get("priority", 0)
        )
    
    def create_response(self, payload: Dict[str, Any], success: bool = True) -> 'AgentMessage':
        """
        Create a response message correlated to this message.
        
        EXPLANATION FOR VIVA:
        ====================
        This implements the Request-Response pattern. The correlation_id links
        the response back to the original request, which is essential for 
        asynchronous communication where responses may arrive out of order.
        """
        return AgentMessage(
            type=MessageType.RESPONSE if success else MessageType.ERROR,
            sender=self.recipient,  # Response comes from the recipient
            recipient=self.sender,   # Goes back to the original sender
            payload=payload,
            correlation_id=self.id   # Link to original request
        )


class Agent(ABC):
    """
    Abstract Base Class for all Agents in the system.
    
    EXPLANATION FOR VIVA:
    ====================
    This follows the Template Method Pattern - it defines the skeleton of the 
    agent lifecycle, with concrete implementations providing specific behaviors.
    
    Key Design Decisions:
    1. Async-first design: All operations are async for non-blocking I/O
    2. Message queue: Each agent has its own inbox for received messages
    3. Handler registration: Agents register handlers for message types they care about
    4. Lifecycle management: start() and stop() methods for clean resource management
    
    The ABC (Abstract Base Class) ensures that all agents implement the required
    methods, enforcing a consistent interface across the system.
    """
    
    def __init__(self, agent_id: str, name: str):
        """
        Initialize the agent with identity and infrastructure.
        
        Args:
            agent_id: Unique identifier for this agent instance
            name: Human-readable name for logging and debugging
        """
        self.agent_id = agent_id
        self.name = name
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: Dict[MessageType, Callable] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._message_broker = None  # Will be set by MessageBroker
        
        logger.info(f"Agent initialized: {self.name} ({self.agent_id})")
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register a handler function for a specific message type.
        
        EXPLANATION FOR VIVA:
        ====================
        This implements the Observer Pattern combined with Strategy Pattern.
        - Observer: The agent observes (listens for) specific message types
        - Strategy: Different handlers (strategies) for different message types
        
        This decouples the message routing logic from the message handling logic,
        making it easy to add new operations without modifying existing code.
        """
        self._handlers[message_type] = handler
        logger.debug(f"Handler registered: {message_type.value} -> {handler.__name__}")
    
    async def receive_message(self, message: AgentMessage):
        """
        Add a message to this agent's inbox queue.
        
        EXPLANATION FOR VIVA:
        ====================
        Using a queue decouples message production from consumption.
        This is the Producer-Consumer pattern - messages are produced by other
        agents and consumed by this agent at its own pace.
        
        Benefits:
        1. Non-blocking: Sender doesn't wait for receiver to process
        2. Buffering: Handles bursts of messages gracefully
        3. Ordering: Messages are processed in FIFO order (can be extended to priority)
        """
        await self._message_queue.put(message)
        logger.debug(f"{self.name} received message: {message.type.value}")
    
    async def send_message(self, message: AgentMessage):
        """
        Send a message to another agent via the message broker.
        
        EXPLANATION FOR VIVA:
        ====================
        Agents don't communicate directly - they go through a message broker.
        This is the Mediator Pattern - the broker mediates all communication.
        
        Benefits:
        1. Decoupling: Agents don't need to know about each other
        2. Flexibility: Can add logging, monitoring, routing logic in the broker
        3. Scalability: Broker can be replaced with a distributed message queue
        """
        if self._message_broker:
            await self._message_broker.route_message(message)
        else:
            logger.error(f"{self.name}: No message broker configured!")
    
    async def _process_messages(self):
        """
        Main message processing loop.
        
        EXPLANATION FOR VIVA:
        ====================
        This is the agent's "brain" - it continuously:
        1. Waits for messages in its queue
        2. Finds the appropriate handler
        3. Executes the handler
        4. Sends any response back
        
        The try-except ensures one bad message doesn't crash the entire agent.
        This is crucial for system reliability.
        """
        while self._running:
            try:
                # Wait for a message with timeout to allow clean shutdown
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue  # Check if still running and continue
                
                # Find and execute the appropriate handler
                handler = self._handlers.get(message.type)
                if handler:
                    try:
                        result = await handler(message)
                        if result and isinstance(result, AgentMessage):
                            await self.send_message(result)
                    except Exception as e:
                        logger.error(f"Handler error in {self.name}: {e}")
                        # Send error response back
                        error_response = message.create_response(
                            {"error": str(e), "success": False},
                            success=False
                        )
                        await self.send_message(error_response)
                else:
                    logger.warning(f"{self.name}: No handler for {message.type.value}")
                    
            except Exception as e:
                logger.error(f"Message processing error in {self.name}: {e}")
    
    async def start(self):
        """
        Start the agent's message processing loop.
        
        EXPLANATION FOR VIVA:
        ====================
        Creates an asyncio Task for the message processing loop.
        Tasks are like lightweight threads managed by the event loop.
        """
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_messages())
            await self.on_start()
            logger.info(f"Agent started: {self.name}")
    
    async def stop(self):
        """
        Gracefully stop the agent.
        
        EXPLANATION FOR VIVA:
        ====================
        Clean shutdown is important to:
        1. Finish processing current messages
        2. Release resources (connections, file handles)
        3. Notify other components of shutdown
        """
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            await self.on_stop()
            logger.info(f"Agent stopped: {self.name}")
    
    @abstractmethod
    async def on_start(self):
        """Called when agent starts - subclasses implement initialization."""
        pass
    
    @abstractmethod
    async def on_stop(self):
        """Called when agent stops - subclasses implement cleanup."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[MessageType]:
        """Return list of message types this agent can handle."""
        pass
