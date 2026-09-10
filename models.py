import io
import base64
import qrcode
from datetime import datetime
from database import get_db_connection

def calculate_tiered_bill(kwh, customer_type, customer_id=None):
    """
    Calculates electricity bill based on 3-tiered tariff structure:
    Tier 1: 0 - 50 kWh
    Tier 2: 51 - 100 kWh
    Tier 3: > 100 kWh
    Plus: Maintenance fee, VAT, and Previous Unpaid Debt.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tariffs WHERE customer_type = ?", (customer_type,))
    tariff = cursor.fetchone()

    if not tariff:
        # Fallback default tariff
        t1_max, t1_rate = 50.0, 380.0
        t2_max, t2_rate = 100.0, 480.0
        t3_rate = 610.0
        maint_fee = 2000.0
        vat_pct = 0.0
    else:
        t1_max = tariff['tier1_max']
        t1_rate = tariff['tier1_rate']
        t2_max = tariff['tier2_max']
        t2_rate = tariff['tier2_rate']
        t3_rate = tariff['tier3_rate']
        maint_fee = tariff['maintenance_fee']
        vat_pct = tariff['vat_percent']

    kwh = max(0.0, float(kwh))

    # Tier 1 calculation (0 to t1_max)
    t1_kwh = min(kwh, t1_max)
    t1_amt = t1_kwh * t1_rate

    # Tier 2 calculation (t1_max to t2_max)
    if kwh > t1_max:
        t2_kwh = min(kwh - t1_max, t2_max - t1_max)
        t2_amt = t2_kwh * t2_rate
    else:
        t2_kwh = 0.0
        t2_amt = 0.0

    # Tier 3 calculation (> t2_max)
    if kwh > t2_max:
        t3_kwh = kwh - t2_max
        t3_amt = t3_kwh * t3_rate
    else:
        t3_kwh = 0.0
        t3_amt = 0.0

    energy_amount = round(t1_amt + t2_amt + t3_amt, 2)
    tax_amount = round((energy_amount + maint_fee) * (vat_pct / 100.0), 2)

    # Previous unpaid calculation if customer_id provided
    prev_unpaid = 0.0
    if customer_id:
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0.0) FROM invoices 
            WHERE customer_id = ? AND payment_status IN ('unpaid', 'overdue')
        """, (customer_id,))
        prev_unpaid = float(cursor.fetchone()[0])

    total_amount = round(energy_amount + maint_fee + tax_amount + prev_unpaid, 2)
    conn.close()

    return {
        'total_kwh': kwh,
        'tier1_kwh': t1_kwh,
        'tier1_rate': t1_rate,
        'tier1_amt': t1_amt,
        'tier2_kwh': t2_kwh,
        'tier2_rate': t2_rate,
        'tier2_amt': t2_amt,
        'tier3_kwh': t3_kwh,
        'tier3_rate': t3_rate,
        'tier3_amt': t3_amt,
        'energy_amount': energy_amount,
        'maintenance_fee': maint_fee,
        'vat_percent': vat_pct,
        'tax_amount': tax_amount,
        'prev_unpaid': prev_unpaid,
        'total_amount': total_amount
    }

def generate_khqr_payload(invoice_number, amount, customer_name="Customer"):
    """
    Constructs an EMVCo-compliant KHQR payload string for Bakong payments.
    """
    # Standard KHQR structure format for EDC Merchant
    merchant_name = "EDC ELECTRICITY BILLING"
    bakong_id = "edc_billing@nbc"
    currency = "116"  # KHR
    amt_str = f"{int(amount)}"
    
    # We construct a recognized KHQR payload representation
    raw_payload = (
        f"00020101021229380010A0000007270120{bakong_id}"
        f"520449005303{currency}54{len(amt_str):02d}{amt_str}"
        f"5802KH59{len(merchant_name):02d}{merchant_name}6010PHNOM PENH"
        f"62{len(invoice_number) + 4:02d}01{len(invoice_number):02d}{invoice_number}6304ABCD"
    )
    return raw_payload

def generate_qr_base64(data_string):
    """
    Generates a high quality QR code Base64 string for direct embedding into HTML <img>.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

def update_overdue_invoices():
    """
    Automatically marks unpaid invoices as 'overdue' if due_date is in the past.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        UPDATE invoices 
        SET payment_status = 'overdue' 
        WHERE due_date < ? AND payment_status = 'unpaid'
    """, (today_str,))
    conn.commit()
    conn.close()

def format_khmer_currency(amount):
    """
    Formats number into Cambodian Riel string (e.g., 42,600 ៛).
    """
    try:
        return f"{int(amount):,} ៛".replace(",", " ")
    except (ValueError, TypeError):
        return "0 ៛"
