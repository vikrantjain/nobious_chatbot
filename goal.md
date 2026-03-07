The goal is to build a Chat Service as per design documented in docs/architecture.md file.

To achieve the goal Following needs to be done.
* Build a REST API service (chat service) in python flask that will receive query from client and return response to client.
* Build an agent using Langgraph and integrate the REST API with the agent.
* Build MCP server for account related tools access using FASTMCP. Convert API documented in ims_api.rest to tools. Don't convert auth api to tool.
* Integrate the agent with LLM, Memory and tools (Account MCP tools). 
* Build a cli for cloning github repo and creating/updating BM25S document index locally on filesystem to be used by document search mcp server. Note: currently document github repo is not available, it can be picked up from .env file
* Build MCP server for document search tools access, using FASTMCP
* Integrate the document search mcp server with the agent.
* Write tests for the mcp tools and test the mcp tools.
* Write tests for the chat service and test the service.
* Build a test client chat application that uses auth api as per example in ims_api.rest file to get the token and use that token for interaction with the chat service api. This will help user do manual testing and verification of the chat service.
