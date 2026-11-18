FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . ./
RUN npm run build
CMD ["sh", "-c", "cp -r build/. /app/result_build/"]
