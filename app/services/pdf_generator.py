import io
import math
import base64
import re
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph as RichParagraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image as RLImage
)
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Page layout setup
PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

# Colors - Curated Teal / Slate color scheme matching frontend aesthetics
C_DARK = colors.HexColor("#0f172a")
C_PRIMARY = colors.HexColor("#0f766e")
C_WHITE = colors.white
C_GRAY50 = colors.HexColor("#f9fafb")
C_GRAY100 = colors.HexColor("#f3f4f6")
C_GRAY200 = colors.HexColor("#e5e7eb")
C_GRAY400 = colors.HexColor("#9ca3af")
C_GRAY600 = colors.HexColor("#4b5563")
C_GRAY800 = colors.HexColor("#1f2937")

# Typography helper
def S(name, **kw):
    return ParagraphStyle(name, **kw)

# Standard Paragraph Styles
TITLE = S('title', fontName='Helvetica-Bold', fontSize=22, leading=26, textColor=C_WHITE, alignment=TA_CENTER)
SUB = S('sub', fontName='Helvetica', fontSize=9.5, leading=14, textColor=C_GRAY200, alignment=TA_CENTER)
H1 = S('h1', fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=C_DARK, spaceBefore=12, spaceAfter=6, keepWithNext=True)
H2 = S('h2', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=C_PRIMARY, spaceBefore=10, spaceAfter=4, keepWithNext=True)
BODY = S('body', fontName='Helvetica', fontSize=8.5, leading=12, textColor=C_GRAY600)
BODYB = S('bodyb', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_GRAY800)

# Table cell styles
TC = S('tc', fontName='Helvetica', fontSize=8, leading=11, textColor=C_GRAY600, alignment=TA_LEFT)
TCB = S('tcb', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=C_GRAY800, alignment=TA_LEFT)
TCC = S('tcc', fontName='Helvetica', fontSize=8, leading=11, textColor=C_GRAY600, alignment=TA_CENTER)
TCCB = S('tccb', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=C_GRAY800, alignment=TA_CENTER)
TCR = S('tcr', fontName='Helvetica', fontSize=8, leading=11, textColor=C_GRAY600, alignment=TA_RIGHT)
TCRB = S('tcrb', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=C_GRAY800, alignment=TA_RIGHT)

# Table header styles
TCH = S('tch', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_WHITE, alignment=TA_CENTER)
TCHL = S('tchl', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_WHITE, alignment=TA_LEFT)
TCHR = S('tchr', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_WHITE, alignment=TA_RIGHT)

# Highlight styles
TCPRI = S('tcpri', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_PRIMARY, alignment=TA_LEFT)
TCPRIC = S('tcpric', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=C_PRIMARY, alignment=TA_CENTER)

def sanitize_html_for_reportlab(text):
    """
    Sanitize text containing HTML or special characters for ReportLab Paragraphs.
    Converts supported styling tags into valid ReportLab XML, cleans invalid tags,
    replaces unrenderable unicode currency symbols, and escapes lone ampersands.
    """
    if text is None:
        return ""
    text = str(text)
    if not text.strip():
        return ""

    # Replace Rupee symbol with 'Rs. ' to avoid missing glyph square in Helvetica
    text = re.sub(r'₹\s*', 'Rs. ', text)
    # Normalize common HTML formatting tags
    text = re.sub(r'<br\s*/?>', '<br/>', text, flags=re.IGNORECASE)
    text = re.sub(r'<strong\b[^>]*>', '<b>', text, flags=re.IGNORECASE)
    text = re.sub(r'</strong>', '</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'<em\b[^>]*>', '<i>', text, flags=re.IGNORECASE)
    text = re.sub(r'</em>', '</i>', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>\s*<p\b[^>]*>', '<br/><br/>', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p\b[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(?:span|div)\b[^>]*>', '', text, flags=re.IGNORECASE)
    # Escape standalone '&' not part of a valid XML entity
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)

    allowed_pattern = re.compile(
        r'^(?:</?(?:b|i|u|sub|super|font|color)(?:\s+[^>]*)?>|<br/>)$',
        re.IGNORECASE
    )

    parts = re.split(r'(<[^>]+>)', text)
    result = []
    open_tags = []
    for part in parts:
        if not part:
            continue
        if part.startswith('<') and part.endswith('>'):
            if allowed_pattern.match(part):
                tag_name_match = re.match(r'^</?([a-zA-Z]+)', part)
                if tag_name_match:
                    tag_name = tag_name_match.group(1).lower()
                    if part.startswith('</'):
                        if tag_name in open_tags:
                            open_tags.remove(tag_name)
                            result.append(f'</{tag_name}>')
                    elif not part.endswith('/>'):
                        open_tags.append(tag_name)
                        result.append(part)
                    else:
                        result.append(part)
            else:
                part_escaped = part.replace('<', '&lt;').replace('>', '&gt;')
                result.append(part_escaped)
        else:
            part_escaped = part.replace('<', '&lt;').replace('>', '&gt;')
            result.append(part_escaped)

    for tag in reversed(open_tags):
        result.append(f'</{tag}>')

    return ''.join(result)

