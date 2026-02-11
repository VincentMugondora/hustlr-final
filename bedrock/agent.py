"""
AWS Bedrock Agent integration for Hustlr.
Handles conversational AI interactions with the HustlrAgent for service marketplace queries.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from botocore.exceptions import BotoCoreError, ClientError
import boto3
from boto3 import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Structured response from Bedrock Agent."""
    success: bool
    response: Optional[str] = None
    action_group: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None


class BedrockAgentClient:
    """
    Client for interacting with AWS Bedrock Agent.
    Handles authentication, session management, and error handling.
    """

    def __init__(self):
        """
        Initialize Bedrock client with AWS credentials and configuration.
        """
        self.agent_id = os.getenv("HUSTLR_AGENT_ID")
        self.agent_alias_id = os.getenv("HUSTLR_AGENT_ALIAS_ID", "TSTALIASID")  # Default to test alias
        self.region = os.getenv("AWS_REGION", "us-east-1")

        if not self.agent_id:
            raise ValueError("HUSTLR_AGENT_ID environment variable is required")

        try:
            # Create boto3 session with proper credentials
            session = Session()
            self.client = session.client(
                service_name="bedrock-agent-runtime",
                region_name=self.region
            )
            logger.info(f"✅ Bedrock Agent client initialized for region: {self.region}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Bedrock client: {e}")
            raise

    async def invoke_agent(
        self,
        user_input: str,
        session_id: str,
        enable_trace: bool = False
    ) -> AgentResponse:
        """
        Invoke the HustlrAgent with user input and return structured response.

        Args:
            user_input: The user's message or query
            session_id: Unique session identifier for conversation continuity
            enable_trace: Whether to include trace information in response

        Returns:
            AgentResponse: Structured response containing agent output and metadata

        Raises:
            ValueError: If input parameters are invalid
            RuntimeError: If agent invocation fails
        """
        if not user_input or not user_input.strip():
            raise ValueError("user_input cannot be empty")

        if not session_id or not session_id.strip():
            raise ValueError("session_id cannot be empty")

        try:
            # Prepare the request payload
            request_payload = {
                "inputText": user_input.strip(),
                "enableTrace": enable_trace
            }

            logger.info(f"🤖 Invoking HustlrAgent with session: {session_id}")

            # Invoke the Bedrock agent
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=user_input
            )

            # Process the streaming response
            return await self._process_streaming_response(response, session_id)

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', 'Unknown error')

            logger.error(f"❌ AWS ClientError [{error_code}]: {error_message}")

            if error_code == 'ResourceNotFoundException':
                return AgentResponse(
                    success=False,
                    error_message="HustlrAgent not found. Please check agent configuration.",
                    session_id=session_id
                )
            elif error_code == 'ThrottlingException':
                return AgentResponse(
                    success=False,
                    error_message="Service is temporarily unavailable. Please try again later.",
                    session_id=session_id
                )
            else:
                return AgentResponse(
                    success=False,
                    error_message=f"Agent invocation failed: {error_message}",
                    session_id=session_id
                )

        except BotoCoreError as e:
            logger.error(f"❌ BotoCoreError: {e}")
            return AgentResponse(
                success=False,
                error_message="Network or authentication error occurred",
                session_id=session_id
            )

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return AgentResponse(
                success=False,
                error_message="An unexpected error occurred",
                session_id=session_id
            )

    async def _process_streaming_response(
        self,
        response: Dict[str, Any],
        session_id: str
    ) -> AgentResponse:
        """
        Process the streaming response from Bedrock Agent.

        Args:
            response: Raw response from invoke_agent
            session_id: Session identifier

        Returns:
            AgentResponse: Processed structured response
        """
        try:
            response_text = ""
            action_group = None
            parameters = {}

            # Process the streaming response
            stream = response.get("completion", {})
            if stream:
                for event in stream:
                    chunk = event.get("chunk", {})
                    if chunk:
                        response_text += chunk.get("bytes", b"").decode("utf-8")

                    # Check for action group invocations
                    trace = event.get("trace", {})
                    if trace:
                        action_group_data = trace.get("actionGroupInvocation", {})
                        if action_group_data:
                            action_group = action_group_data.get("actionGroupName")
                            parameters = action_group_data.get("parameters", {})

            # Parse the response for structured data
            parsed_response = self._parse_agent_response(response_text)

            return AgentResponse(
                success=True,
                response=parsed_response.get("message", response_text),
                action_group=action_group,
                parameters=parameters,
                session_id=session_id
            )

        except Exception as e:
            logger.error(f"❌ Error processing streaming response: {e}")
            return AgentResponse(
                success=False,
                error_message="Failed to process agent response",
                session_id=session_id
            )

    def _parse_agent_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the agent's response text for structured data.

        Args:
            response_text: Raw response text from agent

        Returns:
            Dict containing parsed response data
        """
        try:
            # Attempt to parse as JSON if the response is structured
            if response_text.strip().startswith("{"):
                return json.loads(response_text)
            else:
                return {"message": response_text}
        except json.JSONDecodeError:
            # Return as plain text if not JSON
            return {"message": response_text}


# Global client instance
_agent_client: Optional[BedrockAgentClient] = None


def get_bedrock_client() -> BedrockAgentClient:
    """
    Get or create the global Bedrock agent client instance.

    Returns:
        BedrockAgentClient: Configured client instance
    """
    global _agent_client
    if _agent_client is None:
        _agent_client = BedrockAgentClient()
    return _agent_client


async def invoke_agent(user_input: str, session_id: str) -> AgentResponse:
    """
    Convenience function to invoke the HustlrAgent.

    This is the main entry point for backend services to interact with the AI agent.

    Args:
        user_input: The user's message or query
        session_id: Unique session identifier for conversation continuity

    Returns:
        AgentResponse: Structured response from the agent

    Example:
        response = await invoke_agent("Find plumbers in downtown", "user123")
        if response.success:
            print(f"Agent response: {response.response}")
        else:
            print(f"Error: {response.error_message}")
    """
    client = get_bedrock_client()
    return await client.invoke_agent(user_input, session_id)