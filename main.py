import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
from datetime import datetime
import shutil
import io
import webbrowser
import traceback
import base64
import tempfile
import uuid

# Try to import required libraries
try:
    import qrcode
    from fpdf import FPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("PDF creation libraries not found. Install with: pip install fpdf2 qrcode")

# Try to import Arabic text support libraries
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
    print("Arabic text support is enabled")
except ImportError:
    ARABIC_SUPPORT = False
    print("Arabic text support is not available. Install with: pip install arabic-reshaper python-bidi")

# Try to import calendar widget
try:
    from tkcalendar import DateEntry
    CALENDAR_SUPPORT = True
except ImportError:
    CALENDAR_SUPPORT = False
    print("Calendar widget not found. Install with: pip install tkcalendar")

# ===== HARDCODED COMPANY INFORMATION (DEFAULT) =====
# This information is now available in the main code and will be used if no config file is found.
DEFAULT_COMPANY_INFO = {
    "name": "شركة جابر حسن سالم المالكي للتقييم",
    "address": "الشارع/حبيب بن عدي--رقم المبنى7841\nالدائر--الرقم الفرعي3470--الرمز البريدي83863 Saudi Arabia",
    "vat": "3124660559",
    "reg": "5909630417",
    "phone": "0505793504"
}

# ===== FILE PATHS =====
CONFIG_FILE = "invoice_config.json"
INVOICES_DIR = "invoices"
FONTS_DIR = "fonts"

if not os.path.exists(INVOICES_DIR):
    os.makedirs(INVOICES_DIR)
if not os.path.exists(FONTS_DIR):
    os.makedirs(FONTS_DIR)

