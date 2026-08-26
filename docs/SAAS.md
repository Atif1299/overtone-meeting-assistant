# Overtone SaaS setup

## Stack
- **Auth:** Supabase (email/password)
- **Billing:** Stripe Checkout + Customer Portal
- **Database:** Postgres (existing Cloud SQL) + new SaaS tables

## Backend env (add to Cloud Run)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
MARKETING_URL=https://overtone-marketing-....run.app
DASHBOARD_URL=https://overtone-v2-dashboard-....run.app
OPEN_DEMO_ACCESS=false
PRESENTER_TOKEN_SECRET=random-long-secret
```

## Stripe setup
1. Create products: Overtone Starter ($10/mo), Overtone Pro ($20/mo)
2. Copy Price IDs to `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PRO`
3. Webhook: `POST /webhooks/stripe` — events: checkout.session.completed, customer.subscription.*

## Supabase setup
1. Create project → enable Email auth
2. Copy URL, anon key, JWT secret from Project Settings → API

## Dashboard env (build-time)
```
VITE_API_BASE=https://overtone-v2-api-....run.app
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Marketing env (build-time)
```
VITE_DASHBOARD_URL=https://overtone-v2-dashboard-....run.app
```

## Plans
| Plan | Launches/mo | Uploads/mo |
|------|-------------|------------|
| Free | 1 | 1 |
| Starter $10 | 5 | 3 |
| Pro $20 | 20 | 10 |

## Deploy order
1. API (`deploy/cloudbuild.api.yaml`) — set new env vars
2. Dashboard — add Supabase Vite vars
3. Marketing (`deploy/cloudbuild.marketing.yaml`)
