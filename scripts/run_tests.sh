#!/bin/bash
# scripts/run_tests.sh — Ejecuta todos los tests localmente
# Funciona desde cualquier cwd: la raíz del repo es el directorio padre de este script.

set -e  # exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.venv/bin/activate"
fi

echo "🧪 AirVLC — Test Suite Local"
echo "=============================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 no encontrado${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Instalando/actualizando dependencias...${NC}"
python3 -m pip install --upgrade pip -q
pip install -r requirements.txt -q

echo -e "${YELLOW}🧪 Ejecutando tests Python...${NC}"
pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    -v \
    --tb=short

TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Tests Python OK${NC}"
    echo -e "${GREEN}📊 Coverage report: file://$(pwd)/htmlcov/index.html${NC}"
else
    echo -e "${RED}❌ Algunos tests fallaron (exit code: $TEST_RESULT)${NC}"
    exit $TEST_RESULT
fi

echo -e "${YELLOW}🐦 Tests Flutter (app/)...${NC}"
if [ -f "app/pubspec.yaml" ]; then
    if command -v flutter &> /dev/null; then
        echo "  → Flutter detectado: flutter pub get + flutter test"
        (cd app && flutter pub get && flutter test)
    else
        echo "  → Flutter no está en PATH: se omiten tests de la app en esta máquina."
        echo "  → En GitHub Actions el job «Tests Flutter (App)» (.github/workflows/flutter-tests.yml) instala el SDK y ejecuta flutter test."
    fi
else
    echo "  → No hay app/pubspec.yaml; sin proyecto Flutter en este repo."
fi

echo -e "${YELLOW}🔍 Linting (ruff)...${NC}"
if command -v ruff &> /dev/null; then
    ruff check src/ tests/ --select=E,W,F,I --ignore=E501,W503 || true
    echo -e "${GREEN}✅ Linting completado (warnings solo informativos)${NC}"
else
    echo -e "${YELLOW}⚠️  ruff no instalado (opcional)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Test suite completado exitosamente${NC}"