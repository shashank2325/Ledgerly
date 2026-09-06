# Ledgerly — Personal Finance Data Platform

## 1. Project Overview

Ledgerly is an internal codename for a personal finance tracking and financial analytics application.

The initial goal is to build this primarily for personal use. It may eventually be shared with a small circle of trusted friends/family, but large-scale public commercialization, multi-tenancy, and enterprise-scale infrastructure are NOT requirements for the initial version.

The application should allow users to connect their bank and credit-card accounts through Plaid, automatically ingest financial transactions, store the data in an AWS-based data platform, normalize and enrich the transactions, identify transfers between the user's own accounts, categorize spending, and provide a clean web dashboard for understanding personal finances.

The system should be designed so that the underlying financial data belongs to the user and the application maintains a durable historical record of the data.

The core philosophy is:

> Financial data should be treated as a user's own data asset, not merely as records displayed by a budgeting application.

The system should therefore maintain a raw source layer, a curated analytical layer, and derived financial analytics.

The initial system should be serverless and AWS-native.

Do NOT introduce EC2, ECS, EKS, RDS, Redis, Kafka, microservices, or other continuously running infrastructure unless there is a concrete requirement for them.

The architecture should remain simple enough for a single developer to operate.

---

# 2. Primary Goals

The application should eventually provide:

1. Bank account connectivity through Plaid.
2. Credit-card connectivity through Plaid.
3. Automatic transaction synchronization.
4. Historical transaction ingestion.
5. Incremental transaction synchronization.
6. Pending → posted transaction handling.
7. Transaction updates and deletions.
8. Transaction normalization.
9. Merchant normalization.
10. User-defined transaction categorization.
11. Transfer detection.
12. Transfer pairing/reconciliation.
13. Income detection.
14. Expense detection.
15. Cash-flow analysis.
16. Spending analysis.
17. Net-worth tracking.
18. Account balances.
19. Account-level transaction history.
20. Category-level spending.
21. Monthly financial summaries.
22. Search and filtering.
23. Date-range analysis.
24. Historical analytics.
25. User-defined rules.
26. Dashboard visualizations.
27. Secure authentication.
28. Secure storage of Plaid credentials/tokens.
29. Infrastructure-as-Code using Terraform.
30. Fully serverless AWS infrastructure.
31. Analytical storage using Apache Iceberg.
32. S3 as the underlying data lake.
33. Athena as the primary analytical query engine.
34. Glue Data Catalog for table metadata.
35. CloudFront for frontend delivery.
36. Lambda-based Python backend.
37. DynamoDB for operational application state.
38. Event-driven transaction synchronization.
39. Low AWS operating cost.
40. Ability to scale the architecture later if actual usage justifies it.

---

# 3. Development Philosophy

The developer building this application is significantly stronger on backend, AWS, data engineering, and data-platform architecture than frontend development.

The developer has strong experience with:

- Python
- AWS Lambda
- Amazon S3
- AWS Glue
- Amazon Athena
- Apache Iceberg
- Data pipelines
- ETL/ELT
- Serverless architectures
- Terraform
- Cloud infrastructure
- Data modeling
- Open table formats
- AWS data services

The developer is comparatively inexperienced with frontend development.

Therefore:

## Backend/data architecture

Be sophisticated and production-quality where appropriate.

Prefer:

- Clean data models
- Strong schemas
- Idempotent pipelines
- Event-driven architecture
- Incremental processing
- Proper data lineage
- Immutable raw data
- Curated analytical tables
- Iceberg
- Parquet
- Partition pruning
- Metadata pruning
- Efficient Athena queries
- Terraform
- AWS-native services

## Frontend

Keep it simple.

Use a modern but approachable frontend stack such as:

- React
- TypeScript
- Tailwind CSS

Avoid unnecessarily complicated frontend frameworks or state-management systems unless they provide clear value.

The frontend should consume clean backend APIs.

The frontend should NOT contain financial business logic that belongs in the backend/data layer.

