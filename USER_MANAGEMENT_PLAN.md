# OwnerDashV2 — User Management Enhancement Plan

**Date:** Feb 18, 2026  
**Status:** PLAN ONLY — no code changes

---

## Current State

| Aspect | Today |
|--------|-------|
| Users | 2 hardcoded dicts in `auth_service.py` (PHH, Kairoi) — one login per org |
| Auth | JWT + bcrypt, 24h expiry |
| Roles | None — all users are equal |
| Data scope | `owner_group` on JWT → filters portfolio to group's properties |
| Password reset | None |
| User management | None — adding users requires code change + redeploy |
| Chat | AI chat only (`AIChatPanel.tsx`) — no person-to-person |
| Admin | `admin.py` exists but only for DB upload ops (GitHub Actions), not user mgmt |

---

## 1. Individual User Accounts (Per Person)

**Goal:** Each person (asset manager, regional, VP, etc.) gets their own login.

### Database: `users` table in `unified.db`

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,              -- UUID
    email TEXT UNIQUE NOT NULL,       -- login identifier (replaces username)
    password_hash TEXT NOT NULL,      -- bcrypt
    display_name TEXT NOT NULL,       -- "John Smith"
    role TEXT NOT NULL DEFAULT 'user', -- 'admin' | 'user'
    owner_group TEXT NOT NULL,        -- 'PHH' | 'Kairoi' | etc.
    is_active INTEGER DEFAULT 1,     -- soft delete / disable
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,                  -- user_id of who invited them
    last_login TIMESTAMP,
    avatar_url TEXT                   -- optional profile picture URL
);
```

### Migration path
- Seed initial admin users for PHH and Kairoi from current hardcoded dict
- `auth_service.py` switches from `USERS` dict → SQLite `users` table lookup
- JWT payload adds `user_id`, `role`, keeps `group`
- All existing group-based filtering continues to work unchanged

### Effort: **M** (4-6 hrs)

---

## 2. Password Reset

**Goal:** Users can reset their own password without admin intervention.

### Option A: Email-based reset (recommended)
1. User clicks "Forgot Password" on login page
2. Backend generates a time-limited reset token (e.g., 1hr JWT or random token stored in DB)
3. Backend sends email with reset link: `https://<netlify-url>/reset-password?token=xxx`
4. User clicks link → enters new password → backend verifies token, updates `password_hash`

**Email provider: Resend** — Free tier: 3,000 emails/mo, 100/day, $0. `pip install resend`. Modern API, takes 5 min to set up.

**Railway's role:** Railway hosts the backend API that handles the reset flow. Backend on Railway calls Resend to send the email. The reset link points to the Netlify frontend, which calls the Railway backend to complete the reset.

### Option B: Admin-initiated reset (Phase 1 — no email needed)
1. Admin clicks "Reset Password" next to a user in the admin panel
2. Backend generates a temporary password and shows it to the admin
3. User logs in with temp password → forced to set a new one on first login

### Phasing:
- **Phase 1:** Option B only (admin-initiated, no email dependency)
- **Phase 2:** Option A added (self-service via Resend email)

### New endpoints
```
POST /api/auth/forgot-password        { email }
POST /api/auth/reset-password          { token, new_password }
POST /api/auth/change-password         { old_password, new_password }  ← logged-in user
POST /api/admin/users/{id}/reset-pw    ← admin-initiated
```

