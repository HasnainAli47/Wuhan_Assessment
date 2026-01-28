"""
Message Broker Module - Central Communication Hub

EXPLANATION FOR VIVA:
=====================
The Message Broker is the heart of agent communication. It implements the 
Mediator Pattern - instead of agents knowing about each other, they only
know about the broker.

Why use a Message Broker?
1. Decoupling: Agents are independent; adding/removing agents is easy
2. Routing: Centralized logic for message routing
3. Reliability: Can implement retry, dead letter queues, etc.
4. Monitoring: Single point for logging and metrics
5. Scalability: Can be replaced with distributed brokers (RabbitMQ, Kafka)

This is similar to how real-world systems like Google Docs work:
- Components don't talk directly
- A central service coordinates all communication
- This allows for features like offline sync, conflict resolution, etc.
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

from .agent_base import Agent, AgentMessage, MessageType

logger = logging.getLogger(__name__)


class MessageBroker:
    """
    Central message routing and delivery system.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a Singleton pattern implementation - only one broker exists in the system.
    
    Key Responsibilities:
    1. Agent Registration: Keep track of all agents
    2. Message Routing: Deliver messages to the right agent
    3. Broadcasting: Send messages to multiple agents
    4. Request-Response: Track pending requests and match responses
    
    Architecture Pattern: Publish-Subscribe (Pub/Sub)
    - Publishers (agents) send messages
    - Subscribers (other agents) receive messages they're interested in
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - ensures only one broker instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the broker (only once due to Singleton)."""
        if self._initialized:
            return
            
        self._agents: Dict[str, Agent] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._message_log: List[Dict] = []
        self._subscribers: Dict[MessageType, List[str]] = {}
        self._running = False
        self._initialized = True
        
        logger.info("MessageBroker initialized")
    
    def register_agent(self, agent: Agent):
        """
        Register an agent with the broker.
        
        EXPLANATION FOR VIVA:
        ====================
        When an agent registers:
        1. It's added to the agent registry
        2. The broker reference is injected into the agent (Dependency Injection)
        3. The agent's capabilities are noted for routing
        
        This follows the Inversion of Control principle - the broker controls
        agent communication, not the agents themselves.
        """
        self._agents[agent.agent_id] = agent
        agent._message_broker = self
        
        # Auto-subscribe agent to its capable message types
        for capability in agent.get_capabilities():
            if capability not in self._subscribers:
                self._subscribers[capability] = []
            if agent.agent_id not in self._subscribers[capability]:
                self._subscribers[capability].append(agent.agent_id)
        
        logger.info(f"Agent registered: {agent.name} ({agent.agent_id})")
        logger.debug(f"Capabilities: {[c.value for c in agent.get_capabilities()]}")
    
    def unregister_agent(self, agent_id: str):
        """Remove an agent from the broker."""
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            # Remove from subscriber lists
            for capability in agent.get_capabilities():
                if capability in self._subscribers:
                    self._subscribers[capability] = [
                        a for a in self._subscribers[capability] if a != agent_id
                    ]
            del self._agents[agent_id]
            logger.info(f"Agent unregistered: {agent_id}")
    
    async def route_message(self, message: AgentMessage):
        """
        Route a message to its intended recipient(s).
        
        EXPLANATION FOR VIVA:
        ====================
        This is the core routing logic. It handles:
        1. Direct messages: To a specific agent by ID
        2. Broadcasts: To all agents (recipient="broadcast")
        3. Type-based routing: To agents that handle a message type
        
        The message is logged for debugging and audit trails.
        """
        # Log the message
        self._message_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message.to_dict()
        })
        
        logger.debug(f"Routing message: {message.type.value} from {message.sender} to {message.recipient}")
        
        # Handle response messages (correlate with pending requests)
        if message.type in [MessageType.RESPONSE, MessageType.ERROR]:
            if message.correlation_id and message.correlation_id in self._pending_requests:
                future = self._pending_requests.pop(message.correlation_id)
                if not future.done():
                    future.set_result(message)
                return
        
        # Handle broadcast messages
        if message.recipient == "broadcast":
            await self._broadcast(message)
            return
        
        # Handle direct messages
        if message.recipient in self._agents:
            await self._agents[message.recipient].receive_message(message)
            return
        
        # Handle type-based routing (find an agent that can handle this message type)
        if message.type in self._subscribers:
            handlers = self._subscribers[message.type]
            if handlers:
                # Route to the first available handler (could be load-balanced)
                target_agent_id = handlers[0]
                if target_agent_id in self._agents:
                    await self._agents[target_agent_id].receive_message(message)
                    return
        
        logger.warning(f"No handler found for message: {message.type.value}")
    
    async def _broadcast(self, message: AgentMessage):
        """
        Send a message to all registered agents.
        
        EXPLANATION FOR VIVA:
        ====================
        Broadcasting is useful for:
        1. System-wide notifications (e.g., shutdown)
        2. Real-time updates (e.g., document changes)
        3. State synchronization
        
        We use asyncio.gather for concurrent delivery - all agents
        receive the message in parallel, not sequentially.
        """
        tasks = [
            agent.receive_message(message)
            for agent_id, agent in self._agents.items()
            if agent_id != message.sender  # Don't send to self
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def request(
        self, 
        message: AgentMessage, 
        timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        """
        Send a request and wait for a response.
        
        EXPLANATION FOR VIVA:
        ====================
        This implements the Request-Response pattern on top of async messaging.
        
        How it works:
        1. Create a Future (a placeholder for a future result)
        2. Store it with the message ID as the key
        3. Send the message
        4. Wait for the Future to be resolved (when response arrives)
        5. Return the response
        
        The timeout prevents hanging if no response comes.
        
        This is crucial for operations that need immediate results,
        like user login (need to know if successful before proceeding).
        """
        # Create a future to wait for the response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[message.id] = future
        
        try:
            # Send the request
            await self.route_message(message)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {message.id}")
            self._pending_requests.pop(message.id, None)
            return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            self._pending_requests.pop(message.id, None)
            return None
    
    async def start_all_agents(self):
        """Start all registered agents."""
        self._running = True
        tasks = [agent.start() for agent in self._agents.values()]
        await asyncio.gather(*tasks)
        logger.info(f"Started {len(self._agents)} agents")
    
    async def stop_all_agents(self):
        """Stop all registered agents gracefully."""
        self._running = False
        tasks = [agent.stop() for agent in self._agents.values()]
        await asyncio.gather(*tasks)
        logger.info("All agents stopped")
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> List[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def get_message_log(self, limit: int = 100) -> List[Dict]:
        """Get recent message log for debugging."""
        return self._message_log[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get broker statistics.
        
        EXPLANATION FOR VIVA:
        ====================
        Monitoring and observability are crucial in distributed systems.
        These stats help with:
        1. Performance tuning
        2. Debugging issues
        3. Capacity planning
        """
        return {
            "total_agents": len(self._agents),
            "agents": list(self._agents.keys()),
            "pending_requests": len(self._pending_requests),
            "total_messages_processed": len(self._message_log),
            "subscribers": {
                msg_type.value: len(agents) 
                for msg_type, agents in self._subscribers.items()
            }
        }
