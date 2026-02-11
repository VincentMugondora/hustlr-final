# AWS Bedrock Agent Integration for Hustlr

This directory contains the AWS Bedrock Agent integration for conversational AI in the Hustlr platform.

## Files

- `agent.py` - Main Bedrock Agent client with invoke_agent function
- `README.md` - This documentation file

## Setup

1. **Install Dependencies**:
   ```bash
   pip install boto3
   ```

2. **Configure AWS Credentials**:
   Set up AWS credentials using one of these methods:
   - AWS CLI: `aws configure`
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - IAM roles (for EC2/ECS)

3. **Environment Variables**:
   ```env
   AWS_REGION=us-east-1
   HUSTLR_AGENT_ID=your-bedrock-agent-id
   HUSTLR_AGENT_ALIAS_ID=TSTALIASID
   ```

## Usage

```python
from bedrock.agent import invoke_agent

# Invoke the agent
response = await invoke_agent(
    user_input="Find plumbers in downtown area",
    session_id="user123_session"
)

if response.success:
    print(f"Agent: {response.response}")
    if response.action_group:
        print(f"Action: {response.action_group}")
else:
    print(f"Error: {response.error_message}")
```

## Features

- **Secure Authentication**: Uses AWS IAM credentials
- **Error Handling**: Comprehensive error handling for AWS API calls
- **Structured Responses**: Returns parsed agent responses with metadata
- **Session Management**: Maintains conversation context
- **Logging**: Detailed logging for debugging and monitoring

## Agent Configuration

The HustlrAgent should be configured in AWS Bedrock with these action groups:
- `search_providers` - Search for service providers
- `create_booking` - Create new service bookings
- `register_provider` - Register new service providers

## Security Considerations

- Never commit AWS credentials to version control
- Use IAM roles with minimal required permissions
- Monitor API usage and costs
- Implement rate limiting in production