def Paragraph(value, style):
    cleaned = sanitize_html_for_reportlab(value)
    try:
        return RichParagraph(cleaned, style)
    except Exception:
        return RichParagraph(escape(str(value)), style)

def format_inr(value):
    try:
        val = float(value)
        return f"Rs. {val:,.2f}".replace(".00", "")
    except Exception:
        return f"Rs. {value}"

def clean_description(desc):
    # Remove "(Included in Package, Rate: Rs. ...)"
    desc = re.sub(r'\s*\(Included in Package,\s*Rate:\s*Rs\.[^)]+\)', '', desc)
    # Remove "(Included in Package)"
    desc = desc.replace(" (Included in Package)", "")
    desc = desc.replace("(Included in Package)", "")
    # Remove "(Cost Included in Package)"
    desc = desc.replace(" (Cost Included in Package)", "")
    desc = desc.replace("(Cost Included in Package)", "")
    # Remove ", Rate: Rs. ... /Sqft" or similar if any
    desc = re.sub(r',\s*Rate:\s*Rs\.[^)]+', '', desc)
    return desc.strip()

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print 'Page X of Y'
    along with clean footer separator lines across all document pages.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 8)
        self.setFillColor(C_GRAY600)
        self.setStrokeColor(C_GRAY200)
        self.setLineWidth(0.5)
        self.line(MARGIN, 0.9 * cm, PAGE_W - MARGIN, 0.9 * cm)
        self.drawString(MARGIN, 0.55 * cm, "BuildSmart 360 · Detailed Construction Cost Estimate & BOQ")
        page_num_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(PAGE_W - MARGIN, 0.55 * cm, page_num_str)
        self.restoreState()

