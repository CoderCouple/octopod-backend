╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Plan: AWS Cognito Authentication                                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ The app currently has no real authentication — just an X-Actor-Id header extraction (app/common/auth/auth.py). The user wants robust, easy-to-setup auth for both the Next.js frontend and FastAPI  │
│ backend, free for early users. Chose AWS Cognito (50K MAU free tier).                                                                                                                               │
│                                                                                                                                                                                                     │
│ Key design decision: Handle JWT validation in FastAPI (not ALB auth rules). Simpler, more flexible, no ALB reconfiguration needed, works locally.                                                   │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 1: CloudFormation Stack (05-cognito)                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ New files: octopod-infra/05-cognito/cognito-stack.yaml + cognito-stack-params.json                                                                                                                  │
│                                                                                                                                                                                                     │
│ Resources:                                                                                                                                                                                          │
│ - Cognito User Pool — email sign-up, email auto-verification, password policy                                                                                                                       │
│ - User Pool Domain — hosted UI at octopodai-dev.auth.us-west-2.amazoncognito.com                                                                                                                    │
│ - Frontend App Client — public client (no secret), OAuth2 code flow, openid/email/profile scopes, 1hr token validity, 30-day refresh                                                                │
│                                                                                                                                                                                                     │
│ Outputs: UserPoolId, UserPoolArn, FrontendAppClientId, UserPoolDomainURL, CognitoRegion                                                                                                             │
│                                                                                                                                                                                                     │
│ No M2M/backend client needed initially. No social providers yet (can add later).                                                                                                                    │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 2: Add PyJWT[crypto] dependency                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ File: pyproject.toml                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Add PyJWT = {version = "^2.8.0", extras = ["crypto"]}. Actively maintained (unlike python-jose), supports RS256 for Cognito JWKS.                                                                   │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 3: Settings — Add Cognito config                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ File: app/settings.py                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ Add fields:                                                                                                                                                                                         │
│ cognito_user_pool_id: str = ""                                                                                                                                                                      │
│ cognito_region: str = "us-west-2"                                                                                                                                                                   │
│ cognito_app_client_id: str = ""                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Add computed properties: cognito_jwks_url, cognito_issuer                                                                                                                                           │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 4: JWT validation module (new)                                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ New file: app/common/auth/cognito.py                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ - _get_jwks() — fetch + cache Cognito JWKS (1hr TTL)                                                                                                                                                │
│ - decode_cognito_token(token) — verify RS256 signature, expiry, issuer, audience                                                                                                                    │
│ - get_current_user(credentials) — FastAPI dependency, requires valid JWT, returns claims dict                                                                                                       │
│ - get_current_user_optional(credentials) — same but returns None if no token                                                                                                                        │
│                                                                                                                                                                                                     │
│ Uses HTTPBearer scheme → auto-integrates with Swagger UI "Authorize" button.                                                                                                                        │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 5: Update auth.py — backward-compatible                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ File: app/common/auth/auth.py                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ Rewrite get_actor_id to delegate to get_current_user_optional and extract sub claim. Same return type (str | None) → zero changes to the 5 controller files that depend on it.                      │
│                                                                                                                                                                                                     │
│ Add get_actor_id_required (raises 401) and get_user_context (returns full UserContext) for future use.                                                                                              │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 6: Environment variables                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ .env.local / .env.dev:                                                                                                                                                                              │
│ COGNITO_USER_POOL_ID=us-west-2_xxxxxxxxx                                                                                                                                                            │
│ COGNITO_REGION=us-west-2                                                                                                                                                                            │
│ COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ Values obtained from CloudFormation stack outputs after deploying Step 1.                                                                                                                           │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Step 7: Test fixture + auth tests                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ File: tests/conftest.py — add authenticated_client fixture that mocks JWT validation                                                                                                                │
│ New file: tests/test_api/test_auth.py — test health works without auth, protected routes get actor_id from JWT                                                                                      │
│                                                                                                                                                                                                     │
│ Existing tests continue to pass unchanged (auth remains optional in Phase 1).                                                                                                                       │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Route Protection (Phased)                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ ┌───────────────────┬───────────────────────────────────────────────┬──────────────────────────────────────────────────┐                                                                            │
│ │       Phase       │                     Scope                     │                  Auth behavior                   │                                                                            │
│ ├───────────────────┼───────────────────────────────────────────────┼──────────────────────────────────────────────────┤                                                                            │
│ │ Phase 1 (this PR) │ All routes                                    │ Optional — get_actor_id returns None if no token │                                                                            │
│ ├───────────────────┼───────────────────────────────────────────────┼──────────────────────────────────────────────────┤                                                                            │
│ │ Phase 2           │ Outreach routes (mailbox, campaign, template) │ Required — swap to get_actor_id_required         │                                                                            │
│ ├───────────────────┼───────────────────────────────────────────────┼──────────────────────────────────────────────────┤                                                                            │
│ │ Phase 3           │ Ingest/admin routes                           │ Required + role-based                            │                                                                            │
│ └───────────────────┴───────────────────────────────────────────────┴──────────────────────────────────────────────────┘                                                                            │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ No Local Users Table (Yet)                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ Cognito stores the user directory. Backend references users by sub UUID (stored in existing created_by/updated_by columns). Add a local app_user table later when user-specific settings or org     │
│ features are needed.                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Files Summary                                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────────────────────────────┬────────────────────────────────────────┐                                                                                                     │
│ │                        File                        │                 Action                 │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ octopod-infra/05-cognito/cognito-stack.yaml        │ New — CloudFormation template          │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ octopod-infra/05-cognito/cognito-stack-params.json │ New — Parameters                       │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ pyproject.toml                                     │ Add PyJWT[crypto]                      │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ app/settings.py                                    │ Add Cognito config fields + properties │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ app/common/auth/cognito.py                         │ New — JWT validation + FastAPI deps    │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ app/common/auth/auth.py                            │ Rewrite to use Cognito JWT             │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ tests/conftest.py                                  │ Add authenticated_client fixture       │                                                                                                     │
│ ├────────────────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                     │
│ │ tests/test_api/test_auth.py                        │ New — Auth tests                       │                                                                                                     │
│ └────────────────────────────────────────────────────┴────────────────────────────────────────┘                                                                                                     │
│                                                                                                                                                                                                     │
│ Frontend Guidance (Next.js)                                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Use aws-amplify v6 Auth module. Configure with User Pool ID + App Client ID. Call fetchAuthSession() to get ID token, pass as Authorization: Bearer <token> header. Amplify handles sign-up,        │
│ sign-in, email verification, and token refresh automatically.                                                                                                                                       │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. Deploy CloudFormation stack → CREATE_COMPLETE                                                                                                                                                    │
│ 2. poetry install → PyJWT installed                                                                                                                                                                 │
│ 3. make test → all existing tests pass (no breaking changes)                                                                                                                                        │
│ 4. make dev → Swagger UI shows "Authorize" button                                                                                                                                                   │
│ 5. Create Cognito test user → sign in → get token → call API with Authorization: Bearer <token> → get_actor_id returns the Cognito sub                                                              │
│ 6. Call API without token → get_actor_id returns None (no 401, Phase 1 is optional)                                                                                                                 │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯



  ---
  Now here's the AWS Cognito concept explained for your setup:

  How AWS Cognito Works

  ┌─────────────┐         ┌──────────────────┐          ┌─────────────────┐
  │  Next.js    │         │  AWS Cognito     │          │  FastAPI        │
  │  Frontend   │         │  User Pool       │          │  Backend        │
  └──────┬──────┘         └────────┬─────────┘          └────────┬────────┘
         │                         │                             │
         │  1. Sign up / Sign in   │                             │
         │ ──────────────────────> │                             │
         │                         │                             │
         │  2. Returns JWT tokens  │                             │
         │ <────────────────────── │                             │
         │   (ID + Access + Refresh)                             │
         │                         │                             │
         │  3. API call with       │                             │
         │     Authorization:      │                             │
         │     Bearer <IdToken>    │                             │
         │──────────────────────────────────��──────────────────>│
         │                         │                             │
         │                         │  4. Fetch JWKS (public keys)│
         │                         │ <───────────────────────────│
         │                         │                             │
         │                         │  5. Return public keys      │
         │                         │───────────��───────────────>│
         │                         │                             │
         │                         │     6. Verify JWT signature │
         │                         │        Check exp, iss, aud  │
         │                         │        Extract sub (user id)│
         │                         │                             │
         │  7. API response        │                             │
         │ <─────────────────────────────────────────────────────│

  Key pieces:

  User Pool — Your user directory in AWS. Stores emails, passwords, attributes. Like a managed auth database. Free for 50K monthly active users.

  App Client — A "registration" of your frontend app with the User Pool. No secret (public client) since it runs in the browser. Defines allowed OAuth flows and token lifetimes.

  3 Tokens returned on sign-in:
  - ID Token (1hr) — Contains user identity claims (sub, email, email_verified). This is what you send to FastAPI as Authorization: Bearer <token>.
  - Access Token (1hr) — For calling Cognito APIs (e.g., get/update user attributes). Not sent to your backend.
  - Refresh Token (30 days) — Used by Amplify to silently get new ID/Access tokens when they expire. User stays logged in for 30 days.

  JWKS (JSON Web Key Set) — Cognito publishes its public RSA keys at a well-known URL. Your backend fetches these once (cached 1hr), then uses them to verify JWT signatures locally. No network call
  to Cognito per request.

  sub claim — A UUID that uniquely identifies the user (2861c310-9091-7011-4092-c67caed9b848). This is what get_actor_id returns. It's stable — never changes even if the user changes their email.

  Why it works the same locally and on AWS:

  Your backend only needs 3 values (same in both .env.local and .env.dev):
  - COGNITO_USER_POOL_ID — to construct the JWKS URL and issuer
  - COGNITO_REGION — part of the JWKS URL
  - COGNITO_APP_CLIENT_ID — to verify the token's aud claim

  JWT validation is pure crypto (fetch public key → verify RSA signature). It works identically on localhost and in ECS — no VPC, no IAM roles needed.

  What the frontend (Next.js) does:

  npm install aws-amplify

  Configure Amplify with the User Pool ID + Client ID, and it handles:
  - Sign-up flow (email + password → verification code)
  - Sign-in flow → stores tokens in browser
  - Auto-refresh when ID token expires (using refresh token)
  - fetchAuthSession() → gives you the current ID token to pass to API calls

  ---
  You're all set. Run make dev whenever you're ready, and you can test with the token we already got. The test user is test@example.com / Octopod1234
