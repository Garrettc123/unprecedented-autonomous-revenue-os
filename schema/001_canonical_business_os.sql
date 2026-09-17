-- Canonical Business OS schema: PostgreSQL 15+
create extension if not exists pgcrypto;

create type execution_state as enum ('active','paused','emergency_stop');
create type action_status as enum ('proposed','blocked','pending_approval','approved','rejected','expired','executing','executed','failed','revoked');
create type risk_class as enum ('observe','recommend','internal_execute','external_execute','financial_or_irreversible');

create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  execution_state execution_state not null default 'paused',
  created_at timestamptz not null default now()
);
create table customers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  external_ref text,
  name text,
  email text,
  phone text,
  created_at timestamptz not null default now(),
  unique (organization_id, external_ref)
);
create table opportunities (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  customer_id uuid references customers(id),
  source_event_id uuid,
  stage text not null default 'new',
  estimated_value numeric(14,2),
  currency char(3) not null default 'USD',
  created_at timestamptz not null default now()
);
create table business_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  provider text not null,
  provider_event_id text not null,
  event_type text not null,
  payload jsonb not null,
  payload_hash text not null,
  received_at timestamptz not null default now(),
  unique (organization_id, provider, provider_event_id)
);
create table policies (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  version integer not null,
  rules jsonb not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, version)
);
create table action_proposals (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  opportunity_id uuid references opportunities(id),
  action_type text not null,
  risk risk_class not null,
  payload jsonb not null,
  payload_hash text not null,
  evidence jsonb not null default '[]'::jsonb,
  expected_value numeric(14,2),
  currency char(3) not null default 'USD',
  policy_id uuid references policies(id),
  policy_decision text not null,
  status action_status not null default 'proposed',
  idempotency_key text not null unique,
  expires_at timestamptz,
  revision integer not null default 1,
  created_at timestamptz not null default now()
);
create table approvals (
  id uuid primary key default gen_random_uuid(),
  proposal_id uuid not null references action_proposals(id),
  approver_id uuid not null,
  decision text not null check (decision in ('approved','rejected')),
  reason text,
  proposal_hash text not null,
  policy_version integer not null,
  decided_at timestamptz not null default now(),
  unique (proposal_id, approver_id)
);
create table executions (
  id uuid primary key default gen_random_uuid(),
  proposal_id uuid not null unique references action_proposals(id),
  provider text not null,
  provider_request_id text,
  provider_receipt jsonb,
  status action_status not null,
  error_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create table outcomes (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id),
  opportunity_id uuid references opportunities(id),
  proposal_id uuid references action_proposals(id),
  outcome_type text not null,
  attribution text not null check (attribution in ('direct','assisted','unattributed')),
  value numeric(14,2),
  currency char(3) not null default 'USD',
  evidence jsonb not null default '[]'::jsonb,
  occurred_at timestamptz not null default now()
);
create index on business_events (organization_id, received_at desc);
create index on action_proposals (organization_id, status, created_at desc);
create index on outcomes (organization_id, occurred_at desc);