def generate_estimate_pdf(estimate, items, builder_name=None, builder_logo=None):
    """
    Generate a beautifully formatted PDF binary byte stream of the estimate report.
    """
    branding = (estimate.get('output_json') or {}).get('branding') or {}
    if branding:
        builder_name = branding['name']
        builder_logo = branding.get('logo')
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Quotation - {builder_name or 'Buildsmart 360'}",
        author=builder_name or "Buildsmart 360",
    )

    story = []
    
    # 1. Builder Logo parsing
    logo_flowable = None
    if builder_logo:
        try:
            logo_str = builder_logo.strip()
            if logo_str.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')):
                from PIL import Image
                encoded = logo_str.partition(',')[2]
                if len(encoded) <= 1400000:
                    img_data = base64.b64decode(encoded, validate=True)
                    with Image.open(io.BytesIO(img_data)) as image:
                        if image.width * image.height <= 4000000:
                            image.thumbnail((240, 240))
                            img_file = io.BytesIO()
                            image.convert('RGBA').save(img_file, 'PNG')
                            img_file.seek(0)
                            ratio = 1.7 * cm / max(image.width, image.height)
                            logo_flowable = RLImage(img_file, width=image.width * ratio, height=image.height * ratio, mask='auto')
        except Exception as e:
            print(f"Error parsing builder logo in PDF: {e}")

    # 1. Premium Header Banner
    if logo_flowable:
        logo_flowable.hAlign = 'CENTER'
        banner_data = [
            [Paragraph(builder_name or "Buildsmart 360", TITLE)],
            [Spacer(1, 0.15 * cm)],
            [logo_flowable],
            [Spacer(1, 0.15 * cm)],
            [Paragraph("DETAILED CONSTRUCTION COST ESTIMATE & BILL OF QUANTITIES (BOQ)", SUB)]
        ]
        banner_table = Table(banner_data, colWidths=[CONTENT_W])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), C_PRIMARY),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
            ('LEFTPADDING', (0,0), (-1,-1), 20),
            ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ]))
    else:
        banner_data = [
            [Paragraph(builder_name or "Buildsmart 360", TITLE)],
            [Spacer(1, 0.1 * cm)],
            [Paragraph("DETAILED CONSTRUCTION COST ESTIMATE & BILL OF QUANTITIES (BOQ)", SUB)]
        ]
        banner_table = Table(banner_data, colWidths=[CONTENT_W])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), C_PRIMARY),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 16),
            ('BOTTOMPADDING', (0,0), (-1,-1), 16),
            ('LEFTPADDING', (0,0), (-1,-1), 20),
            ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ]))
    story.append(banner_table)
    if branding:
        if branding.get('address'):
            story.append(Paragraph(' · '.join(branding['address'].splitlines()), BODY))
        contacts = [branding.get('phone'), branding.get('email')]
        if branding.get('tax_id'):
            contacts.append('GSTIN / Tax ID: ' + branding['tax_id'])
        if any(contacts):
            story.append(Paragraph(' | '.join(value for value in contacts if value), BODY))
    story.append(Spacer(1, 0.4 * cm))
    source = (estimate.get('output_json') or {}).get('source') or {}
    if source:
        story.append(Paragraph(
            f"{source.get('label', 'Estimate data')} | Snapshot {source.get('updated_at', '')[:19].replace('T', ' ')} UTC",
            BODY))
    story.append(Spacer(1, 0.2 * cm))

    # Parse JSON properties safely
    inj = estimate.get('input_json') or {}
    
    builder_company = builder_name or inj.get('builder_company_name') or "Builder Account"
    customer_name = inj.get('customer_name') or "Valued Client"
    project_name = inj.get('project_name') or inj.get('name') or "Residential Villa"
    location = f"{inj.get('city', '')}, {inj.get('state', '')}"
    quality_tier = inj.get('quality') or "Standard"
    total_area = inj.get('total_sqft') or estimate.get('total_sqft') or "1500"
    date_str = estimate.get('generated_at', '').split('T')[0] if estimate.get('generated_at') else "Recent"
    
    # 2. Project Specifications Summary Table (2-Column Grid Layout)
    story.append(Paragraph("1. Project & Builder Specification", H1))
    spec_data = [
        [Paragraph("<b>Project/Site Name:</b>", BODY), Paragraph(project_name, BODY),
         Paragraph("<b>Builder Company:</b>", BODY), Paragraph(builder_company, BODY)],
        [Paragraph("<b>Customer Name:</b>", BODY), Paragraph(customer_name, BODY),
         Paragraph("<b>Location/Address:</b>", BODY), Paragraph(location, BODY)],
        [Paragraph("<b>Quality Tier:</b>", BODY), Paragraph(quality_tier, BODY),
         Paragraph("<b>Total Built-up Area:</b>", BODY), Paragraph(f"{total_area} Sqft", BODY)],
        [Paragraph("<b>Quotation Date:</b>", BODY), Paragraph(date_str, BODY),
         Paragraph("<b>Contingency Margins:</b>", BODY), Paragraph(f"{estimate.get('contingency_pct', 5)}%", BODY)]
    ]
    spec_table = Table(spec_data, colWidths=[CONTENT_W*0.18, CONTENT_W*0.32, CONTENT_W*0.18, CONTENT_W*0.32])
    spec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_GRAY50),
        ('GRID', (0,0), (-1,-1), 0.5, C_GRAY200),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(spec_table)
    story.append(Spacer(1, 0.4 * cm))

    # Area calculation breakdown
    plot_length = float(inj.get("plot_length") or 0.0)
    plot_width = float(inj.get("plot_width") or 0.0)
    plot_area = plot_length * plot_width
    
    floors_list = inj.get("floors_list") or []
    floor_area_sum = sum(float(f.get("floor_area_sqft") or f.get("area") or (float(f.get("length") or 0) * float(f.get("width") or 0)) or 0) for f in floors_list)
    
    ground_coverage_floor = float(floors_list[0].get("floor_area_sqft") or (float(floors_list[0].get("length") or 0) * float(floors_list[0].get("width") or 0)) or 0.0) if floors_list else 0.0
    
    staircase_length = float(inj.get("staircase_length") or 0.0)
    staircase_width = float(inj.get("staircase_width") or 0.0)
    staircase_area = staircase_length * staircase_width
    
    portico_length = float(inj.get("portico_length") or 0.0)
    portico_width = float(inj.get("portico_width") or 0.0)
    portico_area = portico_length * portico_width
    
    total_builtup_area = floor_area_sum + portico_area + staircase_area
    ground_coverage_area = ground_coverage_floor + portico_area + staircase_area
    open_area = max(0.0, plot_area - ground_coverage_area)
    
    area_headers = [
        Paragraph("Specification", TCHL),
        Paragraph("Calculated Area", TCHR),
        Paragraph("Unit", TCH),
        Paragraph("Details / Formula", TCHL)
    ]
    area_rows = [
        area_headers,
        [Paragraph("Plot Area", TC), Paragraph(f"{plot_area:,.2f}".rstrip('0').rstrip('.'), TCR), Paragraph("Sqft", TCC), Paragraph("Plot Length × Plot Width", TC)],
        [Paragraph("Ground Coverage Area", TC), Paragraph(f"{ground_coverage_area:,.2f}".rstrip('0').rstrip('.'), TCR), Paragraph("Sqft", TCC), Paragraph("Ground Floor Area + Portico + Staircase", TC)],
        [Paragraph("Open Area", TC), Paragraph(f"{open_area:,.2f}".rstrip('0').rstrip('.'), TCR), Paragraph("Sqft", TCC), Paragraph("Plot Area − Ground Coverage Area", TC)],
        [Paragraph("Total Built-up Area", TCB), Paragraph(f"{total_builtup_area:,.2f}".rstrip('0').rstrip('.'), TCRB), Paragraph("Sqft", TCC), Paragraph("Sum of all floors + Portico + Staircase", TC)],
        [Paragraph("Staircase Area", TC), Paragraph(f"{staircase_area:,.2f}".rstrip('0').rstrip('.'), TCR), Paragraph("Sqft", TCC), Paragraph("Staircase Length × Staircase Width", TC)],
        [Paragraph("Portico Area", TC), Paragraph(f"{portico_area:,.2f}".rstrip('0').rstrip('.'), TCR), Paragraph("Sqft", TCC), Paragraph("Portico Length × Portico Width", TC)]
    ]
    area_table = Table(area_rows, colWidths=[CONTENT_W * 0.28, CONTENT_W * 0.18, CONTENT_W * 0.12, CONTENT_W * 0.42], repeatRows=1)
    area_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, C_GRAY200),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_WHITE, C_GRAY50]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'LEFT'),
    ]))
    
    story.append(Paragraph("1.1 Project Area Specifications", H2))
    story.append(area_table)
    story.append(Spacer(1, 0.4 * cm))

    # Room-wise breakdown
    rooms_list = inj.get("rooms_list") or []
    if rooms_list:
        room_headers = [
            Paragraph("Floor", TCHL),
            Paragraph("Room Name", TCHL),
            Paragraph("Dimensions", TCH),
            Paragraph("Area", TCHR),
            Paragraph("Doors", TCH),
            Paragraph("Windows", TCH),
            Paragraph("Elec Points", TCH),
            Paragraph("Plumb Points", TCH)
        ]
        room_rows = [room_headers]
        for r in rooms_list:
            floor_num = r.get("floor_num", 1)
            floor_obj = next((f for f in floors_list if f.get("floor_num") == floor_num), None)
            floor_name = floor_obj.get("floor_name") or floor_obj.get("name") if floor_obj else f"Floor {floor_num}"
            
            door_count = sum(int(d.get('qty', 0)) for d in r.get('doors', []))
            window_count = sum(int(w.get('qty', 0)) for w in r.get('windows', []))
            
            elec = r.get('electrical') or {}
            elec_points = sum(int(elec.get(k) or 0) for k in ['light_points', 'fan_points', 'plug_points', 'switch_boards', 'ac_points', 'tv_points', 'geyser_points', 'exhaust_points', 'exterior_light_points'])
            
            plumb = r.get('plumbing') or {}
            plumb_points = sum(int(plumb.get(k) or 0) for k in ['wc', 'wash_basin', 'shower', 'faucet', 'drain', 'tap', 'sink', 'inlet', 'drain_point'])
            
            r_len = float(r.get('length') or 0.0)
            r_wid = float(r.get('width') or 0.0)
            dim_str = f"{r_len:,.1f}x{r_wid:,.1f} ft".replace(".0", "")
            area_str = f"{r_len*r_wid:,.1f} Sqft".replace(".0", "")
            
            room_rows.append([
                Paragraph(floor_name, TC),
                Paragraph(r.get('name', ''), TC),
                Paragraph(dim_str, TCC),
                Paragraph(area_str, TCR),
                Paragraph(str(door_count), TCC),
                Paragraph(str(window_count), TCC),
                Paragraph(str(elec_points), TCC),
                Paragraph(str(plumb_points), TCC)
            ])
            
        room_table = Table(room_rows, colWidths=[
            CONTENT_W * 0.15,  # Floor
            CONTENT_W * 0.23,  # Room Name
            CONTENT_W * 0.14,  # Dimensions
            CONTENT_W * 0.12,  # Area
            CONTENT_W * 0.09,  # Doors
            CONTENT_W * 0.09,  # Windows
            CONTENT_W * 0.09,  # Elec
            CONTENT_W * 0.09   # Plumb
        ], repeatRows=1)
        room_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
            ('GRID', (0,0), (-1,-1), 0.5, C_GRAY200),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_WHITE, C_GRAY50]),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (1,-1), 'LEFT'),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
            ('ALIGN', (3,0), (3,-1), 'RIGHT'),
            ('ALIGN', (4,0), (-1,-1), 'CENTER'),
        ]))
        
        story.append(Paragraph("1.2 Room-wise Specifications & Fixtures", H2))
        story.append(room_table)
        story.append(Spacer(1, 0.4 * cm))
    source = (estimate.get('output_json') or {}).get('source') or {}
    if source:
        story.append(Paragraph(
            f"{source.get('label', 'Estimate data')} | Snapshot {source.get('updated_at', '')[:19].replace('T', ' ')} UTC",
            BODY))
    story.append(Spacer(1, 0.2 * cm))

    # 3. Stage-wise Cost Split Table
    story.append(PageBreak()) # Push completely to second page to avoid cutoffs
    story.append(Paragraph("2. Stage-wise Construction Cost Split", H1))
    
    civil_item = next((x for x in items if x.get('item_code') == 'CW-001' or x.get('code') == 'CW-001'), None)
    core_cost = float(civil_item.get('amount') or 0.0) if civil_item else float(estimate.get('subtotal') or 0.0)
    
    stages = [
        {
            "num": 1,
            "stage": "Foundation & Basement Stage",
            "pct": 20,
            "desc": "Includes site cleaning, excavation, PCC foundation bed, footing reinforcement steel, brick masonry up to plinth level, and plinth beam concreting.",
            "cost": round(core_cost * 0.20)
        },
        {
            "num": 2,
            "stage": "Concrete Slab & Structure Stage",
            "pct": 30,
            "desc": "Includes shuttering, reinforcement steel binding, column raising, beam layouts, and concrete casting for roof slabs.",
            "cost": round(core_cost * 0.30)
        },
        {
            "num": 3,
            "stage": "Brickwork & Plastering Stage",
            "pct": 20,
            "desc": "Includes internal and external wall brickwork/blockwork and double coat plastering.",
            "cost": round(core_cost * 0.20)
        },
        {
            "num": 4,
            "stage": "MEP (Electrical & Plumbing) Stage",
            "pct": 15,
            "desc": "Includes concealed wall piping, conduit laying, electrical box fixing, bathroom plumbing pipe layouts, and sanitary fittings.",
            "cost": round(core_cost * 0.15)
        },
        {
            "num": 5,
            "stage": "Finishing & Woodworks Stage",
            "pct": 15,
            "desc": "Includes general flooring tiling, wall painting, and doors & windows framing and shutter installations.",
            "cost": round(core_cost * 0.15)
        }
    ]
    
    stage_headers = [
        Paragraph("#", TCH),
        Paragraph("Stage", TCHL),
        Paragraph("Percentage", TCH),
        Paragraph("Description", TCHL),
        Paragraph("Estimated Cost", TCHR)
    ]
    stage_col_widths = [
        CONTENT_W * 0.06,  # #
        CONTENT_W * 0.26,  # Stage
        CONTENT_W * 0.13,  # Percentage
        CONTENT_W * 0.38,  # Description
        CONTENT_W * 0.17   # Estimated Cost
    ]
    stage_rows = [stage_headers]
    for s in stages:
        stage_rows.append([
            Paragraph(f"<b>{s['num']}</b>", TCCB),
            Paragraph(f"<b>{s['stage']}</b>", TC),
            Paragraph(f"<b>{s['pct']}%</b>", TCPRIC),
            Paragraph(s['desc'], TC),
            Paragraph(f"<b>{format_inr(s['cost'])}</b>", TCRB)
        ])
    stage_table = Table(stage_rows, colWidths=stage_col_widths, repeatRows=1)
    stage_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, C_GRAY200),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_WHITE, C_GRAY50]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'LEFT'),
        ('ALIGN', (4,0), (4,-1), 'RIGHT'),
    ]))
    story.append(stage_table)
    story.append(Spacer(1, 0.4 * cm))

    # Duration note
    min_months = estimate.get('duration_min') or 8
    max_months = estimate.get('duration_max') or 10
    duration_str = f"Estimated project duration is <b>{min_months} to {max_months} months</b> depending on site execution speeds and weather delays."
    story.append(Paragraph(duration_str, BODY))
    story.append(Spacer(1, 0.4 * cm))
    source = (estimate.get('output_json') or {}).get('source') or {}
    if source:
        story.append(Paragraph(
            f"{source.get('label', 'Estimate data')} | Snapshot {source.get('updated_at', '')[:19].replace('T', ' ')} UTC",
            BODY))
    story.append(Spacer(1, 0.2 * cm))

    # 4. Detailed BOQ Table
    story.append(Paragraph("3. Itemized Bill of Quantities (BOQ)", H1))
    
    # Header for BOQ table (Prices removed!)
    boq_headers = [
        Paragraph("Code", TCH),
        Paragraph("Item Name / Description", TCHL),
        Paragraph("Qty", TCHR),
        Paragraph("Unit", TCH)
    ]
    
    boq_col_widths = [
        CONTENT_W * 0.14,  # Code
        CONTENT_W * 0.59,  # Description
        CONTENT_W * 0.14,  # Qty
        CONTENT_W * 0.13   # Unit
    ]

    # Group items by category to make it extremely readable
    categories = ['Civil Works', 'Labour', 'Flooring', 'Painting', 'Electrical', 'Plumbing', 'Interiors', 'Additional Works']
    
    for cat in categories:
        cat_items = [x for x in items if x.get('category') == cat]
        if not cat_items:
            continue
            
        story.append(Paragraph(f"<b>Category: {cat}</b>", H2))
        
        table_rows = [boq_headers]
        for it in cat_items:
            # Format unit mapping
            unit_display = it.get('unit', '')
            qty_display = float(it.get('quantity') or it.get('qty') or 0.0)
            
            # Map cft -> Unit as per requirement
            if unit_display.lower() == 'cft':
                unit_display = 'Unit'
                qty_display = round(qty_display / 100, 2)
            
            # Form paragraphs for description cell to enable auto-wrapping & clean descriptions on the fly
            desc_text = it.get('name') or it.get('description') or 'Item'
            cleaned_desc = clean_description(desc_text)
            
            table_rows.append([
                Paragraph(it.get('item_code') or it.get('code') or '—', TCC),
                Paragraph(cleaned_desc, TC),
                Paragraph(f"{qty_display:,.2f}".rstrip('0').rstrip('.'), TCR),
                Paragraph(unit_display, TCC)
            ])
            
        cat_table = Table(table_rows, colWidths=boq_col_widths, repeatRows=1)
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
            ('GRID', (0,0), (-1,-1), 0.5, C_GRAY200),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_WHITE, C_GRAY50]),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (1,0), (1,-1), 'LEFT'),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('ALIGN', (3,0), (3,-1), 'CENTER'),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 0.35 * cm))

    # Build PDF with two-pass NumberedCanvas to ensure accurate 'Page X of Y' and headers/footers
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Return binary PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
