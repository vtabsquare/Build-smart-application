import unittest
import io
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from services.pdf_generator import generate_estimate_pdf, sanitize_html_for_reportlab

class TestPdfFormatting(unittest.TestCase):
    def test_sanitize_html(self):
        # 1. Bold tags
        self.assertEqual(sanitize_html_for_reportlab("<b>bold</b>"), "<b>bold</b>")
        self.assertEqual(sanitize_html_for_reportlab("<strong>strong</strong>"), "<b>strong</b>")
        
        # 2. Italic tags
        self.assertEqual(sanitize_html_for_reportlab("<i>italic</i>"), "<i>italic</i>")
        self.assertEqual(sanitize_html_for_reportlab("<em>emphasized</em>"), "<i>emphasized</i>")
        
        # 3. Line breaks & paragraphs
        self.assertEqual(sanitize_html_for_reportlab("line1<br>line2"), "line1<br/>line2")
        self.assertEqual(sanitize_html_for_reportlab("line1<br/>line2"), "line1<br/>line2")
        self.assertEqual(sanitize_html_for_reportlab("<p>p1</p><p>p2</p>"), "p1<br/><br/>p2")
        
        # 4. Spans & Divs stripped
        self.assertEqual(sanitize_html_for_reportlab("<span>clean</span>"), "clean")
        self.assertEqual(sanitize_html_for_reportlab("<div>clean</div>"), "clean")
        
        # 5. Ampersand escaping
        self.assertEqual(sanitize_html_for_reportlab("Electrical & Plumbing"), "Electrical &amp; Plumbing")
        self.assertEqual(sanitize_html_for_reportlab("Tom &amp; Jerry"), "Tom &amp; Jerry")
        
        # 6. Currency symbol replacement
        self.assertEqual(sanitize_html_for_reportlab("₹ 50,000"), "Rs. 50,000")
        self.assertEqual(sanitize_html_for_reportlab("₹50,000"), "Rs. 50,000")
        
        # 7. Auto-closing unclosed tags
        self.assertEqual(sanitize_html_for_reportlab("<b>unclosed"), "<b>unclosed</b>")

    def test_generate_pdf_output(self):
        estimate = {
            'total_sqft': 1500,
            'contingency_pct': 5,
            'generated_at': '2026-11-23T11:03:21',
            'subtotal': 2800000,
            'duration_min': 3,
            'duration_max': 5,
            'input_json': {
                'customer_name': 'Test Client',
                'project_name': 'Sample Villa',
                'city': 'Coimbatore',
                'state': 'Tamil Nadu',
                'quality': 'Standard',
                'total_sqft': 1500,
                'plot_length': 50,
                'plot_width': 30,
                'floors_list': [{'floor_name': 'Ground Floor', 'length': 30, 'width': 30}],
                'rooms_list': [{'name': 'Living Room', 'length': 16, 'width': 12, 'doors': [{'qty': 1}], 'windows': [{'qty': 2}]}]
            }
        }
        categories = ['Civil Works', 'Labour', 'Flooring', 'Painting', 'Electrical', 'Plumbing', 'Interiors', 'Additional Works']
        items = []
        for cat in categories:
            for j in range(3):
                items.append({
                    'category': cat,
                    'item_code': f'{cat[:2].upper()}-00{j+1}',
                    'name': f'Item <b>bold</b> & normal {cat} {j+1}',
                    'quantity': 100 * (j+1),
                    'unit': 'Sqft',
                    'amount': 2800000 if cat == 'Civil Works' and j == 0 else 50000
                })

        pdf_bytes = generate_estimate_pdf(estimate, items, builder_name='VTabdemo')
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

        # Inspect PDF with fitz (PyMuPDF)
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        self.assertGreaterEqual(doc.page_count, 2)
        
        full_text = ""
        for page in doc:
            page_text = page.get_text()
            full_text += page_text
            # Verify footer page numbering format "Page X of Y"
            self.assertIn("Page ", page_text)
            self.assertIn(f" of {doc.page_count}", page_text)

        # Ensure raw HTML tags are NOT leaked into the PDF text output
        self.assertNotIn("<b>", full_text)
        self.assertNotIn("</b>", full_text)
        self.assertNotIn("<strong>", full_text)
        self.assertNotIn("</strong>", full_text)
        self.assertNotIn("&lt;b&gt;", full_text)
        self.assertNotIn("&lt;/b&gt;", full_text)

        # Ensure key sections and currency exist
        self.assertIn("Stage-wise Construction Cost Split", full_text)
        self.assertIn("Itemized Bill of Quantities (BOQ)", full_text)
        self.assertIn("Rs.", full_text)

if __name__ == '__main__':
    unittest.main()
