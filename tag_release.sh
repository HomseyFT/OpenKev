#!/bin/bash
# tag_release.sh — creates and pushes a signed annotated tag for OpenKev v1

set -e

TAG="v1.0.0"
MESSAGE="OpenKev v1.0.0 — initial demo release

Includes:
- KevPilot: Ollama-backed AI chat
- Wei Word: rich-text .kev document editor
- Kevcel: spreadsheet with formula engine
- Kevin Compressor: DCT + Huffman image compression
- Kev Teams: WebSocket messaging via relay server
- Navigator: tabbed app launcher and sidebar"

echo "Creating annotated tag $TAG..."
git tag -a "$TAG" -m "$MESSAGE"

echo "Pushing tag to origin..."
git push origin "$TAG"

echo "Done! $TAG is live."
