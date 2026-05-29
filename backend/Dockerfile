FROM node:22-alpine AS deps

WORKDIR /service

RUN npm install -g pnpm@10.0.0

COPY package.json pnpm-lock.yaml* ./

RUN pnpm install --frozen-lockfile=false

FROM node:22-alpine AS build

WORKDIR /service

RUN npm install -g pnpm@10.0.0

COPY --from=deps /service/node_modules ./node_modules
COPY . .

ENV DATABASE_URL=postgresql://ml_wink:ml_wink_password@postgres:5432/ml_wink?schema=public
RUN pnpm prisma:generate
RUN pnpm build

FROM node:22-alpine AS runner

WORKDIR /service

ENV NODE_ENV=production

COPY --from=build /service/node_modules ./node_modules
COPY --from=build /service/assets ./assets
COPY --from=build /service/dist ./dist
COPY --from=build /service/prisma ./prisma
COPY --from=build /service/prisma.config.ts ./prisma.config.ts
COPY --from=build /service/package.json ./package.json

EXPOSE 8000

CMD ["node", "dist/src/main.js"]
