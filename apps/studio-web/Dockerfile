FROM node:22-alpine AS dependencies
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/studio-web/package.json apps/studio-web/package.json
COPY packages/design-system/package.json packages/design-system/package.json
RUN npm ci --legacy-peer-deps

FROM node:22-alpine AS builder
WORKDIR /workspace
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=dependencies /workspace/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY apps/studio-web apps/studio-web
COPY packages/design-system packages/design-system
RUN npm run build --workspace @story-studio/web

FROM node:22-alpine AS runtime
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S studio && adduser -S studio -G studio
WORKDIR /app
COPY --from=builder --chown=studio:studio /workspace/apps/studio-web/.next/standalone ./
COPY --from=builder --chown=studio:studio /workspace/apps/studio-web/.next/static ./apps/studio-web/.next/static
COPY --from=builder --chown=studio:studio /workspace/apps/studio-web/public ./apps/studio-web/public
USER studio
EXPOSE 3000
CMD ["node", "apps/studio-web/server.js"]

