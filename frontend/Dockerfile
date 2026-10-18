FROM node:22.19.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --global npm@11.6.2 && npm ci --no-audit --no-fund
COPY . .
ARG PORTAL_BUILD_IDDQD=0
RUN PORTAL_BUILD_IDDQD="$PORTAL_BUILD_IDDQD" npm run build \
    && cp nginx.arcade-disabled.conf /tmp/portal-arcade.conf \
    && if [ "$PORTAL_BUILD_IDDQD" = "1" ]; then cp nginx.arcade.conf /tmp/portal-arcade.conf; fi

FROM nginx:1.29.1-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /tmp/portal-arcade.conf /etc/nginx/portal-arcade.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
