from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph

def generate_subject_performance_pdf(response, student_data, subjects, class_averages, term_performance, academic_performance):
    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    # Title
    title = Paragraph("<b>Subject Performance Analysis Report</b>", styles["Title"])
    elements.append(title)

    # Space
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # **Student Performance Table**
    student_table_data = [["Student Name"] + subjects]

    # Add Student Data
    for student, marks in sorted(student_data.items()):
        row = [student] + [marks.get(subject, "-") for subject in subjects]
        student_table_data.append(row)

    # Add Class Average Row
    student_table_data.append(["Class Average"] + [class_averages.get(subject, "-") for subject in subjects])

    student_table = Table(student_table_data, repeatRows=1)
    student_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey)
    ]))
    elements.append(student_table)

    # Space
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # **Term Performance Table**
    term_table_data = [["Subject"] + list(term_performance.keys())]
    for subject in subjects:
        row = [subject] + [term_performance.get(term, {}).get(subject, "-") for term in term_performance]
        term_table_data.append(row)

    term_table = Table(term_table_data, repeatRows=1)
    term_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(Paragraph("<b>Term Performance</b>", styles["Heading2"]))
    elements.append(term_table)

    # Space
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # **Academic Year Performance Table**
    year_table_data = [["Subject", "Past Two Years", "Current Year"]]
    for subject in subjects:
        row = [subject, academic_performance.get(subject, {}).get("past_years", "-"), academic_performance.get(subject, {}).get("current_year", "-")]
        year_table_data.append(row)

    year_table = Table(year_table_data, repeatRows=1)
    year_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(Paragraph("<b>Academic Year Performance</b>", styles["Heading2"]))
    elements.append(year_table)

    doc.build(elements)
