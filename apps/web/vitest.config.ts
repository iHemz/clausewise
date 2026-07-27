import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  test: {
    // `describe`/`it`/`expect` available without an import in every test file.
    // Paired with "types": ["vitest/globals"] in tsconfig so tsc sees them too.
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['{app,components,lib,hooks}/**/*.test.{ts,tsx}'],
  },
  resolve: {
    // Mirror the tsconfig "@/*" -> "./*" alias.
    alias: { '@': path.resolve(process.cwd()) },
  },
});