The frontend should primarily:

- Display data
- Collect user input
- Send API requests
- Display loading/error states
- Render charts/tables
- Provide filtering
- Provide navigation

The backend should remain the source of truth for financial calculations and business rules.

---

# 4. Initial AWS Architecture

The initial architecture should be:

Internet
→ CloudFront
→ S3 for frontend assets

and:

Frontend
→ CloudFront
→ API Gateway
→ Lambda
→ DynamoDB / S3 / Athena / Plaid

The analytical data architecture should be:

Plaid
→ Lambda
→ S3 Raw
→ Transformation
→ Iceberg tables on S3
→ Glue Data Catalog
→ Athena
→ API/dashboard

Conceptually:

                    ┌──────────────────┐
                    │     Browser      │
                    │ React + TS + UI  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   CloudFront     │
                    └────────┬─────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
             S3 Frontend            API Gateway
                                         │
                                         ▼
                                     Lambda/Python
                                         │
                 ┌───────────────────────┼──────────────────────┐
                 │                       │                      │
                 ▼                       ▼                      ▼
             DynamoDB                  Plaid                   S3
          operational state          API/banks               raw data
                                                                 │
                                                                 ▼
                                                          Iceberg tables
                                                                 │
                                                                 ▼
                                                           Glue Catalog
                                                                 │
                                                                 ▼
                                                              Athena
                                                                 │
                                                                 ▼
                                                            Analytics


---

# 5. AWS Services

## Amazon S3

S3 is the foundational storage layer.

Use S3 for:

- Raw Plaid responses/events
- Immutable source data
- Curated Parquet/Iceberg data
- Analytical datasets
- Frontend static assets
- Potential exports/backups

The S3 data lake should have clear separation between raw, curated, and analytical data.

Possible conceptual structure:

s3://ledgerly-data/

    raw/
        plaid/
            items/
            accounts/
            transactions/

    curated/
        transactions/
        accounts/
        merchants/

    analytics/
        monthly_spending/
        monthly_income/
        cash_flow/
        net_worth/

The exact S3 layout should be finalized during implementation based on Iceberg requirements.

Raw data should be retained independently from transformed data whenever practical.

---

# 6. Apache Iceberg

Apache Iceberg should be the primary analytical table format.

Do NOT treat the data lake as simply a collection of independent Parquet files.

Use Iceberg tables for structured analytical datasets.

Initial primary table:

finance.transactions

Potential future tables:

finance.accounts
finance.institutions
finance.merchants
finance.categories
finance.transfer_groups
finance.monthly_spending
finance.monthly_income
finance.cash_flow
finance.net_worth
finance.recurring_transactions

Iceberg should provide:

- ACID table operations
- Schema evolution
- Partition evolution
- Snapshot history
- Time travel
- Reliable incremental updates
- Metadata-based pruning
- Separation between physical storage and logical table definitions

The system should preserve raw financial data so that derived tables can be rebuilt if business rules change.

---

# 7. Partitioning and Data Layout

Partitioning should be deliberately designed based on expected query patterns.

Do NOT create excessive partitions.

Do NOT automatically partition by every dimension.

The initial transaction table will likely be partitioned by transaction date, for example:

year(transaction_date)
month(transaction_date)

The exact Iceberg partition specification should be evaluated during implementation.

The most common queries are expected to be:

- Current month
- Previous month
- Last 30 days
- Last 90 days
- Specific year
- Specific date range
- Account-specific historical transactions
- Category-specific spending
- Monthly summaries

Date-based partitioning should therefore be strongly considered.

Potential ordering/sorting strategies may include:

transaction_date
account_id
transaction_id

but should be evaluated based on actual access patterns.

The system should avoid small-file problems.

If ingestion creates many small Parquet files, introduce compaction/maintenance rather than allowing the table to degrade.

The architecture should consider:

- File size
- Compression
- Compaction
- Partition pruning
- Predicate pushdown
- Iceberg metadata pruning
- Athena scanned-data costs

