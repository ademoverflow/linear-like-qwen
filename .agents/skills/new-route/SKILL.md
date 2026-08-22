---
name: new-route
description: Scaffold a new TanStack Router route in the webapp. Use when adding a new page.
argument-hint: "<route-path> [page-name]"
---

Scaffold a new frontend route for the project.

Parse `$ARGUMENTS`:
- First arg: route path like `/settings` or `/events/$eventId` (required)
- Second arg: optional page component name (defaults to deriving from the path)

If arguments are missing, ask the user.

## Steps

### 1. Create the page component

Create `webapp/src/pages/<PageName>.tsx` following the pattern in `webapp/src/pages/About.tsx`:

```tsx
export default function PageName() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Page Title</h1>
    </div>
  );
}
```

- Uses Tailwind CSS utility classes
- Uses `@/` path alias for imports from `src/`

For routes with URL params (e.g., `/events/$eventId`), the component can access params via TanStack Router hooks.

### 2. Register in the route tree

Edit `webapp/src/main.tsx`:
- Import the new page component
- Create a new route using `createRoute`:
  ```tsx
  const newRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/path",
    component: PageComponent,
  });
  ```
- Add the route to `rootRoute.addChildren([..., newRoute])`

### 3. Add navigation (if appropriate)

If the route should appear in navigation, add a `<Link to="/path">Label</Link>` element in the appropriate component.

### 4. Run quality checks

Run `make check-webapp` and fix any Biome issues.
