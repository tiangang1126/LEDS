from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"


def paragraph_text(paragraph: ET.Element) -> str:
    parts = []
    for node in paragraph.iter():
        if node.tag == f"{W}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{W}tab":
            parts.append("\t")
        elif node.tag in {f"{W}br", f"{W}cr"}:
            parts.append(" / ")
    return "".join(parts).strip()


def paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    return style.get(f"{W}val", "") if style is not None else ""


def main() -> None:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    with ZipFile(input_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W}body")
    lines = []
    paragraph_number = 0
    table_number = 0
    for block in body:
        if block.tag == f"{W}p":
            paragraph_number += 1
            lines.append(
                f"P{paragraph_number:04d}\t[{paragraph_style(block)}]\t{paragraph_text(block)}"
            )
        elif block.tag == f"{W}tbl":
            table_number += 1
            lines.append(f"TABLE {table_number}")
            for row_number, row in enumerate(block.findall(f"{W}tr"), start=1):
                cells = []
                for cell in row.findall(f"{W}tc"):
                    cell_text = " / ".join(
                        filter(None, (paragraph_text(item) for item in cell.findall(f".//{W}p")))
                    )
                    cells.append(cell_text)
                lines.append(f"T{table_number:02d}R{row_number:03d}\t" + "\t".join(cells))
            lines.append(f"END TABLE {table_number}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"paragraphs={paragraph_number} tables={table_number} output={output_path}")


if __name__ == "__main__":
    main()
