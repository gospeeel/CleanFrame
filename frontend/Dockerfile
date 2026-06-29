ARG NODE_BASE_IMAGE=mirror.gcr.io/library/node:22-alpine

FROM ${NODE_BASE_IMAGE} AS deps

WORKDIR /service

RUN npm install -g pnpm@10.0.0

COPY package.json pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile=false

FROM ${NODE_BASE_IMAGE} AS build

WORKDIR /service

RUN npm install -g pnpm@10.0.0

COPY --from=deps /service/node_modules ./node_modules
COPY . .

RUN pnpm build

FROM ${NODE_BASE_IMAGE} AS runner

WORKDIR /service

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

COPY --from=build /service/.output ./.output

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
