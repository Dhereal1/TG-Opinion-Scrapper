#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Run this script with: source scripts/activate_venv.sh"
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
REQ_FILE="${PROJECT_ROOT}/requirements.txt"

if [[ ! -f "${VENV_PATH}/bin/activate" ]]; then
  if [[ -d "${PROJECT_ROOT}/venv-win" ]]; then
    echo "Found Windows venv-win. In bash/WSL, use Linux venv instead."
  fi

  PYTHON_CMD="python3"
  if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python"
  fi

  if ! command -v "${PYTHON_CMD}" >/dev/null 2>&1; then
    echo "Python is not installed or not in PATH."
    return 1
  fi

  echo "Creating venv..."
  "${PYTHON_CMD}" -m venv "${VENV_PATH}"

  echo "Installing dependencies..."
  "${VENV_PATH}/bin/pip" install -r "${REQ_FILE}"
fi

source "${VENV_PATH}/bin/activate"
echo "Activated virtual environment: ${VENV_PATH}"
