# Compose AI

Compose AI is an AI-powered building architecture SaaS for architects, civil engineers, builders, interior designers, and homeowners.

This repository is a production-oriented monorepo foundation for Phase 1.

## Workspace Layout

- `apps/web`: Next.js 15 frontend with TypeScript, Tailwind CSS, and shadcn/ui conventions.
- `apps/api`: FastAPI backend with PostgreSQL, SQLAlchemy, and Alembic.
- `packages/shared`: Shared TypeScript contracts used by frontend packages.
- `infra/docker`: Local infrastructure images and database bootstrap scripts.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Start infrastructure and apps with Docker:

   ```bash
   npm run docker:up
   ```

3. Run the apps directly during development:

   ```bash
   npm install
   npm run dev:web
   npm run dev:api
   ```

## Quality Commands

```bash
npm run lint
npm run typecheck
npm run format:check
npm run test:api
```

Authentication is intentionally not implemented in Phase 1.
