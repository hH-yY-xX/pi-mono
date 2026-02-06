#!/bin/bash
# Development scripts for pi-coding-agent

set -e

case "$1" in
    "install")
        pip install -e .
        ;;
    "test")
        pytest tests/ -v
        ;;
    "format")
        black pi_coding_agent/ tests/ examples/
        ;;
    "lint")
        pylint pi_coding_agent/
        ;;
    "type-check")
        mypy pi_coding_agent/
        ;;
    "clean")
        rm -rf build/ dist/ *.egg-info/
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -delete
        ;;
    *)
        echo "Usage: $0 {install|test|format|lint|type-check|clean}"
        exit 1
        ;;
esac