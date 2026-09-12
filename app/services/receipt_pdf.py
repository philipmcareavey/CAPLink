"""Technical Implementation Plan 3.d.iii — auto-generated PDF receipts on
milestone payment, for both the business's and student's own records. Built
on request (GET /payments/milestones/{id}/receipt.pdf), not pre-generated
and stored — there's nowhere sensible to store a per-user file today (no
object storage/CDN exists yet, see 1.d.iii), and a paid milestone's
underlying data never changes afterward, so regenerating on demand is
exactly as accurate as a stored copy would be, with no extra storage or
cleanup to manage.
"""
from fpdf import FPDF

from app.models.contract import Contract, Milestone
from app.models.project import Project
from app.models.user import BusinessProfile, StudentProfile
from app.services.stripe_payments import calculate_platform_fee_gbp


def generate_milestone_receipt_pdf(
    *,
    milestone: Milestone,
    contract: Contract,
    project: Project,
    business: BusinessProfile,
    student: StudentProfile,
) -> bytes:
    platform_fee = calculate_platform_fee_gbp(milestone.payment_amount_gbp)
    net_to_student = round(milestone.payment_amount_gbp - platform_fee, 2)
    paid_on = milestone.captured_at.strftime("%d %B %Y") if milestone.captured_at else "Not yet captured"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CAPLink Payment Receipt", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Receipt for milestone {milestone.id}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Project", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, project.title)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Milestone", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, milestone.description)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Parties", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Business: {business.company_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Student: {student.user.full_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Payment", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Amount paid by business: GBP {milestone.payment_amount_gbp:.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"CAPLink platform fee: GBP {platform_fee:.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Net amount to student: GBP {net_to_student:.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Date paid: {paid_on}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
