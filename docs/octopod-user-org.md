╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Multi-Tenant Org/User/Project System                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ The backend currently has Cognito JWT auth but no concept of organizations, users (in DB), or projects. Resources (mailboxes, campaigns, templates) are scoped by owner_id = Cognito sub. We need a │
│  SaaS-style hierarchy: Organization → Users → Projects, where all resources belong to a project.                                                                                                    │
│                                                                                                                                                                                                     │
│ Cognito handles authentication only. All org/project/role management lives in our database (standard SaaS pattern recommended by AWS).                                                              │
│                                                                                                                                                                                                     │
│ Hierarchy                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Organization (org_)                                                                                                                                                                                 │
│   ├── OrgMembership (om_) ← role: owner | admin | member                                                                                                                                            │
│   │     └── User (usr_) ← linked to Cognito sub                                                                                                                                                     │
│   └── Project (prj_)                                                                                                                                                                                │
│         ├── Mailbox                                                                                                                                                                                 │
│         ├── EmailCampaign                                                                                                                                                                           │
│         ├── EmailTemplate                                                                                                                                                                           │
│         └── DeveloperProfile                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 1: Models + Enums                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ New files to create:                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ app/common/enum/org.py — OrgRole (owner, admin, member), MembershipStatus (active, invited, suspended)                                                                                              │
│                                                                                                                                                                                                     │
│ app/model/organization_model.py — organization table                                                                                                                                                │
│ - id (org_uuid), name, slug (unique), plan (free/pro/enterprise), logo_url, is_deleted, audit fields                                                                                                │
│                                                                                                                                                                                                     │
│ app/model/user_model.py — user table                                                                                                                                                                │
│ - id (usr_uuid), cognito_sub (unique, indexed), email (indexed), display_name, avatar_url, default_org_id, default_project_id, last_login_at, audit fields                                          │
│                                                                                                                                                                                                     │
│ app/model/org_membership_model.py — org_membership table                                                                                                                                            │
│ - id (om_uuid), org_id, user_id, role, status, invited_by, invited_email                                                                                                                            │
│ - Unique constraint on (org_id, user_id)                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ app/model/project_model.py — project table                                                                                                                                                          │
│ - id (prj_uuid), org_id, name, slug, description, is_deleted, audit fields                                                                                                                          │
│ - Unique constraint on (org_id, slug)                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ Existing models to modify:                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ Add project_id = Column(String(), nullable=True, index=True) to:                                                                                                                                    │
│ - app/model/mailbox_model.py                                                                                                                                                                        │
│ - app/model/email_campaign_model.py                                                                                                                                                                 │
│ - app/model/email_template_model.py                                                                                                                                                                 │
│ - app/model/developer_profile_model.py                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ Keep existing owner_id as audit/creator tracking.                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 2: Repositories                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ New files:                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ - app/db/repository/organization_repository.py — CRUD, list_by_user(user_id)                                                                                                                        │
│ - app/db/repository/user_repository.py — get_by_cognito_sub(sub), get_by_email(email), CRUD                                                                                                         │
│ - app/db/repository/org_membership_repository.py — get(org_id, user_id), list_by_org(org_id), list_by_user(user_id), invite/accept                                                                  │
│ - app/db/repository/project_repository.py — CRUD, list_by_org(org_id)                                                                                                                               │
│                                                                                                                                                                                                     │
│ Existing repos to modify:                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Change list_by_owner(owner_id) → list_by_project(project_id) and add project_id filter to get_by_id in:                                                                                             │
│ - app/db/repository/mailbox_repository.py                                                                                                                                                           │
│ - app/db/repository/email_campaign_repository.py                                                                                                                                                    │
│ - app/db/repository/email_template_repository.py                                                                                                                                                    │
│ - app/db/repository/developer_profile_repository.py (add list_by_project)                                                                                                                           │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 3: Auth Enhancement                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Modify app/common/auth/auth.py:                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Enhanced UserContext:                                                                                                                                                                               │
│ class UserContext(BaseModel):                                                                                                                                                                       │
│     actor_id: str        # Cognito sub (backward compat)                                                                                                                                            │
│     user_id: str         # Internal usr_ id                                                                                                                                                         │
│     email: str | None                                                                                                                                                                               │
│     organization_id: str # Active org                                                                                                                                                               │
│     project_id: str      # Active project                                                                                                                                                           │
│     role: str            # Role in active org                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ New get_user_context dependency:                                                                                                                                                                    │
│ 1. Decode JWT → get sub, email                                                                                                                                                                      │
│ 2. Lookup user by cognito_sub → auto-provision if first time (create user + personal org + default project + owner membership)                                                                      │
│ 3. Resolve org from X-Org-Id header or user.default_org_id                                                                                                                                          │
│ 4. Verify org membership → extract role                                                                                                                                                             │
│ 5. Resolve project from X-Project-Id header or user.default_project_id                                                                                                                              │
│ 6. Verify project belongs to org                                                                                                                                                                    │
│ 7. Return UserContext                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ New require_role(*roles) dependency factory — returns 403 if user's role not in allowed list.                                                                                                       │
│                                                                                                                                                                                                     │
│ Keep get_actor_id_required working for backward compatibility during migration.                                                                                                                     │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 4: Services                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ New files:                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ - app/service/user_service.py — auto_provision(sub, email), get_or_create_user(), update_profile(), switch_context(org_id, project_id)                                                              │
│ - app/service/organization_service.py — create_org(), update_org(), delete_org(), list_user_orgs()                                                                                                  │
│ - app/service/org_membership_service.py — invite_member(email, role), accept_invite(), remove_member(), change_role()                                                                               │
│ - app/service/project_service.py — create_project(), update_project(), delete_project(), list_projects()                                                                                            │
│                                                                                                                                                                                                     │
│ Existing services to modify:                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ Update to accept project_id instead of owner_id for scoping:                                                                                                                                        │
│ - app/service/mailbox_service.py                                                                                                                                                                    │
│ - app/service/campaign_service.py                                                                                                                                                                   │
│ - app/service/developer_profile_service.py                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 5: Request/Response Schemas                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ New files:                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ - app/api/v1/request/organization_request.py — Create/UpdateOrgRequest                                                                                                                              │
│ - app/api/v1/request/project_request.py — Create/UpdateProjectRequest                                                                                                                               │
│ - app/api/v1/request/user_request.py — UpdateProfileRequest, SwitchContextRequest, InviteMemberRequest                                                                                              │
│ - app/api/v1/response/organization_response.py — OrgResponse                                                                                                                                        │
│ - app/api/v1/response/project_response.py — ProjectResponse                                                                                                                                         │
│ - app/api/v1/response/user_response.py — UserResponse, UserContextResponse                                                                                                                          │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 6: API Controllers                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ New files:                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ app/api/v1/controller/user_api.py                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ ┌────────┬─────────────┬───────────────────────────────────┬───────────────┐                                                                                                                        │
│ │ Method │    Path     │            Description            │     Auth      │                                                                                                                        │
│ ├────────┼─────────────┼───────────────────────────────────┼───────────────┤                                                                                                                        │
│ │ GET    │ /me         │ Current user + active org/project │ Authenticated │                                                                                                                        │
│ ├────────┼─────────────┼───────────────────────────────────┼───────────────┤                                                                                                                        │
│ │ PATCH  │ /me         │ Update display_name, avatar       │ Authenticated │                                                                                                                        │
│ ├────────┼─────────────┼───────────────────────────────────┼───────────────┤                                                                                                                        │
│ │ PUT    │ /me/context │ Switch active org/project         │ Authenticated │                                                                                                                        │
│ └────────┴─────────────┴───────────────────────────────────┴───────────────┘                                                                                                                        │
│                                                                                                                                                                                                     │
│ app/api/v1/controller/organization_api.py                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ ┌────────┬──────────────────────────────────────────┬──────────────────┬───────────────┐                                                                                                            │
│ │ Method │                   Path                   │   Description    │     Auth      │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ POST   │ /organization                            │ Create org       │ Authenticated │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ GET    │ /organization                            │ List user's orgs │ Authenticated │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ GET    │ /organization/{org_id}                   │ Get org details  │ Member        │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ PATCH  │ /organization/{org_id}                   │ Update org       │ Admin+        │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ DELETE │ /organization/{org_id}                   │ Soft-delete org  │ Owner         │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ POST   │ /organization/{org_id}/members/invite    │ Invite by email  │ Admin+        │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ GET    │ /organization/{org_id}/members           │ List members     │ Member        │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ PATCH  │ /organization/{org_id}/members/{user_id} │ Change role      │ Admin+        │                                                                                                            │
│ ├────────┼──────────────────────────────────────────┼──────────────────┼───────────────┤                                                                                                            │
│ │ DELETE │ /organization/{org_id}/members/{user_id} │ Remove member    │ Admin+        │                                                                                                            │
│ └────────┴──────────────────────────────────────────┴──────────────────┴───────────────┘                                                                                                            │
│                                                                                                                                                                                                     │
│ app/api/v1/controller/project_api.py                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ ┌────────┬───────────────────────┬──────────────────────────────┬────────┐                                                                                                                          │
│ │ Method │         Path          │         Description          │  Auth  │                                                                                                                          │
│ ├────────┼───────────────────────┼──────────────────────────────┼────────┤                                                                                                                          │
│ │ POST   │ /project              │ Create project in active org │ Admin+ │                                                                                                                          │
│ ├────────┼───────────────────────┼──────────────────────────────┼────────┤                                                                                                                          │
│ │ GET    │ /project              │ List projects in active org  │ Member │                                                                                                                          │
│ ├────────┼───────────────────────┼──────────────────────────────┼────────┤                                                                                                                          │
│ │ GET    │ /project/{project_id} │ Get project                  │ Member │                                                                                                                          │
│ ├────────┼───────────────────────┼──────────────────────────────┼────────┤                                                                                                                          │
│ │ PATCH  │ /project/{project_id} │ Update project               │ Admin+ │                                                                                                                          │
│ ├────────┼───────────────────────┼──────────────────────────────┼────────┤                                                                                                                          │
│ │ DELETE │ /project/{project_id} │ Soft-delete project          │ Admin+ │                                                                                                                          │
│ └────────┴───────────────────────┴──────────────────────────────┴────────┘                                                                                                                          │
│                                                                                                                                                                                                     │
│ Existing controllers to modify:                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Switch from get_actor_id_required to get_user_context, pass ctx.project_id to services:                                                                                                             │
│ - All 10 controller files (mailbox, campaign, template, developer_profile, enrichment, ingest_*)                                                                                                    │
│                                                                                                                                                                                                     │
│ Wire-up:                                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ - app/api/v1/router.py — register new routers                                                                                                                                                       │
│ - app/api/tags.py — add Organization, Project, User tags                                                                                                                                            │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 7: Database Migration                                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ alembic/versions/YYYYMMDD_add_multi_tenant_tables.py                                                                                                                                                │
│                                                                                                                                                                                                     │
│ 1. Create tables: organization, user, org_membership, project                                                                                                                                       │
│ 2. Add project_id column (nullable) to: mailbox, email_campaign, email_template, developer_profile                                                                                                  │
│ 3. Add indexes on project_id                                                                                                                                                                        │
│ 4. Backfill: for each distinct owner_id, create user + org + project + membership, set project_id                                                                                                   │
│ 5. Make project_id NOT NULL after backfill                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Phase 8: Tests                                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ - Update tests/conftest.py — import new models, update authenticated_client fixture to auto-provision user+org+project                                                                              │
│ - Update existing test files to work with project-scoped queries                                                                                                                                    │
│ - Add new test files:                                                                                                                                                                               │
│   - tests/test_api/test_user_api.py                                                                                                                                                                 │
│   - tests/test_api/test_organization_api.py                                                                                                                                                         │
│   - tests/test_api/test_project_api.py                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Context Resolution (Header-Based)                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Frontend sends X-Org-Id and X-Project-Id headers. If omitted, falls back to user.default_org_id / user.default_project_id. The PUT /me/context endpoint updates defaults when users switch in the   │
│ UI.                                                                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ This avoids breaking existing URL structure (no path prefix changes).                                                                                                                               │
│                                                                                                                                                                                                     │
│ Permission Matrix                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ ┌───────────────────────────┬───────┬───────┬────────┐                                                                                                                                              │
│ │          Action           │ Owner │ Admin │ Member │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ Create/delete org         │ Yes   │ No    │ No     │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ Update org settings       │ Yes   │ Yes   │ No     │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ Invite/remove members     │ Yes   │ Yes   │ No     │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ Change member roles       │ Yes   │ Yes*  │ No     │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ Create/delete projects    │ Yes   │ Yes   │ No     │                                                                                                                                              │
│ ├───────────────────────────┼───────┼───────┼────────┤                                                                                                                                              │
│ │ CRUD resources in project │ Yes   │ Yes   │ Yes    │                                                                                                                                              │
│ └───────────────────────────┴───────┴───────┴────────┘                                                                                                                                              │
│                                                                                                                                                                                                     │
│ *Admins cannot change/remove owners.                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Auto-Provisioning (First Login)                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ When a Cognito user hits any protected endpoint for the first time:                                                                                                                                 │
│ 1. Create User record from JWT (sub, email)                                                                                                                                                         │
│ 2. Create personal Organization ("Personal Org")                                                                                                                                                    │
│ 3. Create OrgMembership (role=owner)                                                                                                                                                                │
│ 4. Create default Project ("Default")                                                                                                                                                               │
│ 5. Set user defaults → user is ready to use the app immediately                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make lint + make test — all pass                                                                                                                                                                 │
│ 2. Hit any endpoint without auth → 401                                                                                                                                                              │
│ 3. Hit with auth (first time) → auto-provisions user+org+project, returns data                                                                                                                      │
│ 4. GET /me → returns user profile with active org/project                                                                                                                                           │
│ 5. POST /organization → creates new org, user becomes owner                                                                                                                                         │
│ 6. POST /organization/{id}/members/invite → invite by email                                                                                                                                         │
│ 7. Resources created in project A not visible when switched to project B                                                                                                                            │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
