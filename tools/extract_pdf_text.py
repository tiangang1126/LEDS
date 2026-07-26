from pathlib import Path
import sys

import pdfplumber


def main() -> None:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    pages = []
    with pdfplumber.open(input_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            pages.append(f"\n===== PAGE {page_number} =====\n")
            pages.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(pages), encoding="utf-8")
    print(f"pages={len(pages) // 2} output={output_path}")


if __name__ == "__main__":
    main()
