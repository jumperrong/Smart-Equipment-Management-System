import io
import os
import logging
from datetime import datetime
from typing import Optional

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import Color, red, white, gray
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab 未安装，PDF 水印功能已降级（返回原文件）")

try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter
        PYPDF2_AVAILABLE = True
    except ImportError:
        PYPDF2_AVAILABLE = False
        logger.warning("PyPDF2/pypdf 未安装，PDF 水印功能已降级（返回原文件）")


def watermark_pdf_bytes(pdf_bytes: bytes, watermark_text: str, extra_lines: list[str] = []) -> bytes:
    if not REPORTLAB_AVAILABLE or not PYPDF2_AVAILABLE:
        logger.warning("PDF 水印依赖缺失，返回原始 PDF 字节")
        return pdf_bytes

    try:
        original_pdf = PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(original_pdf.pages)
        output_pdf = PdfWriter()

        for page_idx in range(num_pages):
            page = original_pdf.pages[page_idx]
            try:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
            except Exception:
                page_width, page_height = A4

            wm_buf = io.BytesIO()
            c = canvas.Canvas(wm_buf, pagesize=(page_width, page_height))

            try:
                c.saveState()
                c.translate(page_width / 2, page_height / 2)
                c.rotate(35)
                c.setFillColor(Color(0.85, 0.85, 0.85, alpha=0.1))
                c.setFont("Helvetica-Bold", 24)
                text_width = c.stringWidth(watermark_text, "Helvetica-Bold", 24)
                c.drawString(-text_width / 2, 0, watermark_text)
                c.restoreState()
            except Exception as e:
                logger.warning(f"绘制水印文字失败: {e}")

            try:
                stamp_text = "受 控 文 件"
                stamp_font_size = 16
                stamp_padding_x = 12
                stamp_padding_y = 6
                c.setFont("Helvetica-Bold", stamp_font_size)
                stamp_text_width = c.stringWidth(stamp_text, "Helvetica-Bold", stamp_font_size)
                stamp_box_w = stamp_text_width + stamp_padding_x * 2
                stamp_box_h = stamp_font_size + stamp_padding_y * 2
                stamp_x = page_width - stamp_box_w - 20
                stamp_y = page_height - stamp_box_h - 20

                c.setFillColor(red)
                c.rect(stamp_x, stamp_y, stamp_box_w, stamp_box_h, fill=1, stroke=0)
                c.setFillColor(white)
                c.drawString(stamp_x + stamp_padding_x, stamp_y + stamp_padding_y, stamp_text)
            except Exception as e:
                logger.warning(f"绘制受控章失败: {e}")

            try:
                page_no_text = f"第 {page_idx + 1} 页 / 共 {num_pages} 页"
                c.setFont("Helvetica", 9)
                c.setFillColor(gray)
                c.drawCentredString(page_width / 2, 18, page_no_text)
            except Exception as e:
                logger.warning(f"绘制页码失败: {e}")

            try:
                if extra_lines:
                    c.setFont("Helvetica", 8)
                    c.setFillColor(gray)
                    line_y = 36
                    for line in reversed(extra_lines):
                        c.drawString(20, line_y, str(line))
                        line_y += 12
            except Exception as e:
                logger.warning(f"绘制附加信息失败: {e}")

            c.save()
            wm_buf.seek(0)

            try:
                wm_pdf = PdfReader(wm_buf)
                wm_page = wm_pdf.pages[0]
                page.merge_page(wm_page)
            except Exception as e:
                logger.warning(f"合并水印页失败: {e}")

            output_pdf.add_page(page)

        out_buf = io.BytesIO()
        output_pdf.write(out_buf)
        return out_buf.getvalue()

    except Exception as e:
        logger.warning(f"PDF 水印处理失败，返回原始文件: {e}")
        return pdf_bytes


def serve_watermarked_pdf(file_path, doc_info, current_user):
    doc_no = doc_info.get("doc_no")
    doc_name = doc_info.get("doc_name") or "document"
    status = doc_info.get("status") or "-"

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    watermark_text = f"受控 · {current_user.username} · {today_str}"
    extra_lines = [
        f'文档编号: {doc_no or "-"}',
        f'文档: {doc_name}',
        f'状态: {status}',
        f'仅供: {current_user.username} 使用 - 打印即失效',
    ]

    abs_path = os.path.abspath(file_path)
    with open(abs_path, "rb") as f:
        pdf_bytes = f.read()

    wm_bytes = watermark_pdf_bytes(pdf_bytes, watermark_text, extra_lines)

    filename = f"{doc_no or doc_name}.pdf"
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
    }
    return StreamingResponse(
        io.BytesIO(wm_bytes),
        media_type="application/pdf",
        headers=headers,
    )