### `password_resets` table
```sql
CREATE TABLE IF NOT EXISTS password_resets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Effort: **M** (Option B) / **L** (Option A with email)

---

## 3. Admin vs Regular User Roles

**Goal:** Admins manage users and platform config. Regular users see the dashboard.

### Role definitions

| Capability | Admin | User |
|------------|-------|------|
| View dashboard (own scope) | ✅ | ✅ |
| AI chat | ✅ | ✅ |
| Person-to-person chat | ✅ | ✅ |
| Change own password | ✅ | ✅ |
| Edit own profile (name, avatar) | ✅ | ✅ |
| Invite new users | ✅ | ❌ |
| Deactivate / delete users | ✅ | ❌ |
| Set data scopes for users | ✅ | ❌ |
| Reset other users' passwords | ✅ | ❌ |
| Edit watchpoint thresholds | ✅ | ❌ |
| View audit log | ✅ | ❌ |
| Access admin panel | ✅ | ❌ |

### Implementation
- `role` field on `users` table (`admin` | `user`)
- Backend middleware: `require_admin()` dependency that checks JWT role
- Frontend: Admin panel route visible only when `user.role === 'admin'`
- First user per owner_group is auto-admin; subsequent users are `user` by default

### Effort: **S** (2-3 hrs — mostly middleware + frontend route guard)

---

## 4. Admin Invites & Data Scope

**Goal:** Admin invites team members and controls what properties/tabs each user can access.

### Invite flow
1. Admin opens "Team" section in admin panel
2. Clicks "Invite User" → enters email, display name, role, property access
3. Backend creates user with temporary password + sends invite email (or shows temp password)
4. Invited user logs in → forced password change → lands on dashboard

### Data scope: `user_property_access` table

```sql
CREATE TABLE IF NOT EXISTS user_property_access (
    user_id TEXT NOT NULL,
    property_id TEXT NOT NULL,        -- unified_property_id
    PRIMARY KEY (user_id, property_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Scope logic:**
- If a user has **zero rows** in `user_property_access` → they see **all properties** in their `owner_group` (backwards-compatible default)
- If a user has **specific rows** → they only see those properties
- Admin always sees all properties in their group

This means:
- PHH admin invites a regional manager → gives them access to only Parkside
- Kairoi admin invites a property manager → gives them access to 3 of 29 properties
- The existing `owner_group` filter stays as the top-level boundary (no user can ever see outside their group)

### Endpoints
```
GET    /api/admin/users                    ← list all users in admin's group
POST   /api/admin/users                    ← invite/create user
PATCH  /api/admin/users/{id}               ← update role, scope, active status
DELETE /api/admin/users/{id}               ← deactivate (soft delete)
GET    /api/admin/users/{id}/access        ← get property access list
PUT    /api/admin/users/{id}/access        ← set property access list
```

### Frontend: Admin Panel (`/admin` route)

```
┌─────────────────────────────────────────────┐
│  Team Management                    [+ Invite] │
├──────────┬─────────┬────────┬───────┬────────┤
│ Name     │ Email   │ Role   │ Scope │ Status │
├──────────┼─────────┼────────┼───────┼────────┤
│ John S.  │ j@phh.. │ Admin  │ All   │ Active │
│ Sarah M. │ s@phh.. │ User   │ 1 prop│ Active │
│ ...      │         │        │       │        │
└──────────┴─────────┴────────┴───────┴────────┘
```

Clicking a user opens a detail panel with:
- Edit name, role
- Property access checkboxes (all properties in the group)
- Reset password button
- Deactivate toggle

### Effort: **L** (1-2 days — backend + admin UI)

---

## 5. 💬 In-Dashboard Personal Chat (BIG ITEM)

**Goal:** Users can message each other inside the dashboard, and reference specific dashboard items (KPIs, properties, charts) in their messages.

### Architecture

#### Backend: WebSocket + REST hybrid

**Why WebSocket?** Real-time messaging requires push. Polling is wasteful and laggy. FastAPI supports WebSockets natively.

**Why REST too?** Message history, read receipts, and search are better as REST.

#### Database tables

```sql
-- Conversations (1:1 or group)
CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,               -- UUID
    type TEXT DEFAULT 'direct',        -- 'direct' | 'group' | 'property'
    name TEXT,                         -- null for direct, name for group
    property_id TEXT,                  -- if scoped to a property discussion
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

-- Conversation members
CREATE TABLE IF NOT EXISTS chat_members (
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_read_at TIMESTAMP,            -- for unread count
    PRIMARY KEY (conversation_id, user_id)
);

-- Messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,               -- UUID
    conversation_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    content TEXT NOT NULL,             -- message text (markdown supported)
    reference_type TEXT,               -- 'property' | 'kpi' | 'unit' | 'chart' | null
    reference_id TEXT,                 -- e.g. property_id, "occupancy", "unit_204"
    reference_snapshot TEXT,           -- JSON snapshot of the referenced data at send time
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id),
    FOREIGN KEY (sender_id) REFERENCES users(id)
);
```

#### The "@" Reference System

Two ways to reference dashboard items in chat:

**Method 1: @ Mention in Chat**
- User types `@` in the chat input → autocomplete dropdown appears
- Categories: `@property:Parkside`, `@kpi:occupancy`, `@unit:204`, `@chart:occ-trend`
- On send, the reference is stored in `reference_type` + `reference_id`
- Rendered as a clickable chip/card in the message bubble
- Clicking the chip navigates to that item in the dashboard

**Method 2: "Share to Chat" Button on Dashboard**
- Each KPI card, chart, table section gets a small share icon (💬 or link icon)
- Clicking it opens a mini-modal: "Share with..." → pick a conversation → add optional comment
- This creates a message with the item pre-attached as a reference
- The `reference_snapshot` stores the value at send time (e.g., `{"occupancy": 92.7, "date": "2026-02-18"}`) so the recipient sees what it was when shared, even if the live number changes later

#### Reference types

| Type | Example Reference ID | Snapshot Content |
|------|---------------------|-----------------|
| `property` | `parkside` | `{name, occupancy, units, ...}` |
| `kpi` | `parkside:occupancy` | `{value: 92.7, trend: "+1.2%"}` |
| `unit` | `parkside:unit_204` | `{status, floorplan, rent, ...}` |
| `chart` | `parkside:occ_trend` | `{data_points: [...], range: "6mo"}` |
| `table_row` | `parkside:delinquency:unit_312` | `{balance, days_past_due}` |
| `watchpoint` | `parkside:occ_below_90` | `{threshold, actual, severity}` |

#### Endpoints

```
# REST
GET    /api/chat/conversations                    ← list user's conversations
POST   /api/chat/conversations                    ← create conversation
GET    /api/chat/conversations/{id}/messages       ← paginated history
POST   /api/chat/conversations/{id}/messages       ← send message (also broadcast via WS)
GET    /api/chat/unread-count                      ← badge count for chat icon

# WebSocket
WS     /api/chat/ws                                ← real-time: new messages, typing indicators, read receipts
```

#### Frontend Components

```
src/
  components/
    chat/
      ChatDrawer.tsx          ← slide-out panel (right side, like Slack)
      ConversationList.tsx    ← list of conversations + unread badges
      MessageThread.tsx       ← message bubbles + reference cards
      ChatInput.tsx           ← input with @ autocomplete + file attach
      ReferenceCard.tsx       ← inline preview of referenced dashboard item
      ShareToChatModal.tsx    ← "share this KPI to chat" mini-modal
      UserPresence.tsx        ← online/offline indicators
```

**Layout:** Chat drawer slides in from the right. Dashboard content shifts or overlays. Chat icon in the top nav bar shows unread badge count.

#### Notifications (In-App Only)
- **Unread badge** on chat icon in top nav
- **Toast notification** for new messages when chat drawer is closed
- No browser push or email digest for now

### Effort: **XL** (5-8 days — WebSocket infra, chat UI, reference system, share buttons)

---

## 6. Additional User Features (Suggestions)

### 6a. User Activity Audit Log
Track who did what and when. Valuable for accountability in multi-user orgs.

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,          -- 'login', 'view_property', 'export', 'chat_message', etc.
    target_type TEXT,              -- 'property', 'report', 'user', etc.
    target_id TEXT,
    metadata TEXT,                 -- JSON details
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Admin panel shows: "Sarah viewed Parkside at 2:14 PM", "John exported delinquency report at 3:30 PM".

**Effort:** M

### 6b. Saved Views / Bookmarks
Users can save their preferred dashboard configurations:
- Which properties are selected
- Which tab they were on
- Filters applied (timeframe, radius, etc.)
- Pinned KPIs

Stored per-user, loads on login. "Where I left off" experience.

**Effort:** M

### 6c. User Preferences / Settings Page
- **Theme:** Light / dark mode (currently only light)
- **Default view:** Portfolio vs single-property on login
- **Notification preferences:** Chat notifications on/off, email digest on/off
- **Number format:** Thousands separator style
- **Timezone:** For date display

Stored in a `user_preferences` JSON column or separate table.

**Effort:** M

### 6d. Report Export with User Attribution
When a user exports a PDF/Excel report from the dashboard, stamp it with:
- "Generated by: John Smith (PHH)"
- "Date: Feb 18, 2026"
- "Data as of: Feb 18, 2026 08:00 UTC"

Creates accountability and provenance for shared reports.

**Effort:** S

### 6e. @Mentions & Notifications for Watchpoints
When a watchpoint triggers (e.g., occupancy drops below 90%):
- Auto-create a chat message in the property's channel
- Tag relevant users (the property manager assigned to that property)
- "⚠️ Parkside occupancy dropped to 88.3% — below 90% threshold"

This turns passive alerts into collaborative conversations.

**Effort:** L (depends on chat being built first)

### 6f. Granular Permissions: Tabs + Sections/Views ✅ CONFIRMED
Beyond admin/user, admins can check/uncheck **individual sections and tables** — not just whole tabs.

#### Two levels of control

| Level | What admin controls | Example |
|-------|-------------------|---------|
| **Tab** | Show/hide entire tab from nav | Hide "Financials" tab entirely for a property manager |
| **View** | Show/hide a specific section/table within a visible tab | Show delinquency summary tiles but hide the unit-level AR table |

#### Database schema

```sql
-- Tab-level access (coarse)
CREATE TABLE IF NOT EXISTS user_tab_access (
    user_id TEXT NOT NULL,
    tab_id TEXT NOT NULL,
    can_view INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, tab_id)
);

-- View/section-level access (granular, within a tab)
CREATE TABLE IF NOT EXISTS user_view_access (
    user_id TEXT NOT NULL,
    view_id TEXT NOT NULL,            -- e.g. 'overview.bedroom_table', 'delinquency.ar_drillthrough'
    can_view INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, view_id)
);
```

#### View ID registry (maps to actual frontend components)

| Tab | View ID | Component | Description |
|-----|---------|-----------|-------------|
| **overview** | `overview.kpi_tiles` | KPICard grid | Occupancy, vacancy, leased %, ATR tiles |
| | `overview.bedroom_table` | BedroomConsolidatedView | Bedroom type breakdown table |
| | `overview.availability` | AvailabilitySection | Availability buckets + ATR trend |
| | `overview.occ_trend` | OccupancyTrendSection | Occupancy trend chart |
| | `overview.market_comps` | MarketCompsTable | Comp properties table |
| | `overview.unit_mix` | UnitMixPricing | Unit mix & pricing section |
| | `overview.trade_outs` | TradeOutSection | Trade-out details |
| **leasing** | `leasing.funnel` | FunnelKPICards | Leads → Tours → Apps → Leases tiles |
| | `leasing.conversions` | (in funnel) | Conversion rate matrix |
| | `leasing.forecast` | Forecast table | Occupancy forecast table |
| | `leasing.floorplan_avail` | (planned) | Available units by floorplan |
| | `leasing.marketing` | MarketingSection | Lead sources & marketing |
| **renewals** | `renewals.summary` | Renewal summary tiles | Renewed / vacating / pending counts |
| | `renewals.drillthrough` | Renewal detail table | Individual renewal rows |
| | `renewals.move_out` | MoveOutReasonsSection | Move-out reasons breakdown |
| | `renewals.expiration_chart` | (planned) | 12-month expiration/renewal chart |
| **delinquency** | `delinquency.summary` | Summary tiles | Aging bucket totals |
| | `delinquency.ar_table` | AR drill-through table | Unit-level delinquency rows |
| | `delinquency.evictions` | Eviction section | Eviction list + details |
| | `delinquency.former_residents` | Former resident balance | Collections / former resident section |
| **financials** | `financials.pnl` | P&L statement | Full income statement |
| | `financials.revenue_detail` | Revenue breakdown | Revenue line items |
| | `financials.kpi_header` | Financial KPIs | Econ occ, bad debt %, etc. |
| **reviews** | `reviews.google` | GoogleReviewsSection | Google reviews + response tracking |
| | `reviews.apartments` | Apartments.com section | Apartments.com reviews |
| | `reviews.reputation` | ReputationOverview | Blended reputation score |
| **risk** | `risk.churn` | Churn gauge + distribution | Churn risk scores |
| | `risk.delinquency` | Delinquency gauge | Delinquency risk scores |
| **maintenance** | `maintenance.summary` | MaintenanceSection | Work orders summary |

#### Default behavior
- **New users get ALL views enabled** (default `can_view=1`)
- Admin **unchecks** specific views to restrict — whitelist model, not blacklist
- If a tab is hidden (`user_tab_access.can_view=0`), all views inside it are automatically hidden regardless of `user_view_access`
- Admin users always see everything — view restrictions only apply to `role='user'`

#### Admin panel UI for permissions

```
┌─ Edit Permissions: Sarah M. ──────────────────────────┐
│                                                        │
│  ☑ Overview                                            │
│    ☑ KPI Tiles                                         │
│    ☑ Bedroom Breakdown Table                           │
│    ☑ Availability & ATR                                │
│    ☑ Occupancy Trend Chart                             │
│    ☑ Market Comps                                      │
│    ☐ Unit Mix & Pricing          ← admin unchecked     │
│    ☐ Trade-Out Details           ← admin unchecked     │
│                                                        │
│  ☑ Leasing                                             │
│    ☑ Funnel Tiles                                      │
│    ☑ Conversion Rates                                  │
│    ☑ Occupancy Forecast                                │
│                                                        │
│  ☐ Financials                    ← entire tab hidden   │
│    (all sections hidden)                               │
│                                                        │
│  ☑ Delinquency                                         │
│    ☑ Summary Tiles                                     │
│    ☐ AR Drill-Through Table      ← admin unchecked     │
│    ☑ Evictions                                         │
│                                                        │
│                              [Save]  [Cancel]          │
└────────────────────────────────────────────────────────┘
```

Unchecking a tab auto-unchecks all children. Checking a tab re-enables all children to their previous state.

#### Frontend enforcement
- API endpoint: `GET /api/auth/me` returns `permissions: { tabs: [...], views: [...] }` alongside user info
- `AuthContext` stores permissions
- Each section component wraps in a `<PermissionGate viewId="overview.bedroom_table">` that renders `null` if the user lacks access
- Tabs not in the user's `tabs` list are removed from `TabNavigation`

#### Backend enforcement
- Drill-through / detail endpoints check `user_view_access` before returning data
- Prevents bypassing the frontend by calling the API directly

**Effort:** L (1-2 days — DB + admin UI checkboxes + PermissionGate component + backend checks)

---

## Implementation Phases

### Phase 1: Foundation (3-4 days)
| Item | What | Effort |
|------|------|--------|
| 1 | `users` table + migrate from hardcoded dict | M |
| 3 | Admin/user roles + middleware | S |
| 2b | Admin-initiated password reset (no email) | S |
| 4a | Admin panel: list/create/edit users | M |
| 4b | Property-level data scoping | M |

**Outcome:** Individual logins, admin can manage team, scoped access works.

### Phase 2: Self-Service & Chat Foundation (5-7 days)
| Item | What | Effort |
|------|------|--------|
| 2a | Email-based password reset (Resend) | M |
| 5a | Chat backend: conversations, messages, WebSocket | L |
| 5b | Chat frontend: drawer, threads, input | L |
| 6c | User settings/preferences page | M |

**Outcome:** Users can reset own passwords, basic person-to-person chat works.

### Phase 3: Dashboard-Integrated Chat (3-5 days)
| Item | What | Effort |
|------|------|--------|
| 5c | @ reference system in chat | L |
| 5d | "Share to Chat" buttons on dashboard components | M |
| 5e | Reference cards (inline previews in chat) | M |
| 6a | Audit log | M |

**Outcome:** Chat is deeply integrated with dashboard data. Full reference system works.

### Phase 4: Polish & Advanced (3-4 days)
| Item | What | Effort |
|------|------|--------|
| 6b | Saved views / bookmarks | M |
| 6d | Export attribution | S |
| 6e | Auto-alerts in chat from watchpoints | L |
| 6f | Granular tab-level permissions | M |

**Outcome:** Full-featured multi-user platform.

---

## Total Estimated Effort

| Phase | Days | Cumulative |
|-------|------|------------|
| Phase 1: Foundation | 3-4 | 3-4 days |
| Phase 2: Self-Service + Chat | 5-7 | 8-11 days |
| Phase 3: Dashboard Chat Integration | 3-5 | 11-16 days |
| Phase 4: Polish | 3-4 | 14-20 days |

**Grand total: ~3-4 weeks** for the full vision.

---

## Technical Decisions ✅

| # | Decision | Answer |
|---|----------|--------|
| 1 | **Email provider** | **Resend** — Free tier (3,000 emails/mo, $0). More than enough for PW resets + invites. |
| 2 | **File sharing in chat** | **No** — not for now. Text + dashboard references only. |
| 3 | **Tab-level permissions** | **Yes** — Phase 4 will include granular tab access (e.g., PM can't see Financials). |
| 4 | **Chat notifications** | **In-app only** for now. No browser push, no email digest. Unread badge + toast. |
| 5 | **Chat persistence** | SQLite on Railway volume. Sufficient for current scale. |
| 6 | **WebSocket on Railway** | Railway supports WS natively. Netlify proxy needs WS passthrough config. |
| 7 | **Mobile/responsive chat** | Chat drawer should work on tablet. Full mobile app is separate. |

---

## Dependencies

- **Phase 1** has zero external dependencies — purely backend + frontend work
- **Phase 2** needs an email provider account (Resend: 5 min setup, free tier sufficient)
- **Phase 3** depends on Phase 2 chat being complete
- **Phase 4** depends on Phases 1-3

No RealPage or Yardi dependencies. No new data pipeline work. This is purely application-layer.
