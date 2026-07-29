# -*- coding: utf-8 -*-
"""List DOCX drawing order, media targets, display size, and effective DPI."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "a": A, "wp": WP, "r": R, "pr": PR}


def text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()


def main() -> None:
    path = Path(sys.argv[1])
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        rel_root = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        rels = {
            item.get("Id"): item.get("Target")
            for item in rel_root.findall("pr:Relationship", NS)
        }
        drawing_no = 0
        for p_no, paragraph in enumerate(root.findall(".//w:body/w:p", NS), start=1):
            for drawing in paragraph.findall(".//w:drawing", NS):
                drawing_no += 1
                blip = drawing.find(".//a:blip", NS)
                extent = drawing.find(".//wp:extent", NS)
                doc_pr = drawing.find(".//wp:docPr", NS)
                rid = blip.get(f"{{{R}}}embed") if blip is not None else None
                target = rels.get(rid, "")
                member = "word/" + target.lstrip("/")
                width_in = int(extent.get("cx")) / 914400 if extent is not None else 0
                height_in = int(extent.get("cy")) / 914400 if extent is not None else 0
                if member in archive.namelist():
                    image = Image.open(io.BytesIO(archive.read(member)))
                    px_w, px_h = image.size
                    dpi_x = px_w / width_in if width_in else 0
                    dpi_y = px_h / height_in if height_in else 0
                else:
                    px_w = px_h = dpi_x = dpi_y = 0
                print(
                    f"D{drawing_no:02d}\tP{p_no:04d}\t{rid}\t{target}\t"
                    f"{px_w}x{px_h}\t{width_in:.3f}x{height_in:.3f}in\t"
                    f"{dpi_x:.1f}x{dpi_y:.1f}dpi\t"
                    f"{doc_pr.get('name', '') if doc_pr is not None else ''}\t{text(paragraph)}"
                )


if __name__ == "__main__":
    main()