Do not optimize prematurely, but establish a good foundation.

---

# 8. Athena

Amazon Athena should be the primary analytical query engine.

Athena should be used for:

- Historical analytics
- Spending analysis
- Income analysis
- Cash-flow analysis
- Category aggregation
- Monthly reports
- Long-range queries
- Ad-hoc financial analysis

Do NOT use Athena as a replacement for DynamoDB for every interactive request.

For example:

"Give me the user's current Plaid sync cursor"

should use DynamoDB.

"Give me the last 50 transactions"

may use DynamoDB or a carefully designed serving layer.

"How much did I spend on restaurants between January 2024 and September 2026?"

should use Athena/Iceberg.

The application should avoid unnecessarily scanning the entire historical dataset.

Use:

- Partition pruning
- Column pruning
- Parquet
- Iceberg metadata pruning
- Appropriate filters
- Pre-aggregated analytical tables where useful

---

# 9. Glue Data Catalog

AWS Glue Data Catalog should be used as the metadata/catalog layer for the Iceberg tables.

Example conceptual namespace:

finance.transactions
finance.accounts
finance.merchants
finance.categories
finance.transfer_groups

Athena should query these tables.

The implementation should keep catalog/table definitions reproducible through Terraform where possible.

---

# 10. DynamoDB

DynamoDB should be used for operational state.

Do NOT use DynamoDB as the primary analytical store.

Potential DynamoDB entities:

- Plaid Items
- Plaid access-token references
- Sync cursors
- Accounts
- User preferences
- Category configuration
- Categorization rules
- Application configuration
- Recent transaction serving data
- User metadata

Example conceptual objects:

PlaidItem:

    item_id
    institution_id
    institution_name
    access_token_reference
    sync_cursor
    last_sync_at
    status

Account:

    account_id
    item_id
    name
    type
    subtype
    mask
    current_balance
    available_balance

Rule:

    rule_id
    condition
    category
    priority
    enabled

Do not expose Plaid access tokens to the frontend.

---

# 11. Plaid Integration

Plaid is the external financial-data provider.

The system should use Plaid Link for account connection.

The backend should securely handle:

- Link token creation
- Public-token exchange
- Access-token storage
- Item management
- Account retrieval
- Transaction synchronization
- Webhook handling
- Transaction refresh when necessary

Plaid access tokens must remain server-side.

Never send Plaid access tokens to the browser.

Use AWS Secrets Manager or an appropriately secured server-side storage mechanism for sensitive credentials.

---

# 12. Transaction Synchronization

Use Plaid's transaction synchronization architecture.

Prefer:

/transactions/sync

for incremental synchronization.

Do not repeatedly download the entire historical transaction set.

The first synchronization should establish the historical baseline.

Subsequent synchronizations should use the stored cursor.

Conceptually:

Initial:

Plaid
→ historical transactions
→ Lambda
→ raw S3
→ normalized Iceberg

Subsequent:

Plaid
→ new/modified/removed transactions
→ Lambda
→ update pipeline
→ Iceberg

Store the sync cursor securely.

The synchronization process must be idempotent.

Running the same synchronization twice should not create duplicate financial transactions.

---

# 13. Plaid Webhooks

Support the appropriate Plaid transaction webhook events.

A transaction availability event should trigger the backend to synchronize transactions.

Conceptually:

Plaid
→ webhook
→ API Gateway
→ Lambda
→ /transactions/sync
→ S3
→ Iceberg

EventBridge may also be used for scheduled synchronization/reconciliation.

The system should not assume webhooks are perfectly reliable.

Periodic reconciliation should be considered.

---

# 14. Pending Transactions

Pending transactions require special handling.

A pending transaction may later become a posted transaction.

The system must not blindly treat every incoming transaction event as a brand-new transaction.

The data model should support:

- Pending status
- Posted status
- Transaction replacement
- Transaction updates
- Transaction removal
- Stable transaction identity
- Historical audit information where useful

