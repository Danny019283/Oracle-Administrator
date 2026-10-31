#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

docker compose up -d

echo "Esperando a que Oracle esté listo (puede tardar varios minutos)..."
until docker logs oracle21c 2>&1 | grep -q "DATABASE IS READY TO USE"; do
  sleep 5
done
docker exec -u root oracle21c sh -c "pgrep -x crond >/dev/null 2>&1 || crond" || echo "Aviso: no se pudo arrancar crond; los respaldos programados no se dispararán hasta que lo arranques"
echo "Oracle listo en localhost:1521"
