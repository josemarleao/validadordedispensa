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

# Configurar variáveis de ambiente da IA (só executa se OPENROUTER_API_KEY estiver definida no shell)
if [ -n "$OPENROUTER_API_KEY" ]; then
  echo ""
  echo "🤖 Configurando variáveis de IA no container..."
  IA_MODEL_VALUE="${IA_MODEL:-openrouter/free}"
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
      OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
      IA_ENABLED="true" \
      IA_MODEL="$IA_MODEL_VALUE" \
    --output none
  echo "✅ IA habilitada (modelo: $IA_MODEL_VALUE)"
fi

echo ""
echo "🌐 API disponível em:"
echo "   $URL/docs"
