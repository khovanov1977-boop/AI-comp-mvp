FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json /app/
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/shared/package.json /app/packages/shared/package.json
RUN npm ci
COPY apps/web /app/apps/web
COPY packages/shared /app/packages/shared
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build --workspace apps/web
RUN npm prune --omit=dev

FROM node:22-alpine
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build /app/package.json /app/package.json
COPY --from=build /app/package-lock.json /app/package-lock.json
COPY --from=build /app/node_modules /app/node_modules
COPY --chown=node:node --from=build /app/apps/web /app/apps/web
COPY --chown=node:node --from=build /app/packages/shared /app/packages/shared
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "apps/web"]