The ingestion pipeline should be idempotent.

---

# 15. Raw Data Layer

The raw layer should preserve source information from Plaid.

Raw data should ideally be append-only or immutable.

Example:

raw/plaid/transactions/

The raw layer is the source of truth for ingestion.

Do not destroy raw data merely because a transaction has been transformed.

The purpose is to make the system recoverable.

If the categorization algorithm changes six months later, we should be able to rebuild derived data from the raw/normalized layer.

---

# 16. Normalized Transaction Model

The normalized transaction model should be independent of Plaid's exact representation where possible.

Potential fields:

transaction_id
account_id
item_id
transaction_date
authorized_date
amount
currency
merchant_name
merchant_id
description
plaid_category
plaid_category_id
payment_channel
pending
status

Application-derived fields:

normalized_merchant
category
subcategory
is_income
is_expense
is_transfer
transfer_group_id
is_recurring
user_note
created_at
updated_at

Do not assume all fields will always be populated.

The schema should tolerate missing/null values.

---

# 17. Transfer Detection

Transfer detection is one of the most important features.

The application should NOT treat movement of money between a user's own accounts as income or expense.

Example:

Checking:

-$2,000

Savings:

+$2,000

The system should recognize these as:

TRANSFER

rather than:

Expense: $2,000
Income: $2,000

A transfer should ideally be represented using a transfer group:

transfer_group_id = XYZ

with:

transaction A:
    account = checking
    amount = -2000

transaction B:
    account = savings
    amount = +2000

Both:

is_transfer = true
transfer_group_id = XYZ

The transfer logic should consider:

- Amount
- Date
- Opposite signs
- Accounts
- Merchant/description
- Institution
- Transfer-related transaction metadata
- Credit-card payments
- Internal bank transfers

The system should allow manual correction when automatic matching is wrong.

---

# 18. Credit Card Payments

Credit-card payments should be treated carefully.

For example:

Checking:

-$1,500

Credit Card:

+$1,500

This is not:

-$1,500 spending

It is a transfer/payment between the user's accounts.

The actual expenses occurred when the credit-card transactions happened.

Therefore:

Credit-card purchase:
    Expense

Credit-card payment:
    Transfer

This distinction should be reflected throughout:

- Spending reports
- Income reports
- Cash flow
- Net worth
- Category analytics

---

# 19. Income vs Expense vs Transfer

The system should distinguish:

INCOME
EXPENSE
TRANSFER
REFUND
ADJUSTMENT
UNKNOWN

The exact taxonomy can evolve.

The key requirement is that financial reporting should not double-count transfers.

For example:

Income:

+$7,500 salary

Expenses:

-$3,500 actual spending

Transfers:

-$2,000 checking → savings

Net spending should remain:

$3,500

not:

$5,500.

---

# 20. Categorization

The system should support both:

1. Plaid-provided categories
2. User-defined categories

The user should be able to override Plaid's category.

Potential hierarchy:

Food
    Restaurants
    Groceries
    Coffee

Transportation
    Uber
    Metro
    Gas

Housing
    Rent
    Utilities

Shopping
    Amazon
    Clothing
    Electronics

etc.

The exact categories should remain configurable.

---

# 21. User Rules

Eventually support rules such as:

If merchant = Amazon
→ category = Shopping

If merchant contains "Whole Foods"
→ category = Groceries

If transaction matches known transfer pattern
→ is_transfer = true

Rules should have:

- Priority
- Enabled/disabled state
- Conditions
- Actions

Rules should be applied deterministically.

---

# 22. Merchant Normalization

Different transactions may contain variations of the same merchant.

For example:

AMZN Mktp US*1234
Amazon Marketplace
AMAZON.COM

These may all represent:

Amazon

Create a normalized merchant concept.

Potential model:

merchant_id
canonical_name
logo/reference
aliases
category

Merchant normalization should remain separate from raw Plaid merchant information.

---

# 23. Dashboard

The initial dashboard should be simple and useful.