# ===== BUSINESS LOGIC FUNCTIONS =====
def load_config():
    """
    Loads configuration. Starts with hardcoded defaults, then overrides
    with any values found in the config file.
    """
    # Start with the built-in default configuration
    config = {
        "last_invoice_number": 0,
        "company_info": DEFAULT_COMPANY_INFO.copy()
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Update the default config with user's saved settings
                if 'company_info' in user_config:
                    config['company_info'].update(user_config['company_info'])
                if 'last_invoice_number' in user_config:
                    config['last_invoice_number'] = user_config['last_invoice_number']
        except Exception as e:
            print(f"Error loading config file, using defaults: {e}")
    
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_next_invoice_number():
    config = load_config()
    last_number = config.get("last_invoice_number", 0)
    next_number = last_number + 1
    year = datetime.now().year
    return f"INV-{year}-{next_number:06d}"

def update_invoice_number_config():
    config = load_config()
    config["last_invoice_number"] = config.get("last_invoice_number", 0) + 1
    save_config(config)

def calculate_totals(invoice_items):
    subtotal = sum(item["amount"] for item in invoice_items)
    total_vat = sum(item["vat"] for item in invoice_items)
    total = subtotal + total_vat
    return subtotal, total_vat, total

def find_invoice_files():
    """Finds .json invoice data files for editing."""
    invoice_files = []
    if os.path.exists(INVOICES_DIR):
        for filename in os.listdir(INVOICES_DIR):
            if filename.endswith(".json"):
                invoice_files.append(filename)
    return sorted(invoice_files, reverse=True)

def setup_arabic_fonts():
    try:
        system_fonts = [
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
            '/Library/Fonts/Arial Unicode.ttf',
            '/System/Library/Fonts/Arial Unicode.ttf'
        ]
        local_font_path = os.path.join(FONTS_DIR, 'arabic_font.ttf')
        if os.path.exists(local_font_path):
            return local_font_path
        for font_path in system_fonts:
            if os.path.exists(font_path):
                shutil.copy(font_path, local_font_path)
                return local_font_path
        messagebox.showinfo("تنبيه", "لم يتم العثور على خط مناسب للعربية. الرجاء اختيار ملف خط يدعم اللغة العربية (ttf).")
        font_path = filedialog.askopenfilename(title="اختر ملف خط يدعم اللغة العربية", filetypes=[("TrueType Fonts", "*.ttf"), ("All Files", "*.*")])
        if font_path and os.path.exists(font_path):
            shutil.copy(font_path, local_font_path)
            return local_font_path
        return None
    except Exception as e:
        print(f"Error setting up Arabic fonts: {e}")
        return None

def generate_zatca_tlv_qr_code(invoice_data, temp_file_path=None):
    try:
        company = invoice_data["company"]
        totals = invoice_data["totals"]
        invoice_datetime = datetime.now()
        seller_name = company['name']
        vat_number = company['vat']
        timestamp = invoice_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
        invoice_total = f"{totals['total']:.2f}"
        vat_total = f"{totals['vat']:.2f}"
        tag1 = bytes([1]) + bytes([len(seller_name.encode('utf-8'))]) + seller_name.encode('utf-8')
        tag2 = bytes([2]) + bytes([len(vat_number.encode('utf-8'))]) + vat_number.encode('utf-8')
        tag3 = bytes([3]) + bytes([len(timestamp.encode('utf-8'))]) + timestamp.encode('utf-8')
        tag4 = bytes([4]) + bytes([len(invoice_total.encode('utf-8'))]) + invoice_total.encode('utf-8')
        tag5 = bytes([5]) + bytes([len(vat_total.encode('utf-8'))]) + vat_total.encode('utf-8')
        tlv_data = tag1 + tag2 + tag3 + tag4 + tag5
        base64_data = base64.b64encode(tlv_data).decode('utf-8')
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(base64_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        if temp_file_path:
            img.save(temp_file_path)
            return temp_file_path, img.size
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, img.size
    except Exception as e:
        print(f"QR Generation Error: {str(e)}")
        traceback.print_exc()
        return None, (0,0)

class ArabicPDF(FPDF):
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.font_path = None
    def set_arabic_font(self, font_path, size=10):
        self.font_path = font_path
        self.add_font('Arabic', '', font_path, uni=True)
        self.set_font('Arabic', '', size)
    def arabic_text(self, x, y, txt, align='right', size=None):
        if not txt:
            return
        txt = str(txt)
        if size:
            self.set_font_size(size)
        if ARABIC_SUPPORT:
            try:
                reshaped_text = arabic_reshaper.reshape(txt)
                bidi_text = get_display(reshaped_text)
            except Exception as e:
                print(f"Error processing Arabic text: {e}")
                bidi_text = txt
        else:
            bidi_text = txt
        self.set_text_color(0,0,0)
        width = self.get_string_width(bidi_text)
        if align == 'right':
            self.text(x - width, y, bidi_text)
        elif align == 'center':
            self.text(x - (width/2), y, bidi_text)
        else:
            self.text(x, y, bidi_text)

def create_invoice_pdf(file_path, invoice_data):
    if not PDF_SUPPORT:
        messagebox.showerror("خطأ", "مكتبات إنشاء PDF غير مثبتة.")
        return False
    font_path = setup_arabic_fonts()
    if not font_path:
        messagebox.showerror("خطأ", "لم يتم العثور على خط مناسب للعربية.")
        return False

    pdf = ArabicPDF()
    pdf.set_arabic_font(font_path, 10) # Default font size
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    page_width = pdf.w
    page_height = pdf.h
    right_margin = page_width - 20

    try:
        company = invoice_data["company"]
        najm = invoice_data["najm"]
        invoice = invoice_data["invoice"]
        items = invoice_data["items"]
        totals = invoice_data["totals"]
        
        pdf_main_title = invoice["type"]
        invoice_date = invoice.get("date", datetime.now().strftime("%d-%m-%Y"))

        current_y = 20

        # --- COMPANY INFO, LOGO, TITLES, QR/NAJM (Preamble) ---
        logo_width = 0
        if "logo_path" in company and company["logo_path"] and os.path.exists(company["logo_path"]):
            try: logo_width = 40; pdf.image(company["logo_path"], x=right_margin-logo_width, y=current_y, w=logo_width, h=35)
            except Exception as e: print(f"Error adding logo to PDF: {e}")
        text_right_margin = right_margin - logo_width - 10 if logo_width > 0 else right_margin
        pdf.arabic_text(text_right_margin, current_y + 7, company["name"], 'right', 14); current_y += 7
        if company["address"]:
            for line in company["address"].split('\n'): pdf.arabic_text(text_right_margin, current_y + 7, line, 'right', 10); current_y += 6
        pdf.arabic_text(text_right_margin, current_y + 7, f"رقم ضريبي: {company['vat']}", 'right', 10); current_y += 6
        pdf.arabic_text(text_right_margin, current_y + 7, f"س.ت: {company['reg']}", 'right', 10); current_y += 6
        pdf.arabic_text(text_right_margin, current_y + 7, f"هاتف: {company['phone']}", 'right', 10); current_y += 8
        pdf.line(20, current_y + 5, right_margin, current_y + 5); current_y += 8
        pdf.arabic_text(page_width/2, current_y + 7, pdf_main_title, 'center', 14); current_y += 12
        if invoice["type"] == "فاتورة ضريبية":
            try:
                temp_dir=tempfile.gettempdir();unique_id=str(uuid.uuid4())[:8];qr_temp_file=os.path.join(temp_dir,f"zatca_qr_{unique_id}.png")
                _,qr_size=generate_zatca_tlv_qr_code(invoice_data,qr_temp_file)
                if os.path.exists(qr_temp_file)and os.path.getsize(qr_temp_file)>0:
                    qr_start_y=current_y;qr_width=40;qr_height=int(qr_size[1]*(qr_width/qr_size[0]))if qr_size[0]>0 else 40
                    pdf.image(qr_temp_file,x=20,y=qr_start_y,w=qr_width,h=qr_height)
                    pdf.arabic_text(right_margin,qr_start_y+7,najm["name"],'right',12);pdf.arabic_text(right_margin,qr_start_y+14,najm["address"],'right',10)
                    pdf.arabic_text(right_margin,qr_start_y+21,f"رقم ضريبي: {najm['vat']}",'right',10);pdf.arabic_text(right_margin,qr_start_y+28,f"س.ت: {najm['reg']}",'right',10)
                    current_y=max(qr_start_y+qr_height+5,qr_start_y+35)
                    try:os.remove(qr_temp_file)
                    except Exception as e:print(f"Could not delete temp file: {e}")
                else:
                    print("Failed to create QR code for tax invoice.");pdf.arabic_text(right_margin,current_y+7,najm["name"],'right',12);current_y+=6;pdf.arabic_text(right_margin,current_y+7,najm["address"],'right',10);current_y+=6
                    pdf.arabic_text(right_margin,current_y+7,f"رقم ضريبي: {najm['vat']}",'right',10);current_y+=6;pdf.arabic_text(right_margin,current_y+7,f"س.ت: {najm['reg']}",'right',10);current_y+=20
            except Exception as e:
                print(f"Error QR gen: {e}");traceback.print_exc();pdf.arabic_text(right_margin,current_y+7,najm["name"],'right',12);current_y+=6;pdf.arabic_text(right_margin,current_y+7,najm["address"],'right',10);current_y+=6
                pdf.arabic_text(right_margin,current_y+7,f"رقم ضريبي: {najm['vat']}",'right',10);current_y+=6;pdf.arabic_text(right_margin,current_y+7,f"س.ت: {najm['reg']}",'right',10);current_y+=20
        else:
            pdf.arabic_text(right_margin,current_y+7,najm["name"],'right',12);current_y+=6;pdf.arabic_text(right_margin,current_y+7,najm["address"],'right',10);current_y+=6
            pdf.arabic_text(right_margin,current_y+7,f"رقم ضريبي: {najm['vat']}",'right',10);current_y+=6;pdf.arabic_text(right_margin,current_y+7,f"س.ت: {najm['reg']}",'right',10);current_y+=20
        pdf.arabic_text(right_margin,current_y+5,pdf_main_title,'right',12);current_y+=8
        pdf.arabic_text(right_margin,current_y+5,f"رقم الفاتورة: {invoice['number']}",'right',10);current_y+=6
        pdf.arabic_text(right_margin,current_y+5,f"تاريخ الفاتورة: {invoice_date}",'right',10);current_y+=6
        if invoice["type"]=="فاتورة ضريبية":pdf.arabic_text(right_margin,current_y+5,f"تاريخ الاستحقاق: {invoice_date}",'right',10);current_y+=6
        pdf.arabic_text(right_margin,current_y+5,f"تاريخ التوصيل: {invoice_date}",'right',10);current_y+=6
        
        if len(invoice['reference']) > 60:
            words = invoice['reference'].split(); lines_ref = []; current_line_ref = []
            for word in words:
                current_line_ref.append(word)
                if len(' '.join(current_line_ref)) > 60:
                    current_line_ref.pop(); lines_ref.append(' '.join(current_line_ref)); current_line_ref = [word]
            if current_line_ref: lines_ref.append(' '.join(current_line_ref))
            pdf.arabic_text(right_margin, current_y + 5, "رقم الاشارة:", 'right', 10); current_y += 6
            for line in lines_ref: pdf.arabic_text(right_margin - 5, current_y + 5, line, 'right', 9); current_y += 4
        else:
            pdf.arabic_text(right_margin, current_y + 5, f"رقم الاشارة: {invoice['reference']}", 'right', 10); current_y += 6

        current_y += 5
        pdf.set_y(current_y)
        table_start_y = current_y
        
        # [FIX 1] Adjusted column widths: More space for Product name
        col_widths = [55, 19, 25, 20, 20, 20, 35] # المنتج, الكمية, سعر, نسبة, مبلغ, ضريبة, إجمالي
        headers = ["المنتج", "الكمية", "سعر الوحدة", "نسبة الضريبة", "المبلغ", "قيمة الضريبة", "الإجمالي"]
        
        def draw_table_header_content(header_y):
            pdf.set_fill_color(240,240,240); pdf.rect(20, header_y, right_margin - 20, 10, style='F')
            x_header_pos = right_margin; pdf.set_font('Arabic', '', 10)
            for k, header_text in enumerate(headers):
                x_header_pos -= col_widths[k]; align_offset = -10 if k == 1 else -2
                pdf.arabic_text(x_header_pos + col_widths[k] + align_offset, header_y + 7, header_text, 'right', 10)
            pdf.set_font('Arabic', '', 9); return header_y + 10

        current_y = draw_table_header_content(current_y)
        pdf.set_y(current_y)

        line_height_for_multicell = 5; cell_padding_y = 1.5; pdf.set_font('Arabic', '', 9); product_name_text_leniency_mm = 1.0

        for i, item in enumerate(items):
            product_name_original = item["name"]; bidi_product_name = product_name_original
            if ARABIC_SUPPORT:
                try: reshaped_text = arabic_reshaper.reshape(product_name_original); bidi_product_name = get_display(reshaped_text)
                except Exception: pass
            width_for_split_calc = (col_widths[0]-(2*cell_padding_y))+product_name_text_leniency_mm
            product_name_lines = pdf.multi_cell(w=width_for_split_calc, h=line_height_for_multicell, txt=bidi_product_name, border=0, align='R', fill=False, split_only=True)
            num_lines = max(1, len(product_name_lines)); current_row_height = max(10, (num_lines*line_height_for_multicell)+(2*cell_padding_y))
            if pdf.get_y()+current_row_height > (page_height-pdf.b_margin):
                pdf.add_page(); current_y=pdf.t_margin; current_y=draw_table_header_content(current_y); pdf.set_y(current_y)
            start_of_row_y=pdf.get_y()
            if i%2==0:pdf.set_fill_color(245,245,245);pdf.rect(20,start_of_row_y,right_margin-20,current_row_height,style='F')
            item_display_values=[bidi_product_name,f"{item['quantity']:.2f}",f"{item['unit_price']:.2f} ر.س",f"{item['tax_rate']:.2f}%",f"{item['amount']:.2f} ر.س",f"{item['vat']:.2f} ر.س",f"{item['total']:.2f} ر.س"]
            current_cell_x=right_margin
            for j,value_text in enumerate(item_display_values):
                cell_actual_width=col_widths[j];current_cell_x-=cell_actual_width;content_y_base=start_of_row_y+cell_padding_y
                if j==0:
                    x_for_product_multicell=current_cell_x+cell_padding_y-product_name_text_leniency_mm;pdf.set_xy(x_for_product_multicell,content_y_base)
                    width_for_product_draw=(cell_actual_width-(2*cell_padding_y))+product_name_text_leniency_mm
                    pdf.multi_cell(width_for_product_draw,line_height_for_multicell,txt=value_text,border=0,align='R',fill=False)
                else:
                    text_baseline_y=start_of_row_y+7;horizontal_padding=-10 if j==1 else -3
                    text_target_x=current_cell_x+cell_actual_width+horizontal_padding;pdf.arabic_text(text_target_x,text_baseline_y,str(value_text),'right',9)
            pdf.set_y(start_of_row_y+current_row_height)
        
        current_y = pdf.get_y()
        pdf.line(20, table_start_y, right_margin, table_start_y); pdf.line(20, table_start_y + 10, right_margin, table_start_y + 10)
        pdf.line(20, current_y, right_margin, current_y)
        
        gap_before_totals = 1.0; height_subtotal_line = 5.0; height_vat_line = 5.0; height_total_line = 6.0; gap_after_totals_text = 1.0
        stamp_h = 40.0; stamp_w = 40.0; stamp_x = 30.0; stamp_y_offset_from_totals_end = -15.0
        estimated_totals_text_height = height_subtotal_line + height_vat_line + height_total_line
        potential_totals_start_y = current_y + gap_before_totals
        potential_totals_end_y = potential_totals_start_y + estimated_totals_text_height
        potential_stamp_top_y = potential_totals_end_y + gap_after_totals_text + stamp_y_offset_from_totals_end
        potential_stamp_bottom_y = potential_stamp_top_y + stamp_h
        lowest_point_of_block_on_current_page = max(potential_totals_end_y, potential_stamp_bottom_y)
        page_bottom_drawable_y = page_height - pdf.b_margin
            
        y_for_drawing_totals = 0
        if lowest_point_of_block_on_current_page > page_bottom_drawable_y:
            pdf.add_page(); y_for_drawing_totals = pdf.t_margin + 10
        else:
            y_for_drawing_totals = current_y + gap_before_totals
        
        pdf.set_y(y_for_drawing_totals)

        current_drawing_y = y_for_drawing_totals
        pdf.set_font('Arabic', '', 12)
        pdf.arabic_text(right_margin, current_drawing_y + 5, f"المجموع الفرعي: {totals['subtotal']:,.2f} ر.س", 'right'); current_drawing_y += height_subtotal_line
        pdf.arabic_text(right_margin, current_drawing_y + 5, f"ضريبة القيمة المضافة: {totals['vat']:,.2f} ر.س", 'right'); current_drawing_y += height_vat_line
        pdf.set_font('Arabic', '', 14)
        pdf.arabic_text(right_margin, current_drawing_y + 5, f"الإجمالي: {totals['total']:,.2f} ر.س", 'right'); current_drawing_y += height_total_line
        pdf.set_font('Arabic', '', 9)

        if "stamp_path" in company and company["stamp_path"] and os.path.exists(company["stamp_path"]):
            try:
                actual_stamp_y = current_drawing_y + gap_after_totals_text + stamp_y_offset_from_totals_end
                if actual_stamp_y + stamp_h > (page_height - pdf.b_margin):
                    actual_stamp_y = (page_height - pdf.b_margin) - stamp_h
                pdf.image(company["stamp_path"], x=stamp_x, y=actual_stamp_y, w=stamp_w, h=stamp_h)
            except Exception as e:
                print(f"Error adding stamp to PDF: {e}"); traceback.print_exc()

        pdf.output(file_path)
        return True
    except Exception as e:
        print(f"Error creating PDF: {e}")
        traceback.print_exc()
        return False

class InvoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("نظام الفواتير v3.3")
        self.root.geometry("850x700")
        self.company_logo_path = None
        self.stamp_path = None
        self.config = load_config()
        self.company_name = tk.StringVar()
        self.company_address = tk.StringVar()
        self.company_vat = tk.StringVar()
        self.company_reg = tk.StringVar()
        self.company_phone = tk.StringVar()
        self.najm_name = tk.StringVar(value="شركة نجم لخدمات التأمين")
        self.najm_address = tk.StringVar(value=" 3268طريق الثمامة, حي الصحافة, الرياض 13315-- 6272")
        self.najm_vat = tk.StringVar(value="300146558310003")
        self.najm_reg = tk.StringVar(value="1010229751")
        self.invoice_number = tk.StringVar(value=get_next_invoice_number())
        self.invoice_date_str = tk.StringVar(value=datetime.now().strftime("%d-%m-%Y")) # For PDF
        self.reference = tk.StringVar() # For PDF, set in background
        self.invoice_type = tk.StringVar() # For PDF, set in background
        self.invoice_items = []
        self.is_new_invoice = True # Flag to track if we're creating new or editing
        self.load_settings_from_config()
        self.setup_ui()
    
    def load_settings_from_config(self):
        if "company_info" in self.config:
            info = self.config["company_info"]
            self.company_name.set(info.get("name", ""))
            self.company_address.set(info.get("address", ""))
            self.company_vat.set(info.get("vat", ""))
            self.company_reg.set(info.get("reg", ""))
            self.company_phone.set(info.get("phone", ""))
            self.company_logo_path = info.get("logo", "")
            self.stamp_path = info.get("stamp", "")

    def save_settings_to_config(self):
        self.config["company_info"] = {
            "name": self.company_name.get(), "address": self.company_address.get(),
            "vat": self.company_vat.get(), "reg": self.company_reg.get(),
            "phone": self.company_phone.get(), "logo": self.company_logo_path or "",
            "stamp": self.stamp_path or ""}
        save_config(self.config)
        messagebox.showinfo("تم", "تم حفظ إعدادات الشركة بنجاح")

    def setup_ui(self):
        # [FIX 5] Apply modern theme and styles
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure("TLabel", font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10))
        style.configure("TEntry", font=("Arial", 10))
        style.configure("TLabelFrame.Label", font=("Arial", 11, "bold"))
        style.configure("Action.TButton", font=('Arial', 12, 'bold'), padding=10)
        style.configure("Accent.TButton", font=('Arial', 12, 'bold'), padding=8)
        
        main_container = ttk.Frame(self.root, padding="10 10 10 10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # --- Menu Bar ---
        menubar = tk.Menu(self.root); self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0); menubar.add_cascade(label="ملف", menu=file_menu)
        file_menu.add_command(label="إعدادات الشركة", command=self.show_company_settings_dialog)
        file_menu.add_command(label="فاتورة جديدة", command=self.clear_invoice)
        file_menu.add_command(label="بحث وتعديل فاتورة", command=self.search_and_edit_invoice)
        file_menu.add_separator(); file_menu.add_command(label="خروج", command=self.root.quit)

        # --- Top Control Frames ---
        # [FIX 5] Re-arranged for better visibility of actions
        actions_frame = ttk.LabelFrame(main_container, text="الإجراءات السريعة")
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        action_buttons_container = ttk.Frame(actions_frame)
        action_buttons_container.pack(pady=10)
        
        btn_tathmeen = ttk.Button(action_buttons_container, text="إضافة تثمين", command=self.add_tathmeen, style="Action.TButton")
        btn_tathmeen.grid(row=0, column=3, padx=5)
        btn_taqdeer_client = ttk.Button(action_buttons_container, text="تقدير (دفع العميل)", command=self.add_taqdeer_client, style="Action.TButton")
        btn_taqdeer_client.grid(row=0, column=2, padx=5)
        btn_taqdeer_insurance = ttk.Button(action_buttons_container, text="تقدير (دفع التأمين)", command=self.add_taqdeer_insurance, style="Action.TButton")
        btn_taqdeer_insurance.grid(row=0, column=1, padx=5)
        btn_taqdeer_truck = ttk.Button(action_buttons_container, text="تقدير شاحنات", command=self.add_taqdeer_truck, style="Action.TButton")
        btn_taqdeer_truck.grid(row=0, column=0, padx=5)

        details_frame = ttk.LabelFrame(main_container, text="معلومات الفاتورة")
        details_frame.pack(fill=tk.X, pady=5)
        
        details_grid = ttk.Frame(details_frame, padding=5)
        details_grid.pack(fill=tk.X)
        ttk.Label(details_grid, text="رقم الفاتورة:").grid(row=0, column=3, padx=5, pady=5, sticky='e')
        ttk.Entry(details_grid, textvariable=self.invoice_number, width=25, justify='right').grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(details_grid, text="تاريخ الفاتورة:").grid(row=0, column=1, padx=(15, 5), pady=5, sticky='e')
        if CALENDAR_SUPPORT:
            # [FIX 4] Added Arabic locale to calendar
            self.date_picker = DateEntry(details_grid, width=15, date_pattern='dd-mm-y', locale='ar_SA')
            self.date_picker.grid(row=0, column=0, padx=5, pady=5)
        else:
            ttk.Label(details_grid, text="قم بتثبيت tkcalendar").grid(row=0, column=0, padx=5, pady=5)
        
        # --- Items Tree ---
        items_frame = ttk.LabelFrame(main_container, text="عناصر الفاتورة")
        items_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        columns = ("name", "quantity", "unit_price", "tax_rate", "amount", "vat", "total")
        self.items_tree = ttk.Treeview(items_frame, columns=columns, show="headings", height=10)
        self.items_tree.heading("name", text="المنتج"); self.items_tree.heading("quantity", text="الكمية"); self.items_tree.heading("unit_price", text="سعر الوحدة"); self.items_tree.heading("tax_rate", text="نسبة الضريبة"); self.items_tree.heading("amount", text="المبلغ"); self.items_tree.heading("vat", text="قيمة الضريبة"); self.items_tree.heading("total", text="الإجمالي")
        for col in columns: self.items_tree.column(col, width=70, anchor=tk.CENTER)
        self.items_tree.column("name", width=300, anchor=tk.E)
        
        items_scrollbar = ttk.Scrollbar(items_frame, orient=tk.VERTICAL, command=self.items_tree.yview); self.items_tree.configure(yscrollcommand=items_scrollbar.set)
        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.items_tree.bind("<Double-1>", self.edit_selected_item)
        
        # --- Bottom Buttons ---
        items_btn_frame = ttk.Frame(main_container); items_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(items_btn_frame, text="حذف عنصر محدد", command=self.remove_selected_item).pack(side=tk.RIGHT, padx=5)
        save_btn = ttk.Button(items_btn_frame, text="حفظ وطباعة الفاتورة", command=self.save_and_print, style="Accent.TButton")
        save_btn.pack(side=tk.LEFT, padx=5, pady=5)

    def show_company_settings_dialog(self):
        dialog = tk.Toplevel(self.root); dialog.title("إعدادات الشركة"); dialog.geometry("500x450"); dialog.transient(self.root); dialog.grab_set()
        main_frame = ttk.Frame(dialog); main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas = tk.Canvas(main_frame); scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.pack(side=tk.RIGHT, fill=tk.Y); canvas.configure(yscrollcommand=scrollbar.set)
        settings_frame = ttk.Frame(canvas); canvas.create_window((0,0), window=settings_frame, anchor=tk.NW)
        ttk.Label(settings_frame, text="معلومات الشركة", font=("Arial",12,"bold")).grid(row=0,column=0,columnspan=2,pady=10)
        ttk.Label(settings_frame, text="اسم الشركة:").grid(row=1,column=0,sticky=tk.W,padx=5,pady=5)
        ttk.Entry(settings_frame, textvariable=self.company_name, width=40, justify='right').grid(row=1,column=1,sticky=tk.W,padx=5,pady=5)
        ttk.Label(settings_frame, text="العنوان:").grid(row=2,column=0,sticky=tk.NW,padx=5,pady=5)
        address_text = tk.Text(settings_frame, width=38, height=3, wrap=tk.WORD); address_text.grid(row=2,column=1,sticky=tk.W,padx=5,pady=5)
        if self.company_address.get(): address_text.insert("1.0", self.company_address.get())
        ttk.Label(settings_frame, text="الرقم الضريبي:").grid(row=3,column=0,sticky=tk.W,padx=5,pady=5)
        ttk.Entry(settings_frame, textvariable=self.company_vat, width=40, justify='right').grid(row=3,column=1,sticky=tk.W,padx=5,pady=5)
        ttk.Label(settings_frame, text="السجل التجاري:").grid(row=4,column=0,sticky=tk.W,padx=5,pady=5)
        ttk.Entry(settings_frame, textvariable=self.company_reg, width=40, justify='right').grid(row=4,column=1,sticky=tk.W,padx=5,pady=5)
        ttk.Label(settings_frame, text="رقم الهاتف:").grid(row=5,column=0,sticky=tk.W,padx=5,pady=5)
        ttk.Entry(settings_frame, textvariable=self.company_phone, width=40, justify='right').grid(row=5,column=1,sticky=tk.W,padx=5,pady=5)
        logo_frame = ttk.Frame(settings_frame); logo_frame.grid(row=6,column=0,columnspan=2,sticky=tk.W,padx=5,pady=10)
        ttk.Label(logo_frame, text="شعار الشركة:").pack(side=tk.RIGHT,padx=5); self.logo_label = ttk.Label(logo_frame, text="لم يتم اختيار شعار"); self.logo_label.pack(side=tk.RIGHT,padx=5)
        def browse_logo_dialog():
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")])
            if path: self.company_logo_path=path; self.logo_label.config(text=os.path.basename(path))
        ttk.Button(logo_frame, text="تصفح...", command=browse_logo_dialog).pack(side=tk.RIGHT,padx=5)
        stamp_frame = ttk.Frame(settings_frame); stamp_frame.grid(row=7,column=0,columnspan=2,sticky=tk.W,padx=5,pady=5)
        ttk.Label(stamp_frame, text="ختم الشركة:").pack(side=tk.RIGHT,padx=5); self.stamp_label = ttk.Label(stamp_frame, text="لم يتم اختيار ختم"); self.stamp_label.pack(side=tk.RIGHT,padx=5)
        def browse_stamp_dialog():
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")])
            if path: self.stamp_path=path; self.stamp_label.config(text=os.path.basename(path))
        ttk.Button(stamp_frame, text="تصفح...", command=browse_stamp_dialog).pack(side=tk.RIGHT,padx=5)
        button_frame = ttk.Frame(settings_frame); button_frame.grid(row=8,column=0,columnspan=2,pady=20)
        def save_settings(): self.company_address.set(address_text.get("1.0", "end-1c")); self.save_settings_to_config(); dialog.destroy()
        ttk.Button(button_frame, text="حفظ", command=save_settings).pack(side=tk.LEFT,padx=10); ttk.Button(button_frame, text="إلغاء", command=dialog.destroy).pack(side=tk.LEFT,padx=10)
        if self.company_logo_path: self.logo_label.config(text=os.path.basename(self.company_logo_path))
        if self.stamp_path: self.stamp_label.config(text=os.path.basename(self.stamp_path))
        settings_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # --- New Simplified Workflow Methods ---
    def get_formatted_date(self):
        # [FIX 2] Changed date format to YY/MM
        return self.date_picker.get_date().strftime("%y/%m")

    def add_tathmeen(self):
        quantity = simpledialog.askinteger("الكمية", "أدخل الكمية:", parent=self.root, minvalue=1)
        if not quantity: return
        
        date_str = self.get_formatted_date()
        item_name = f"تثمين المركبات شهر {date_str}"
        invoice_type = "أشعار دائن ضريبي"
        # [FIX 3] Set invoice type and reference in the background
        self.invoice_type.set(invoice_type)
        self.reference.set(f"{invoice_type} - {self.invoice_number.get()}")
        self.add_item_to_tree(item_name, quantity, 10.0)

    def add_taqdeer_client(self):
        invoice_type = "أشعار دائن ضريبي"
        self._add_taqdeer_item(
            invoice_type=invoice_type,
            name_template="مستحقات تقدير اضرار المركبات شهر {}",
            # [FIX 3] Set reference in the background
            reference_template=f"{invoice_type} - {{}}"
        )

    def add_taqdeer_insurance(self):
        invoice_type = "فاتورة ضريبية"
        self._add_taqdeer_item(
            invoice_type=invoice_type,
            name_template="إستحقاق تقدير اضرار المركبات شهر {}",
            # [FIX 3] Set reference in the background
            reference_template="استحقاق شهر {} تقدير اضرار المركبات"
        )

    def add_taqdeer_truck(self):
        quantity = simpledialog.askinteger("الكمية", "أدخل كمية الشاحنات:", parent=self.root, minvalue=1)
        if not quantity: return
        
        date_str = self.get_formatted_date()
        item_name = f"مستحقات تقدير المركبات (شاحنات) شهر {date_str}"
        invoice_type = "أشعار دائن ضريبي"
        # [FIX 3] Set invoice type and reference in the background
        self.invoice_type.set(invoice_type)
        self.reference.set(f"{invoice_type} - {self.invoice_number.get()}")
        self.add_item_to_tree(item_name, quantity, 45.0)

    def _add_taqdeer_item(self, invoice_type, name_template, reference_template):
        price = self.ask_for_price()
        if price is None: return

        quantity = simpledialog.askinteger("الكمية", "أدخل الكمية:", parent=self.root, minvalue=1)
        if not quantity: return
        
        date_str = self.get_formatted_date()
        item_name = name_template.format(date_str)
        # [FIX 3] Set reference and type in the background
        self.invoice_type.set(invoice_type)
        # For the reference, we pass either the date or the invoice number
        ref_arg = date_str if "{}" in reference_template and "استحقاق" in reference_template else self.invoice_number.get()
        self.reference.set(reference_template.format(ref_arg))
        self.add_item_to_tree(item_name, quantity, price)
        
    def ask_for_price(self):
        prices = [75, 56.25, 37.5, 18.75]
        dialog = tk.Toplevel(self.root); dialog.title("اختر السعر"); dialog.geometry("250x230"); dialog.transient(self.root); dialog.grab_set()
        
        ttk.Label(dialog, text="اختر سعر الوحدة:", font=("Arial", 12)).pack(pady=10)
        
        result = tk.DoubleVar()
        for price in prices:
            ttk.Radiobutton(dialog, text=f"{price} ريال", variable=result, value=price, style="TRadiobutton").pack(anchor=tk.E, padx=40, pady=4)
        
        ttk.Button(dialog, text="موافق", command=dialog.destroy, style="Accent.TButton").pack(pady=10)
        
        self.root.wait_window(dialog)
        return result.get() if result.get() != 0.0 else None

    # --- Core Item Handling ---
    def add_item_to_tree(self, name, quantity, unit_price, tax_rate=15.0):
        try:
            quantity=float(quantity); unit_price=float(unit_price); tax_rate=float(tax_rate)
            amount=quantity*unit_price; vat=amount*(tax_rate/100); total=amount+vat
            item_id = self.items_tree.insert("", "end", values=(name, f"{quantity:.2f}", f"{unit_price:.2f}", f"{tax_rate:.2f}%", f"{amount:.2f}", f"{vat:.2f}", f"{total:.2f}"))
            self.invoice_items.append({"id": item_id, "name": name, "quantity": quantity, "unit_price": unit_price, "tax_rate": tax_rate, "amount": amount, "vat": vat, "total": total})
        except ValueError as e: messagebox.showerror("خطأ", f"بيانات خاطئة: {e}")

    def edit_selected_item(self, event=None):
        selected = self.items_tree.selection()
        if not selected: return
        item_id = selected[0]; item = next((i for i in self.invoice_items if i["id"] == item_id), None)
        if not item: return

        dialog = tk.Toplevel(self.root); dialog.title("تعديل العنصر"); dialog.geometry("400x250"); dialog.transient(self.root); dialog.grab_set()
        name_var=tk.StringVar(value=item["name"]); quantity_var=tk.StringVar(value=str(item["quantity"])); price_var=tk.StringVar(value=str(item["unit_price"]))
        
        ttk.Label(dialog,text="اسم المنتج:").grid(row=0,column=0,padx=5,pady=5,sticky=tk.W)
        ttk.Entry(dialog,textvariable=name_var,width=30, justify='right').grid(row=0,column=1,padx=5,pady=5,sticky=tk.W)
        ttk.Label(dialog,text="الكمية:").grid(row=1,column=0,padx=5,pady=5,sticky=tk.W)
        ttk.Entry(dialog,textvariable=quantity_var,width=30, justify='right').grid(row=1,column=1,padx=5,pady=5,sticky=tk.W)
        ttk.Label(dialog,text="سعر الوحدة:").grid(row=2,column=0,padx=5,pady=5,sticky=tk.W)
        ttk.Entry(dialog,textvariable=price_var,width=30, justify='right').grid(row=2,column=1,padx=5,pady=5,sticky=tk.W)
        
        def update_item():
            try:
                name=name_var.get(); quantity=float(quantity_var.get()); unit_price=float(price_var.get()); tax_rate=item['tax_rate']
                if not name: raise ValueError("يجب إدخال اسم المنتج")
                amount=quantity*unit_price; vat=amount*(tax_rate/100); total=amount+vat
                for i, inv_item in enumerate(self.invoice_items):
                    if inv_item["id"] == item_id:
                        self.invoice_items[i].update({"name": name, "quantity": quantity, "unit_price": unit_price, "amount": amount, "vat": vat, "total": total}); break
                self.items_tree.item(item_id, values=(name, f"{quantity:.2f}", f"{unit_price:.2f}", f"{tax_rate:.2f}%", f"{amount:.2f}", f"{vat:.2f}", f"{total:.2f}")); dialog.destroy()
            except ValueError as e: messagebox.showerror("خطأ", str(e) if str(e) else "بيانات خاطئة")
        
        button_frame=ttk.Frame(dialog); button_frame.grid(row=4,column=0,columnspan=2,pady=10)
        ttk.Button(button_frame,text="تحديث",command=update_item).pack(side=tk.LEFT,padx=5); ttk.Button(button_frame,text="إلغاء",command=dialog.destroy).pack(side=tk.LEFT,padx=5)
    
    def remove_selected_item(self):
        selected = self.items_tree.selection()
        if not selected: messagebox.showinfo("تنبيه", "الرجاء اختيار عنصر لحذفه"); return
        if messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف العنصر المحدد؟"):
            for item_id in selected: self.invoice_items = [item for item in self.invoice_items if item["id"] != item_id]; self.items_tree.delete(item_id)

    def save_and_print(self):
        if not self.invoice_items: messagebox.showwarning("تنبيه", "لا يمكن حفظ فاتورة فارغة"); return
        
        base_filename = self.invoice_number.get()
        file_path_base = filedialog.asksaveasfilename(initialdir=INVOICES_DIR, initialfile=base_filename, defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not file_path_base: return

        pdf_path = file_path_base; json_path = os.path.splitext(file_path_base)[0] + ".json"
        
        # Make sure an invoice type is set, default if empty
        if not self.invoice_type.get(): self.invoice_type.set("فاتورة ضريبية")

        try:
            subtotal, total_vat, total = calculate_totals(self.invoice_items)
            invoice_data = {
                "company": {"name":self.company_name.get(),"address":self.company_address.get(),"vat":self.company_vat.get(),"reg":self.company_reg.get(),"phone":self.company_phone.get(),"logo_path":self.company_logo_path,"stamp_path":self.stamp_path},
                "najm": {"name":self.najm_name.get(),"address":self.najm_address.get(),"vat":self.najm_vat.get(),"reg":self.najm_reg.get()},
                "invoice": {"type":self.invoice_type.get(),"number":self.invoice_number.get(),"date":self.date_picker.get(),"reference":self.reference.get()},
                "items": self.invoice_items,
                "totals":{"subtotal":subtotal,"vat":total_vat,"total":total}
            }
            
            with open(json_path, 'w', encoding='utf-8') as f: json.dump(invoice_data, f, indent=4, ensure_ascii=False)
            success = create_invoice_pdf(pdf_path, invoice_data)
            
            if success:
                messagebox.showinfo("تم", f"تم حفظ الفاتورة والبيانات بنجاح")
                if messagebox.askyesno("فتح الملف", "هل ترغب في فتح ملف PDF؟"): webbrowser.open(pdf_path)
                if self.is_new_invoice: update_invoice_number_config()
                self.clear_invoice()
            else:
                messagebox.showerror("خطأ", "فشل إنشاء ملف PDF")
                if os.path.exists(json_path): os.remove(json_path)
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ: {str(e)}"); traceback.print_exc()
    
    def clear_invoice(self):
        for item_id in self.items_tree.get_children(): self.items_tree.delete(item_id)
        self.invoice_items = []; self.invoice_number.set(get_next_invoice_number())
        if CALENDAR_SUPPORT: self.date_picker.set_date(datetime.now())
        self.reference.set(""); self.invoice_type.set(""); self.is_new_invoice = True

    # --- New Search and Edit ---
    def search_and_edit_invoice(self):
        invoice_files = find_invoice_files()
        if not invoice_files: messagebox.showinfo("معلومات", "لا توجد فواتير سابقة"); return

        dialog = tk.Toplevel(self.root); dialog.title("بحث وتعديل فاتورة"); dialog.geometry("450x400"); dialog.transient(self.root); dialog.grab_set()
        ttk.Label(dialog, text="اختر فاتورة:", font=("Arial", 12)).pack(pady=10)
        frame = ttk.Frame(dialog); frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(frame); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Arial", 10)); listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.config(command=listbox.yview)
        
        for filename in invoice_files: listbox.insert(tk.END, os.path.splitext(filename)[0])

        def handle_selection(action):
            selection = listbox.curselection()
            if not selection: messagebox.showinfo("تنبيه", "الرجاء اختيار فاتورة أولاً"); return
            
            base_filename = listbox.get(selection[0])
            json_path = os.path.join(INVOICES_DIR, base_filename + ".json"); pdf_path = os.path.join(INVOICES_DIR, base_filename + ".pdf")

            if action == 'edit':
                if os.path.exists(json_path): self.load_invoice_for_editing(json_path); dialog.destroy()
                else: messagebox.showerror("خطأ", "ملف بيانات الفاتورة غير موجود!")
            elif action == 'view':
                if os.path.exists(pdf_path): webbrowser.open(pdf_path)
                else: messagebox.showerror("خطأ", "ملف PDF للفاتورة غير موجود!")

        button_frame = ttk.Frame(dialog); button_frame.pack(pady=10)
        ttk.Button(button_frame, text="تعديل", command=lambda: handle_selection('edit')).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="عرض PDF", command=lambda: handle_selection('view')).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="إلغاء", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def load_invoice_for_editing(self, json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)

            for item_id in self.items_tree.get_children(): self.items_tree.delete(item_id)
            self.invoice_items = []
            
            invoice_info = data['invoice']
            self.invoice_number.set(invoice_info['number'])
            self.reference.set(invoice_info['reference'])
            self.invoice_type.set(invoice_info['type'])
            
            date_obj = datetime.strptime(invoice_info['date'], "%d-%m-%Y")
            self.date_picker.set_date(date_obj)

            for item in data['items']: self.add_item_to_tree(item['name'], item['quantity'], item['unit_price'], item['tax_rate'])
            
            self.is_new_invoice = False
        except Exception as e:
            messagebox.showerror("خطأ في التحميل", f"لم يتم تحميل بيانات الفاتورة: {e}"); traceback.print_exc()

if __name__ == "__main__":
    if not PDF_SUPPORT or not ARABIC_SUPPORT or not CALENDAR_SUPPORT:
        print("\n--- تحذير: بعض المكتبات المطلوبة غير مثبتة ---")
        if not PDF_SUPPORT: print("دعم PDF معطل. قم بتثبيت: pip install fpdf2 qrcode")
        if not ARABIC_SUPPORT: print("دعم اللغة العربية معطل. قم بتثبيت: pip install arabic-reshaper python-bidi")
        if not CALENDAR_SUPPORT: print("أداة التقويم معطلة. قم بتثبيت: pip install tkcalendar")
        print("-------------------------------------------------")
    root = tk.Tk()
    app = InvoiceApp(root)
    root.mainloop()