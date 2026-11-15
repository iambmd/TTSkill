import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      { find: /^@\//, replacement: root },
      // `server-only` throws outside Next's server build; route handlers import it via lib/jobs.
      { find: "server-only", replacement: `${root}test/server-only.ts` },
    ],
  },
  test: { environment: "node", include: ["test/**/*.test.ts"] },
});