Potential sections:

## Net Worth

Current:

$XXX,XXX

Change this month:

+$X,XXX

## Income

This month:

$X,XXX

## Spending

This month:

$X,XXX

## Cash Flow

Income - Expenses

## Spending by Category

Example:

Housing       $1,500
Food            $680
Shopping        $420
Transportation  $240

## Recent Transactions

Show the latest transactions.

---

# 24. Transactions Page

The transactions page should support:

- Date
- Merchant
- Amount
- Account
- Category
- Pending/posted
- Transfer indicator
- Search
- Date filtering
- Account filtering
- Category filtering
- Income/expense/transfer filtering

Clicking a transaction should show more details.

The UI should remain clean and simple.

---

# 25. Accounts Page

Display:

- Institution
- Account name
- Account type
- Masked account number
- Current balance
- Available balance where appropriate
- Last synced timestamp

Potential account types:

- Checking
- Savings
- Credit Card
- Investment
- Loan
- Other

Investment/loan support can initially be limited.

---

# 26. Analytics

Future analytics should include:

- Monthly spending
- Monthly income
- Net cash flow
- Spending by category
- Spending by merchant
- Account balances
- Net worth over time
- Year-over-year spending
- Monthly comparisons
- Recurring expenses
- Subscription detection

Analytics should preferably be based on curated/derived Iceberg tables rather than repeatedly scanning the raw transaction table for every dashboard request.

---

# 27. Derived Tables

Potential derived tables:

finance.monthly_spending

Columns:

month
category
amount
transaction_count

finance.monthly_income

Columns:

month
income_type
amount

finance.cash_flow

Columns:

month
income
expenses
transfers
net_cash_flow

finance.net_worth

Columns:

date
assets
liabilities
net_worth

finance.transfer_groups

Columns:

transfer_group_id
source_transaction_id
destination_transaction_id
amount
confidence
matched_at

These are examples, not requirements that must all be implemented immediately.

---

# 28. Frontend Technology

Use:

React
TypeScript
Tailwind CSS

The frontend should be intentionally simple.

Do not build a complicated frontend architecture.

Avoid introducing:

- Redux unless necessary
- Complex state machines
- Micro-frontends
- Overly elaborate component systems
- Unnecessary frontend infrastructure

A simple component hierarchy is preferred.

Example:

frontend/

    src/
        components/
        pages/
        hooks/
        api/
        types/
        utils/

Use reusable components where they clearly help.

---

# 29. Frontend Design Inspiration

The UI can take inspiration from modern personal-finance applications such as Monarch, YNAB, Copilot, etc.

Use these products to understand:

- Feature organization
- Dashboard patterns
- Transaction-table UX
- Filtering
- Navigation
- Charts
- Account views
- Budget views
- Financial summaries

Do NOT copy proprietary source code, assets, branding, or exact designs.

The goal is to build an original UI inspired by established usability patterns.

The frontend can be iteratively vibe-coded.

The developer is not a frontend expert, so prioritize:

- Clarity
- Maintainability
- Simplicity
- Good defaults
- Responsive layout
- Accessible controls
- Minimal configuration

---

# 30. API Design

Use a clean REST-style API initially.

Potential endpoints:

POST /plaid/link-token

POST /plaid/exchange-token

POST /plaid/webhook

GET /accounts

GET /accounts/{account_id}

GET /transactions

GET /transactions/{transaction_id}

PATCH /transactions/{transaction_id}

GET /categories

GET /rules

POST /rules

PATCH /rules/{rule_id}

GET /dashboard

GET /cash-flow

GET /net-worth

GET /analytics/spending

GET /analytics/income

POST /sync

The exact API design should evolve based on implementation.

Keep the API contract independent of the underlying infrastructure.

The frontend should not care whether the backend runs on Lambda today or ECS in the future.

---

# 31. Authentication

The application should eventually use Amazon Cognito for authentication.

Initial personal development can be simplified if appropriate, but production-like authentication should eventually exist before sharing with other users.

