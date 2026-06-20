FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Copy built files to shared volume
FROM alpine:3.19
COPY --from=build /app/dist /output-stage

CMD ["cp", "-r", "/output-stage/.", "/output/"]
