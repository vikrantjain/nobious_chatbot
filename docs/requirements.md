# Context
Nobious is a cloud-based multi-tenant inventory management system.
Customers can access the system via web or mobile application.
An AI Chat interface is required for the application.

# Requirements

## 1. Functional Requirements

### 1.1 Chat Interface
- Chat application must be embedded within mobile and web applications
- Users must authenticate via existing login mechanism to access chat interface
- System must accept questions in plain language (natural language input)
- System must respond with answers in plain English

### 1.2 Question Types

#### 1.2.1 General Questions
- Users can ask general questions about Nobious product/features
- Answers must be sourced from Nobious documentation
- No access restrictions apply to general questions
- All authenticated users can access general information

#### 1.2.2 Account-Specific Questions
- Users can ask questions related to their account data
- Answers must be based on data accessible to the user's account
- System must enforce tenant isolation (multi-tenant data separation)
- System must respect existing user permissions and access controls

### 1.3 Session Management
- Chat session is active only while user is logged in and authentication token is valid
- Chat session history will NOT be stored persistently
- When session ends (logout or token expiry), conversation history is discarded

### 1.4 Context Understanding
- System must understand the context of questions
- System must maintain conversation context within the active session only
- Maximum of 3 previous messages (user questions and system responses) will be considered for context
- If a question cannot be understood within the available context, system may ask clarifying questions

### 1.5 Response Handling
- System must provide relevant answers based on question type
- System must indicate when it cannot answer a question
- System must NOT answer questions outside the domain (Nobious product/features or user's account data)
- For out-of-domain questions, system must respond with: "I don't have information about the subject"
- When data is not found within the domain, system must simply state that data was not found
- System must NOT suggest alternative questions or clarifications, except when asking clarifying questions for ambiguous queries
- No escalation to human support is required

## 2. Security & Access Control

### 2.1 Authentication & Authorization
- Users must be authenticated before accessing chat
- System must validate user identity for each request
- Account-specific queries must enforce row-level security based on tenant/user permissions

### 2.2 Data Privacy
- Chat conversations may contain sensitive inventory data
- System must not expose data from other tenants
- System must not allow privilege escalation through chat queries
- Chat history is not persisted beyond the active session
- System must comply with GDPR, HIPAA, and SOC2 requirements
- PII (Personally Identifiable Information) may be logged in application logs
- Audit logging is NOT required for account-specific queries
- No data residency requirements - all customers are US-based and data/application hosted in US
- Application logs are rotated every 15 days
- Logs containing PII are accessible only to authenticated development team members

## 3. Performance Requirements

- Maximum response time for queries: 5-10 seconds
- System must support up to 25 concurrent users
- Expected query volume: Maximum 25 queries per minute
- Rate limit: Maximum 3 queries per user per minute

## 4. User Experience

### 4.1 Conversation Flow
- System must support back-and-forth conversation
- Users must be able to ask follow-up questions
- Typing indicators are NOT required
- Message delivery status is NOT required
- Users cannot edit or delete sent messages
- File and image attachments are NOT supported
- Maximum character limit for questions: 200 characters (configurable)
- Voice input/output is NOT supported
- System provides plain text responses only - no data visualizations

### 4.2 Language Support
- System must respond in plain English only
- No other languages are supported

### 4.3 Chat History
- Chat history is available only during the active session
- No persistent storage of conversation history
- History is cleared when user logs out or token expires
- Users cannot export conversation history
- No warning before session expiry

### 4.4 Response Formatting
- All responses must use plain text format
- Dates must be formatted as: MM/DD/YYYY (e.g., "01/15/2024")
- Currency must be formatted as: $X,XXX.XX (e.g., "$1,234.56")
- Quantities such as liters, feet, meters, gallons, etc. can be entered with decimals.
- Entity references must include type (e.g., "Order #12345", "Product SKU-001")
- Multiple items must be presented as numbered or bulleted lists
- For large result sets, limit to first 5-10 items with count (e.g., "Showing 5 of 23 results")
- Empty results must use clear messaging (e.g., "No pending orders found")
- Status values must use consistent terminology (e.g., "Pending", "Shipped", "Delivered")

## 5. Scope & Boundaries

### 5.1 Capabilities
- System is READ-ONLY - no write operations supported
- System must answer questions based on existing data
- Users cannot perform transactional operations (create, update, delete) through chat
- System can perform calculations and aggregations on retrieved data for answers
- System must only answer questions within domain: Nobious product/features and user's account data
- Questions outside this domain must be rejected with standard response
- When users request write operations, system must respond with: "I cannot do writes, for this you need to access the web or mobile application"
- System may optionally suggest which section in the web or mobile application can be used to perform the requested write operation

### 5.2 Data Sources
- General questions: Nobious documentation
- Account questions: User's accessible inventory data
- Queryable data entities: Products, Orders, Warehouses, Locations, Items, Receipts, Tickets, Vendors
- System must use real-time data (no caching)

## 6. Integration Requirements

- Chat system integrates with inventory system via APIs
- Chat must use existing authentication token to validate user identity and access permissions
- User's existing auth token is passed to inventory APIs for authorization
- No API rate limits currently exist on inventory system APIs
- Webhooks and real-time notifications are NOT required

## 7. Quality & Reliability

- Response accuracy must be at least 70%
- Chat availability and uptime depends on main web/mobile application availability
- Service degradation handling: Fail fast approach
  - If AI service or inventory APIs are unavailable, system must respond with: "Chat is temporarily unavailable. Please try again later."
  - No fallback mechanisms or partial functionality during service degradation
- Monitoring and alerting is handled by main web/mobile application infrastructure
- Chat system must log data for monitoring purposes

## 8. Constraints & Assumptions

### 8.1 Assumptions
- Users are already authenticated in the mobile/web application
- Existing permission system is available for authorization checks
- Nobious documentation is available in a queryable format

### 8.2 Constraints
- All customers are US-based
- Data and application must be hosted in US
- Budget constraints exist - chat is provided as a free additional feature to customers
- Solution must be cost-effective for AI/LLM API usage
- Mobile UI is built using React
- Web UI is built using Angular
- Solution must be deployed on AWS