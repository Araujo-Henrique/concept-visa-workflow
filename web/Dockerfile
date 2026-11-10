# Front (Next.js). Contexto de build: a pasta web/.
FROM node:24-slim AS dependencias
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: o "prepare" instala o husky (git hooks), que não existe nem faz sentido na imagem
RUN npm ci --ignore-scripts

FROM node:24-slim AS construir
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencias /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-slim AS rodar
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# "standalone": o Next copia só o que precisa para rodar (sem node_modules inteiro)
COPY --from=construir --chown=node:node /app/.next/standalone ./
COPY --from=construir --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
