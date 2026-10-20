# Build from the typescript/ workspace: docker build -f packages/waf-worker/Dockerfile .
FROM oven/bun:1.4.3
USER root
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
COPY packages/client/package.json ./packages/client/package.json
COPY packages/mcp/package.json ./packages/mcp/package.json
COPY packages/waf-session/package.json ./packages/waf-session/package.json
COPY packages/waf-worker/package.json ./packages/waf-worker/package.json
RUN bun install --frozen-lockfile --production --filter @patent-client-agents/waf-worker
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN bun packages/waf-worker/node_modules/playwright/cli.js install --with-deps chromium \
    && chmod -R a+rX /opt/playwright-browsers
COPY packages/client/src ./packages/client/src
COPY packages/waf-session/src ./packages/waf-session/src
COPY packages/waf-worker/src ./packages/waf-worker/src
USER bun
CMD ["bun", "packages/waf-worker/src/cli.ts"]
