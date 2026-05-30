# Webapp

React single-page application frontend.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | React 19 |
| Language | TypeScript 5.7 |
| Build Tool | Vite 7.1 |
| Routing | TanStack Router |
| Data Fetching | TanStack Query |
| Forms | TanStack React Form |
| Styling | Tailwind CSS 4 |
| Icons | Lucide React |
| Testing | Vitest + Testing Library |
| Linting | Biome |

## Project Structure

```
webapp/
├── src/
│   ├── main.tsx              # App entry point + router setup
│   ├── App.tsx               # Home page component
│   ├── env.ts                # Environment variables (T3 Env)
│   ├── styles.css            # Global styles + Tailwind
│   │
│   ├── pages/                # Page components
│   │   └── About.tsx
│   │
│   ├── integrations/         # Library integrations
│   │   └── tanstack-query/
│   │       └── root-provider.tsx
│   │
│   └── routes/               # (For file-based routing)
│
├── public/                   # Static assets
│   └── favicon.ico
│
├── index.html                # HTML entry point
├── vite.config.ts            # Vite configuration
├── tsconfig.json             # TypeScript config
├── package.json              # Dependencies
├── Dockerfile                # Multi-stage Docker build
└── README.md
```

## Development

### Running Locally

```bash
# Install dependencies
pnpm install

# Start dev server
pnpm dev
```

Dev server runs at `http://localhost:3000`.

### With Docker

```bash
# From repository root
docker compose up webapp
```

Accessible at `http://localhost:8998`.

## Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start development server |
| `pnpm build` | Build for production |
| `pnpm preview` | Preview production build |
| `pnpm test` | Run tests |
| `pnpm lint` | Run linter |
| `pnpm format` | Format code |
| `pnpm check` | Run linter + formatter |

## Environment Variables

Configure in `src/env.ts` using T3 Env with Zod validation.

| Variable | Prefix | Description |
|----------|--------|-------------|
| `VITE_APP_TITLE` | `VITE_` | Application title (client-side) |
| `SERVER_URL` | None | Backend API URL (server-side) |

Usage:

```typescript
import { env } from "@/env";

console.log(env.VITE_APP_TITLE);
```

## Routing

Uses TanStack Router with code-based routing (defined in `main.tsx`).

### Current Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `App` | Home page |
| `/about` | `About` | About page |

### Adding Routes

```typescript
import { createRoute } from "@tanstack/react-router";

const newRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/new-path",
    component: NewComponent,
});

// Add to route tree
const routeTree = rootRoute.addChildren([indexRoute, aboutRoute, newRoute]);
```

### Navigation

```typescript
import { Link } from "@tanstack/react-router";

<Link to="/about">About</Link>
```

## Data Fetching

TanStack Query is pre-configured. Use `useQuery` for data fetching:

```typescript
import { useQuery } from "@tanstack/react-query";

function Component() {
    const { data, isLoading } = useQuery({
        queryKey: ["items"],
        queryFn: () => fetch("/api/items").then(r => r.json()),
    });

    if (isLoading) return <div>Loading...</div>;
    return <div>{JSON.stringify(data)}</div>;
}
```

## Styling

Tailwind CSS 4 with Vite plugin. Write utility classes directly:

```tsx
<div className="flex items-center justify-center p-4 bg-blue-500 text-white">
    Styled content
</div>
```

Global styles in `src/styles.css`.

## Testing

```bash
# Run all tests
pnpm test

# Watch mode
pnpm test --watch
```

Using Vitest + Testing Library:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
    it("renders hello world", () => {
        render(<App />);
        expect(screen.getByText(/hello world/i)).toBeInTheDocument();
    });
});
```

## Code Quality

```bash
# Check linting
pnpm lint

# Format code
pnpm format

# Check both
pnpm check
```

Biome handles both linting and formatting. Config in `/biome.json`.

## Building for Production

```bash
pnpm build
```

Output in `dist/` directory. Preview with:

```bash
pnpm preview
```

## Docker

Multi-stage Dockerfile:

- `dev`: Development with hot reload
- `prod`: Optimized Nginx serving static files

```bash
# Development
docker build --target dev -t webapp:dev .

# Production
docker build --target prod -t webapp:prod .
```

Production image uses Nginx with:
- SPA routing support (try_files)
- Security headers
- Gzip compression
- Non-root user

## Path Aliases

`@/` maps to `src/`:

```typescript
import { env } from "@/env";
import { Component } from "@/components/Component";
```

Configured in `tsconfig.json` and `vite.config.ts`.