Never rely on frontend-only authorization.

Backend APIs must validate authenticated identity.

---

# 32. Security

Financial data is sensitive.

Security is a first-class requirement.

Requirements:

- No Plaid access tokens in frontend code.
- No secrets in Git.
- Use Secrets Manager for secrets.
- Private S3 buckets.
- Block public S3 access.
- CloudFront should be the public frontend entry point.
- Least-privilege IAM.
- Separate IAM roles for Lambda functions.
- Encrypt data at rest.
- Use HTTPS.
- Validate API inputs.
- Validate webhook requests according to Plaid's security recommendations.
- Avoid logging sensitive financial information.
- Avoid logging access tokens.
- Avoid logging complete financial records unnecessarily.
- Use CloudWatch carefully.
- Implement authentication before exposing personal data publicly.

---

# 33. Terraform / Infrastructure as Code

Terraform is mandatory for infrastructure.

Do not manually create production infrastructure through the AWS console unless absolutely necessary for debugging or initial account setup.

Terraform should manage:

- S3 buckets
- CloudFront
- API Gateway
- Lambda
- IAM
- DynamoDB
- Glue
- Athena-related resources
- EventBridge
- Secrets Manager configuration where appropriate
- Cognito
- DNS/Route53 if used
- CloudWatch resources
- SNS/SQS if later introduced

Potential structure:

infrastructure/

    terraform/

        environments/
            dev/
            prod/

        modules/
            s3/
            cloudfront/
            lambda/
            api_gateway/
            dynamodb/
            iam/
            glue/
            athena/
            cognito/

Start with a single dev environment if necessary.

Do not over-engineer Terraform modules before infrastructure actually exists.

---

# 34. Environments

At minimum:

dev

Eventually:

dev
prod

Do not create a large environment-management system initially.

Keep development cheap.

---

# 35. CI/CD

Eventually use GitHub Actions or another CI/CD mechanism.

Potential flow:

git push
→ CI
→ tests
→ Terraform validation
→ build frontend
→ deploy infrastructure
→ deploy Lambda
→ deploy frontend to S3
→ CloudFront invalidation where required

CI/CD is not required before the first functional prototype.

---

# 36. Event-Driven Architecture

Use AWS EventBridge where it makes sense.

Potential events:

transaction sync required
daily reconciliation
analytics refresh
maintenance/compaction
periodic balance refresh

Avoid introducing EventBridge simply for architectural decoration.

Use it where it provides meaningful decoupling.

---

# 37. Cost Requirements

The application is initially for personal use.

The expected AWS cost should be extremely low.

Target:

Approximately $0–$5/month during normal personal usage, with the exact cost depending on AWS pricing and usage.

Use serverless services.

Avoid continuously running compute.

Avoid unnecessary Athena scans.

Use Parquet/Iceberg.

Use appropriate partitioning.

Use S3 lifecycle policies where appropriate.

Set AWS Budgets/alerts.

Do not optimize purely for zero cost if doing so creates unnecessary complexity.

The goal is:

LOW COST + SIMPLE + RELIABLE.

---

# 38. Scaling Philosophy

Do not prematurely design for millions of users.

Initial scale:

1 user

Possible near-term:

5–20 trusted users

Potential future:

Hundreds/thousands of users

Only introduce ECS/Fargate or other infrastructure when actual requirements justify it.

The API contract should be designed so Lambda can eventually be replaced by ECS without forcing a frontend rewrite.

Potential future architecture:

CloudFront
→ API Gateway / ALB
→ ECS/Fargate
→ services

But this is explicitly a future consideration, NOT an initial requirement.

---

# 39. Data Lifecycle

The conceptual data lifecycle is:

Plaid
↓
Raw ingestion
↓
Raw S3
↓
Normalization
↓
Curated Iceberg
↓
Enrichment
↓
Transfer detection
↓
Categorization
↓
Derived analytical Iceberg tables
↓
Athena
↓
API
↓
Frontend

