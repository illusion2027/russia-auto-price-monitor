"""Render the repository's own vector icon into PWA PNG sizes."""
from pathlib import Path
import fitz
root = Path(__file__).resolve().parents[1]
with fitz.open(root / 'public/icon.svg') as document:
    page = document[0]
    for size, name in [(180, 'apple-touch-icon.png'), (192, 'icon-192.png'), (512, 'icon-512.png')]:
        page.get_pixmap(matrix=fitz.Matrix(size / page.rect.width, size / page.rect.height), alpha=False).save(root / 'public' / name)
