import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? 'list' : [['list']],

  use: {
    baseURL: process.env.PW_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    launchOptions: {
      args: [
        // MapLibre v6 requires WebGL2, and headless has no GPU. Phase 1 needs
        // this the moment a map is constructed; harmless before then.
        '--enable-unsafe-swiftshader',
      ],
    },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /\.offline\.spec\.ts$/,
    },
    {
      // A browser-level DNS blackhole, and it needs its own project because
      // launchOptions force a new worker and cannot be scoped to a describe block.
      //
      // Why DNS rather than page.route(): the RTL text plugin is fetched by the
      // MapLibre *worker*, not the page, and route interception is not a bet worth
      // taking there. Blackholing at the resolver covers every requester.
      name: 'chromium-offline',
      testMatch: /\.offline\.spec\.ts$/,
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost',
            '--enable-unsafe-swiftshader',
          ],
        },
      },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
