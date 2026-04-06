#!/usr/bin/env python3
"""
PDF dergi → Markdown dönüştürücü
Kullanım:
    python pdf_to_md.py /klasor/pdfs/          # klasördeki tüm PDF'ler
    python pdf_to_md.py dosya.pdf              # tek dosya
    python pdf_to_md.py /klasor/ --outdir ./md --skip-existing
    python pdf_to_md.py /klasor/ --dpi 200     # daha hızlı, biraz daha düşük kalite
    python pdf_to_md.py /klasor/ --lang tur+eng
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import argparse
import glob as _glob
import io
import re
import sys
from pathlib import Path

# ── Bağımlılıklar ─────────────────────────────────────────────────────────────
try:
    import fitz
except ImportError:
    sys.exit("Hata: PyMuPDF yüklü değil.  pip install pymupdf")

try:
    from PIL import Image
    import easyocr
except ImportError:
    sys.exit("Hata: easyocr/Pillow yüklü değil.  pip install easyocr pillow")

# ── EasyOCR reader (GPU otomatik kullanılır) ──────────────────────────────────
print("EasyOCR başlatılıyor (ilk seferde model indirilir)...", flush=True)
_reader: easyocr.Reader | None = None

def get_reader(lang: str) -> easyocr.Reader:
    global _reader
    if _reader is None:
        # EasyOCR dil kodu: tur → tr, eng → en
        lang_map = {"tur": "tr", "eng": "en", "tr": "tr", "en": "en"}
        langs = [lang_map.get(l, l) for l in lang.split("+")]
        _reader = easyocr.Reader(langs, gpu=True)
        print(f"  EasyOCR hazir — diller: {langs}", flush=True)
    return _reader

# ── Yapılandırma ──────────────────────────────────────────────────────────────
MARGIN_TOP_PX    = 80
MARGIN_BOTTOM_PX = 80

SKIP_PATTERNS = [
    r"^\s*\d{1,2}\s*$",
    r"^B[İI]L[İI]M\s+[Vv][Ee]\s+TEKN[İI]K\s*$",
    r"^AYLIK\s+POP[ÜU]LER\s+DERG[İI]\s*$",
    r"^(SAYI|C[İI]LT)\s*[:\d]",
]

UPPERCASE_RATIO_HEADING = 0.70
MIN_HEADING_LEN = 4
MAX_HEADING_LEN = 80

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def render_page(page, dpi: int) -> Image.Image:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    w, h = img.size
    top    = MARGIN_TOP_PX
    bottom = max(top + 100, h - MARGIN_BOTTOM_PX)
    return img.crop((0, top, w, bottom))


def ocr_image(img: Image.Image, lang: str) -> str:
    import numpy as np
    reader = get_reader(lang)
    results = reader.readtext(np.array(img), detail=0, paragraph=True)
    return "\n".join(results)


def should_skip(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return any(re.match(p, s, re.IGNORECASE) for p in SKIP_PATTERNS)


def detect_heading(line: str):
    s = line.strip()
    if not s or not (MIN_HEADING_LEN <= len(s) <= MAX_HEADING_LEN):
        return None
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return None
    ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if ratio >= UPPERCASE_RATIO_HEADING:
        if len(s) <= 25:   return "#"
        elif len(s) <= 50: return "##"
        else:              return "###"
    return None


def fix_hyphenation(text: str) -> str:
    return re.sub(r"-\n([a-züöçşığA-ZÜÖÇŞİĞ])", r"\1", text)


def clean_line(line: str) -> str:
    line = re.sub(r"  +", " ", line)
    return line.rstrip()


def to_markdown(raw: str) -> str:
    text  = fix_hyphenation(raw)
    lines = text.split("\n")
    out   = []
    blanks = 0
    for line in lines:
        line = clean_line(line)
        if not line.strip():
            blanks += 1
            if blanks == 1:
                out.append("")
            continue
        blanks = 0
        if should_skip(line):
            continue
        level = detect_heading(line)
        if level:
            out.append(f"\n{level} {line.strip()}\n")
        else:
            out.append(line)
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def pdf_to_markdown(pdf_path: Path, out_path: Path, dpi: int, lang: str) -> None:
    import numpy as np
    doc   = fitz.open(str(pdf_path))
    total = len(doc)
    print(f"  [{pdf_path.name}] {total} sayfa render ediliyor...", end="", flush=True)

    # 1) Tüm sayfaları CPU'da numpy array olarak hazırla
    imgs = []
    for i, page in enumerate(doc):
        if i == 0:
            imgs.append(None)  # kapak
        else:
            imgs.append(np.array(render_page(page, dpi)))
        print(".", end="", flush=True)
    doc.close()
    print(" OCR...", end="", flush=True)

    # 2) GPU'da OCR
    reader = get_reader(lang)
    pages  = ["<!-- KAPAK -->"]
    for i, img in enumerate(imgs[1:], start=1):
        try:
            results = reader.readtext(img, detail=0, paragraph=True)
            md = to_markdown("\n".join(results))
            pages.append(f"<!-- sayfa {i+1} -->\n\n{md}")
        except Exception as e:
            pages.append(f"<!-- sayfa {i+1} HATA: {e} -->")
        print(".", end="", flush=True)

    print(" OK")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n---\n\n".join(pages), encoding="utf-8")


# ── Ana program ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PDF dergi -> Markdown")
    parser.add_argument("input", nargs="?", default=".",
                        help="PDF dosyasi, klasor veya glob deseni")
    parser.add_argument("--dpi",          type=int, default=300)
    parser.add_argument("--lang",         default="tur")
    parser.add_argument("--outdir",       default="./markdown")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Zaten var olan .md dosyalarini atla")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    inp    = Path(args.input)

    if inp.is_dir():
        pdfs = sorted(inp.glob("*.pdf"))
    elif inp.is_file() and inp.suffix.lower() == ".pdf":
        pdfs = [inp]
    else:
        pdfs = sorted(Path(p) for p in _glob.glob(str(inp)) if p.endswith(".pdf"))

    if not pdfs:
        sys.exit("Hic PDF bulunamadi.")

    print(f"\n{len(pdfs)} PDF dosyasi bulundu -> '{outdir}' klasorune yazilacak")
    print(f"   DPI: {args.dpi} | Dil: {args.lang}\n")

    for pdf in pdfs:
        out = outdir / pdf.with_suffix(".md").name
        if args.skip_existing and out.exists():
            print(f"  [ATLA] {pdf.name}")
            continue
        try:
            pdf_to_markdown(pdf, out, args.dpi, args.lang)
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            sys.exit(0)
        except Exception as e:
            print(f"\n  [HATA] {pdf.name}: {e}")

    print(f"\nTamamlandi. Dosyalar: {outdir}/")


if __name__ == "__main__":
    main()