The raw source should remain recoverable.

Derived data should be reproducible.

---

# 40. Data Quality

The pipeline should eventually implement data-quality checks.

Examples:

- Duplicate transaction detection
- Missing transaction IDs
- Invalid amounts
- Invalid dates
- Duplicate transfer matching
- Impossible account references
- Unexpected transaction states
- Schema changes
- Unexpected null rates

Data-quality failures should be observable through CloudWatch/logging.

---

# 41. Idempotency

Idempotency is extremely important.

The following should be safe to repeat:

- Plaid webhook processing
- Transaction synchronization
- Raw ingestion
- Transformation
- Categorization
- Transfer matching
- Analytics aggregation

A retry must not create duplicate transactions.

Use stable identifiers and deterministic processing.

---

# 42. Observability

Use CloudWatch for:

- Lambda logs
- Errors
- Invocation metrics
- Duration
- API failures
- Plaid sync failures
- Data pipeline failures

Eventually add:

- Structured logging
- Correlation IDs
- Sync status
- Last successful synchronization
- Failed transaction processing count

Do not log sensitive credentials or unnecessary financial details.

---

# 43. Initial MVP

The MVP should NOT attempt to implement every feature above.

The first working version should accomplish:

1. Terraform creates AWS infrastructure.
2. React frontend is deployed through S3/CloudFront.
3. User can authenticate.
4. User can initiate Plaid Link.
5. Backend exchanges the Plaid token.
6. Plaid access token is securely stored.
7. Accounts are retrieved.
8. Transactions are synchronized.
9. Raw transaction data is stored in S3.
10. Transactions are normalized.
11. Transactions are written to an Iceberg table.
12. Glue Catalog exposes the table.
13. Athena can query the table.
14. Backend can return transactions.
15. Frontend displays transactions.
16. Pending/posted transactions are handled.
17. Basic transfer detection exists.
18. Basic categories exist.
19. Basic dashboard exists.

Everything else can follow.

---

# 44. Recommended Development Order

Build incrementally.

## Phase 1 — Repository

Create:

ledgerly/

    README.md
    backend/
    frontend/
    infrastructure/
    data/
    docs/

Set up Git.

Set up Python environment.

Set up frontend.

Set up Terraform.

---

## Phase 2 — AWS Foundation

Terraform:

- S3
- IAM
- Lambda
- API Gateway
- DynamoDB
- CloudWatch
- Secrets Manager

Get a basic Lambda API responding successfully.

---

## Phase 3 — Frontend Foundation

Create a very simple React application.

Pages:

- Dashboard
- Transactions
- Accounts
- Settings

Initially use mocked data.

Do not spend weeks on styling.

---

## Phase 4 — Plaid

Implement:

Plaid Link
→ public token
→ backend
→ access token
→ secure storage

Connect one real personal financial institution.

Do not connect everything at once.

---

## Phase 5 — Transaction Pipeline

Implement:

Plaid
→ Lambda
→ raw S3
→ normalization
→ Iceberg

Test:

- Initial load
- Incremental sync
- Duplicate handling
- Pending transactions
- Posted transactions
- Deleted transactions

---

## Phase 6 — Athena

Create Glue/Iceberg tables.

Run Athena queries.

Validate:

- Partitioning
- File layout
- Query performance
- Data correctness
- Cost

---

## Phase 7 — Transfer Logic

Implement:

- Account-to-account transfer detection
- Credit-card payment detection
- Transfer groups
- Manual overrides

Validate financial reporting.

---

## Phase 8 — Dashboard

Build:

- Net worth
- Income
- Expenses
- Cash flow
- Category spending
- Recent transactions

---

## Phase 9 — Rules

Add:

- Categorization rules
- Merchant normalization
- User overrides
- Transfer overrides

---

## Phase 10 — Hardening

Add:

- Authentication
- Security improvements
- Error handling
- Monitoring
- Data-quality checks
- Retry behavior
- CI/CD
- Terraform environments
- AWS budgets

