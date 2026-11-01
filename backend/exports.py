import csv
import io
from datetime import datetime
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def _val(v):
    if isinstance(v, (list, dict)):
        return str(len(v)) if isinstance(v, list) else ""
    return "" if v is None else str(v)


def export_response(rows, columns, fmt, title):
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    name = f"{title.lower().replace(' ', '_')}_{stamp}"
    headers = [c[1] for c in columns]
    data = [[_val(r.get(c[0])) for c in columns] for r in rows]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        w.writerows(data)
        return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8-sig")), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = title[:30]
        ws.append(headers)
        for d in data:
            ws.append(d)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=24, bottomMargin=20)
    styles = getSampleStyleSheet()
    cell = styles["BodyText"].clone("cell", fontSize=6.5, leading=8)
    table_data = [[Paragraph(f"<b>{h}</b>", cell) for h in headers]] + [[Paragraph(x, cell) for x in d] for d in data]
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DBEAFE")),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build([Paragraph(f"PA Admin — {title} ({len(rows)} records)", styles["Heading2"]),
               Paragraph(f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}", styles["Normal"]), Spacer(1, 8), t])
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


def simple_pdf(title, lines, filename):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 10)]
    for kind, text in lines:
        story.append(Paragraph(text.replace("\n", "<br/>"), styles["Heading3"] if kind == "h" else styles["BodyText"]))
        story.append(Spacer(1, 4))
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{filename}"'})
