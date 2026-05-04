#!/usr/bin/env bash
# Script para descargar y verificar Flutter SDK en macOS

set -e

FLUTTER_VERSION="3.19.6" # O la última versión estable preferida
INSTALL_DIR="$HOME/development"
FLUTTER_DIR="$INSTALL_DIR/flutter"

echo "============================================="
echo "📱 Configuración del Entorno Flutter (macOS)"
echo "============================================="

# 1. Crear directorio
mkdir -p "$INSTALL_DIR"

# 2. Descargar Flutter si no existe
if [ -d "$FLUTTER_DIR" ]; then
    echo "✅ Flutter ya está descargado en $FLUTTER_DIR"
else
    echo "⬇️ Descargando Flutter SDK (estable)..."
    cd "$INSTALL_DIR"
    curl -O "https://storage.googleapis.com/flutter_infra_release/releases/stable/macos/flutter_macos_arm64_${FLUTTER_VERSION}-stable.zip"
    echo "📦 Extrayendo SDK..."
    unzip -q "flutter_macos_arm64_${FLUTTER_VERSION}-stable.zip"
    rm "flutter_macos_arm64_${FLUTTER_VERSION}-stable.zip"
    echo "✅ Flutter descargado y extraído."
fi

# 3. Añadir al PATH (temporalmente para este script, y avisar para .zshrc)
export PATH="$PATH:$FLUTTER_DIR/bin"

if ! grep -q "$FLUTTER_DIR/bin" "$HOME/.zshrc"; then
    echo "🔧 Añadiendo Flutter a ~/.zshrc..."
    echo "" >> "$HOME/.zshrc"
    echo "# Flutter SDK" >> "$HOME/.zshrc"
    echo "export PATH=\"\$PATH:$FLUTTER_DIR/bin\"" >> "$HOME/.zshrc"
    echo "⚠️  Nota: Cierra y abre la terminal o ejecuta 'source ~/.zshrc' para aplicar los cambios."
fi

# 4. Flutter Doctor
echo "🩺 Ejecutando flutter doctor para comprobar dependencias de macOS y iOS..."
flutter doctor

echo "============================================="
echo "🎉 Proceso finalizado. Revisa el resultado de flutter doctor."
echo "   Para compilar en iOS, asegúrate de tener Xcode instalado."
echo "   Para Android, instala Android Studio."
echo "============================================="