---

# 45. Important Architectural Principles

Always prefer:

Simple over complex.

Serverless over continuously running infrastructure.

Data correctness over UI polish.

Incremental processing over full reloads.

Immutable raw data over destructive transformations.

Idempotent pipelines over fragile one-time scripts.

Iceberg tables over unmanaged collections of Parquet files.

Athena for analytics, not every operational read.

DynamoDB for operational state, not analytical workloads.

Terraform over manual infrastructure.

Backend business logic over frontend financial calculations.

Small incremental changes over giant rewrites.

---

# 46. Things NOT to Build Initially

Do NOT build:

- ECS
- Kubernetes
- EKS
- RDS
- Redis
- Kafka
- Complex microservices
- Multi-region architecture
- Multi-account AWS organization
- Enterprise RBAC
- Complex event buses
- Machine-learning categorization
- Investment trading
- Tax preparation
- Bill payment
- Financial advice
- Social features
- Public marketplace

These may become relevant later, but are explicitly out of scope for v1.

---

# 47. AI Coding Assistant Instructions

When assisting with this project:

1. Understand the architecture before writing code.
2. Do not introduce new AWS services without explaining why.
3. Prefer existing AWS services already selected.
4. Keep the initial architecture serverless.
5. Use Python for Lambda/backend code.
6. Use Terraform for infrastructure.
7. Use React + TypeScript + Tailwind for frontend.
8. Keep frontend code simple and understandable.
9. Keep financial business logic out of the frontend.
10. Treat S3 as the data lake.
11. Treat Iceberg as the analytical table format.
12. Treat Athena as the analytical query engine.
13. Treat DynamoDB as operational storage.
14. Treat Plaid as the financial-data ingestion source.
15. Preserve raw data.
16. Make ingestion idempotent.
17. Design for incremental updates.
18. Never expose secrets to the frontend.
19. Do not hardcode credentials.
20. Do not create unnecessary abstractions.
21. Do not prematurely optimize for millions of users.
22. Do not introduce ECS unless there is a demonstrated need.
23. Explain significant architectural decisions before implementing them.
24. Prefer small, testable changes.
25. When modifying existing code, preserve working functionality.
26. Add tests for important backend/data transformations.
27. Treat transfer detection as a first-class financial requirement.
28. Never count transfers as income or expenses.
29. Design schemas deliberately before implementing pipelines.
30. Optimize Athena/Iceberg for realistic query patterns.
31. Consider partition pruning and file sizes.
32. Avoid small-file problems.
33. Keep raw, curated, and derived layers logically separated.
34. Assume financial correctness is more important than visual polish.
35. If uncertain about a Plaid or AWS API behavior, consult current official documentation rather than guessing.

---

# 48. Definition of Success

The project is successful when the developer can:

1. Open the Ledgerly web application.
2. Authenticate securely.
3. Connect personal bank/credit-card accounts through Plaid.
4. Pull historical transactions.
5. Automatically synchronize new transactions.
6. Store source data in S3.
7. Store normalized transactions in Iceberg.
8. Query the data using Athena.
9. View transactions in the frontend.
10. Correct categories.
11. Automatically identify transfers.
12. Avoid double-counting credit-card payments.
13. View monthly spending.
14. View income.
15. View cash flow.
16. View net worth.
17. Search/filter transactions.
18. Reprocess data without losing the original source.
19. Operate the entire application with minimal AWS cost.
20. Provision infrastructure using Terraform.

The long-term vision is not simply to clone Monarch or another budgeting application.

The vision is:

> Build a personal financial data platform where the user owns the data model, owns the rules, owns the historical record, and can query and analyze their finances however they want.

The UI is simply the interface to that underlying financial data platform.

For the first version, prioritize correctness, simplicity, AWS-native architecture, good data modeling, and a reliable transaction pipeline.

Do not optimize for hypothetical scale.

Build the smallest version that works end-to-end, then iterate.

# END OF PROJECT SPECIFICATION