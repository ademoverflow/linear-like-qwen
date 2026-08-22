---
name: new-component
description: Scaffold a new React component following project patterns. Use when creating a UI component.
argument-hint: "<ComponentName>"
---

Scaffold a new React component for the project.

Parse `$ARGUMENTS`: PascalCase component name (required).

If no argument is provided, ask the user for the component name.

## Steps

### 1. Create the component file

Create `webapp/src/components/<ComponentName>.tsx` following project conventions:

```tsx
// 1. Imports
import { useState } from "react";

// 2. Types/Interfaces
interface ComponentNameProps {
  // props here
}

// 3. Component (named export, NOT default export)
export function ComponentName({ ...props }: ComponentNameProps) {
  // 3a. Hooks
  // 3b. Handlers
  // 3c. Render
  return (
    <div>
      {/* component content */}
    </div>
  );
}
```

**Styling:**
- Uses Tailwind CSS utility classes
- Uses `@/` path alias for imports from `src/`

### 2. Run quality checks

Run `make check-webapp` to verify Biome compliance. Fix issues with `pnpm --filter webapp run check --write`.

## Conventions

- **Named exports** only (not default exports)
- **TypeScript interfaces** for props (not `type` aliases)
- **`@/` import alias** for anything from `src/`
- **Functional components** only
- Keep components focused and single-responsibility
