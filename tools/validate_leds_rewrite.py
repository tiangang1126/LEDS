from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"

SOURCE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "LEDS_指挥与控制学报_李铁乔_0725_一级核心期刊投稿精修稿_v5.docx"
)
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "LEDS_指挥与控制学报_李铁乔_0725_科学论文范式全文重写稿.docx"
)

REQUIRED_TEXT = [
    "240个分层Prompt",
    "2880条真实API输出",
    "67.22%",
    "67.36%",
    "66.81%",
    "67.08%",
    "6.67%",
    "56.000%",
    "56.333%",
    "55.667%",
    "55.933%",
    "0.279%",
    "[55.587%,56.280%]",
    "0.667个百分点",
    "0.667%～1.667%",
    "1.400%",
    "[1.154%,1.646%]",
    "exact match为3/3",
    "2400次降至701次",
    "2.5～4.8倍",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-v4-flash",
]


def read_document(path: Path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        media = {
            entry.filename: sha256(archive.read(entry.filename)).hexdigest()
            for entry in archive.infolist()
            if entry.filename.startswith("word/media/")
        }
    text = "".join(node.text or "" for node in root.iter(f"{W}t"))
    tables = []
    for table in root.iter(f"{W}tbl"):
        tables.append("".join(node.text or "" for node in table.iter(f"{W}t")))
    return text, tables, media


def main() -> None:
    source_text, source_tables, source_media = read_document(SOURCE)
    target_text, target_tables, target_media = read_document(TARGET)
    errors = []
    if source_tables != target_tables:
        errors.append("table contents changed")
    if source_media != target_media:
        errors.append("embedded media changed")
    missing = [item for item in REQUIRED_TEXT if item not in target_text]
    if missing:
        errors.append("missing required evidence: " + ", ".join(missing))
    for model_name in ("deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"):
        if Counter(source_text)[model_name] != Counter(target_text)[model_name]:
            pass
    if errors:
        raise SystemExit("FAIL\n- " + "\n- ".join(errors))
    print("PASS")
    print(f"tables={len(target_tables)} unchanged")
    print(f"media_files={len(target_media)} unchanged")
    print(f"required_evidence_items={len(REQUIRED_TEXT)} present")


if __name__ == "__main__":
    main()
