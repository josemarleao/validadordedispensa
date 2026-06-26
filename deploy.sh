#!/bin/bash
set -e

BASE_IMAGE="dccl/saneamento-pdf"
TAG=$(date +%Y%m%d%H%M%S)
IMAGE="$BASE_IMAGE:$TAG"
IMAGE_LATEST="$BASE_IMAGE:latest"
APP_NAME="saneamento-pdf"
RESOURCE_GROUP="mpba-saneamento"
URL="https://saneamento-pdf.purplemoss-25ff039e.brazilsouth.azurecontainerapps.io"

echo "🔨 Build da imagem para linux/amd64 (tag: $TAG)..."
docker buildx build \
  --platform linux/amd64 \
  --cache-from "type=registry,ref=$IMAGE_LATEST" \
  --cache-to "type=inline" \
  -t "$IMAGE" \
  -t "$IMAGE_LATEST" \
  --push \
  .
echo "✅ Build e push concluídos"

echo ""
echo "🚀 Atualizando Azure Container Apps..."
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$IMAGE" \
  --output none
echo "✅ Deploy concluído (revisão com imagem $IMAGE)"

# Configurar variável do fluxo de processamento (só executa se POWER_AUTOMATE_PROCESSO_URL estiver definida no shell)
if [ -n "$POWER_AUTOMATE_PROCESSO_URL" ]; then
  echo ""
  echo "🤖 Configurando fluxo Power Automate no container..."
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
      POWER_AUTOMATE_PROCESSO_URL="$POWER_AUTOMATE_PROCESSO_URL" \
    --output none
  echo "✅ Fluxo Power Automate configurado"
fi

echo ""
echo "🌐 API disponível em:"
echo "   $URL/docs"
