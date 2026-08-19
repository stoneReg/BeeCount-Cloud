#!/usr/bin/env bash
# WSL 本地构建 BeeCount-Cloud fork 镜像并部署到 Ubuntu VM (10.10.10.251)。
# 用法: ./scripts/dev/deploy_to_vm251.sh [--skip-build] [--skip-backup]
set -euo pipefail

VM="${BEECOUNT_VM_HOST:-beecount-vm}"
TAG="${BEECOUNT_IMAGE_TAG:-beecount-cloud:fork-local}"
STACK="/opt/stacks/beecloud"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

SKIP_BUILD=false
SKIP_BACKUP=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --skip-backup) SKIP_BACKUP=true ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

cd "$REPO_ROOT"
VERSION="$(git rev-parse --short HEAD)"
echo "==> 版本 fork-${VERSION}  镜像 ${TAG}  目标 ${VM}"

if [[ "$SKIP_BACKUP" != true ]]; then
  echo "==> 备份远端 data ..."
  ssh "$VM" "sudo tar czf ~/beecount-data-backup-\$(date +%F-%H%M).tar.gz -C ${STACK} data && ls -lh ~/beecount-data-backup-*.tar.gz | tail -1"
fi

if [[ "$SKIP_BUILD" != true ]]; then
  echo "==> WSL 构建镜像 (较久) ..."
  docker build --build-arg VERSION="fork-${VERSION}" -t "$TAG" .
fi

echo "==> 推送镜像到 VM ..."
docker save "$TAG" | gzip | ssh "$VM" 'gunzip | docker load'

echo "==> 更新 compose 并重启 ..."
ssh "$VM" "sudo sed -i 's|^    image: .*|    image: ${TAG}|' ${STACK}/compose.yaml && grep 'image:' ${STACK}/compose.yaml"
ssh "$VM" "cd ${STACK} && sudo docker compose up -d"

echo "==> 健康检查 ..."
sleep 5
ssh "$VM" "curl -fsS http://127.0.0.1:8869/healthz && echo && docker exec beecloud-beecount-cloud-1 alembic current && docker exec beecloud-beecount-cloud-1 cat /app/VERSION"

echo "==> 部署完成"
