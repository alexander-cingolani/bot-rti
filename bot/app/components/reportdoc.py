from datetime import datetime
from textwrap import wrap

from app.components.models import Driver, Report
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


class ReviewedReportDocument:
    def __init__(self, report: Report) -> None:
        if not report.time_penalty or not report.championship_penalty_points:
            self.filename = (
                f"{report.number} - Decisione {report.reported_driver.psn_id}.pdf"
            )
        else:
            self.filename = (
                f"{report.number} - Penalità {report.reported_driver.psn_id}.pdf"
            )

        self.report: Report = report
        self.subtitle: str = f"{report.round.number}ª Tappa | {report.round.circuit}"
        self.reported_driver: Driver = report.reported_driver
        self.reporting_driver: Driver = report.reporting_driver
        self.date: str = datetime.now().date().strftime("%d %b %Y")
        self.time: str = datetime.now().time().strftime("%H:%M")

    filename: str

    def generate_document(self) -> str:
        """Generates the report document named as the filename attribute"""
        pdfmetrics.registerFont(TTFont("arial", "./app/fonts/arial.ttf"))
        pdfmetrics.registerFont(TTFont("arialB", "./app/fonts/arialB.ttf"))

        pdf = canvas.Canvas(filename=self.filename)
        pdf.setTitle(self.filename)

        pdf.drawImage(
            "./app/images/logo_rti.jpg",
            x=220,
            y=715,
            height=100,
            width=200,
            preserveAspectRatio=True,
        )

        pdf.setLineWidth(0.1)
        pdf.line(x1=50, x2=550, y1=640, y2=640)
        pdf.line(x1=50, x2=550, y1=560, y2=560)

        pdf.setFont("arialB", 24)
        pdf.drawCentredString(297, 680, f"CATEGORIA {self.report.category.name}")

        pdf.setFont("arialB", 14)
        pdf.drawCentredString(297, 663, self.subtitle)

        pdf.setFont("arialB", 11)
        pdf.drawString(50, 620, "Da")
        pdf.drawString(50, 600, "Per")
        pdf.drawString(410, 620, "Documento")
        pdf.drawString(410, 600, "Data")
        pdf.drawString(410, 580, "Orario")
        pdf.setFont("arial", 11)
        pdf.drawString(
            50,
            540,
            "La Safety Commission, in seguito alla segnalazione ricevuta, ha analizzato"
            " l'episodio e determina che:",
        )
        pdf.setFont("arialB", 11.5)
        pdf.drawString(50, 500, "No / Pilota")
        pdf.drawString(50, 475, "Scuderia")
        pdf.drawString(50, 450, "Minuto")
        pdf.drawString(50, 425, "Sessione")
        pdf.drawString(50, 400, "Fatto")
        pdf.drawString(50, 375, "Violazione")
        pdf.drawString(50, 350, "Decisione")
        pdf.drawString(50, 325, "Motivazioni")
        pdf.setFont("arial", 11)

        reported_driver_team_name = self.reported_driver.current_team().name

        pdf.drawString(75, 619, "Safety Commission")
        pdf.drawString(75, 599, "Capo Scuderia,")
        pdf.drawString(75, 585, f"Scuderia {reported_driver_team_name}")
        pdf.drawString(480, 619, str(self.report.number))
        pdf.drawString(480, 599, self.date)
        pdf.drawString(480, 579, self.time)
        pdf.setFontSize(11)
        pdf.drawString(
            135,
            499,
            f"{self.reported_driver.current_race_number} / {self.reported_driver.psn_id}",
        )
        pdf.drawString(135, 475, reported_driver_team_name)
        pdf.drawString(135, 450, self.report.incident_time)
        pdf.drawString(135, 425, self.report.session.name)
        text = self.report.penalty_reason
        text = "\n".join(wrap(text, 80)).split("\n")
        pdf.drawString(135, 400, self.report.fact)
        pdf.drawString(135, 375, "Regolamento Sportivo RTI")
        pdf.drawString(135, 350, self.report.penalty)
        y0 = 325
        for line in text:
            pdf.drawString(135, y0, line)
            y0 -= 15

        pdf.setFont("arialB", 11.5)
        pdf.drawString(50, y0 - 55, "Direzione Gara")
        pdf.drawString(295, y0 - 55, "Safety Commission")

        pdf.save()
        return self.filename


class ReportDocument:
    def __init__(self, report: Report) -> None:
        self.report: Report = report
        self.reported_driver: Driver = report.reported_driver
        self.reporting_driver: Driver = report.reporting_driver
        self.filename: str = (
            f"{self.report.number} - Segnalazione {self.reported_driver.psn_id}.pdf"
        )
        self.subtitle: str = f"{report.round.number}ª Tappa | {report.round.circuit}"

        self.date: str = datetime.now().date().strftime("%d %b %Y")
        self.time: str = datetime.now().time().strftime("%H:%M")

    filename: str

    def generate_document(self) -> str:
        pdf = canvas.Canvas(self.filename)
        pdfmetrics.registerFont(TTFont("arial", "./app/fonts/arial.ttf"))
        pdfmetrics.registerFont(TTFont("arialB", "./app/fonts/arialB.ttf"))

        pdf.setTitle(self.filename)
        logo_rti = "./app/images/logo_rti.jpg"
        pdf.drawImage(
            logo_rti, x=220, y=715, height=90, width=180, preserveAspectRatio=True
        )

        pdf.setFont("arialB", 28)
        pdf.drawCentredString(297, 690, f"CATEGORIA {self.report.category.name}")

        pdf.setFont("arialB", 14)
        pdf.drawCentredString(297, 663, self.subtitle)
        pdf.setFont("arialB", 10)
        pdf.drawString(50, 620, "Da")
        pdf.drawString(50, 600, "Per")
        pdf.drawString(410, 620, "Documento")
        pdf.drawString(410, 600, "Data")
        pdf.drawString(410, 580, "Orario")
        pdf.setFont("arialB", 11.5)
        pdf.drawString(50, 500, "No / Vittima")
        pdf.drawString(50, 475, "No / Colpevole")
        pdf.drawString(50, 450, "Scuderia")
        pdf.drawString(50, 425, "Minuto")
        pdf.drawString(50, 400, "Sessione")
        pdf.drawString(50, 375, "Fatto")
        pdf.setFont("arial", 10)

        pdf.drawString(75, 619, f"Scuderia {self.reporting_driver.current_team().name}")
        pdf.drawString(75, 599, "Safety Commission")
        pdf.drawString(480, 619, str(self.report.number))
        pdf.drawString(480, 599, self.date)
        pdf.drawString(480, 579, self.time)
        pdf.setFont("arial", 11)
        pdf.drawString(
            50,
            540,
            f"La scuderia {self.reporting_driver.current_team().name} "
            "chiede la revisione del seguente incidente:",
        )
        pdf.drawString(
            155,
            499,
            f"{self.reporting_driver.current_race_number} / {self.reporting_driver.psn_id}",
        )
        pdf.drawString(
            155,
            474,
            f"{self.reported_driver.current_race_number} / {self.reported_driver.psn_id}",
        )
        pdf.drawString(155, 449, self.reported_driver.current_team().name)
        pdf.drawString(155, 424, self.report.incident_time)
        pdf.drawString(155, 399, self.report.session.name)
        text = "\n".join(wrap(self.report.report_reason, 80)).split("\n")
        y0 = 374
        for line in text:
            pdf.drawString(155, y0, line)
            y0 -= 15

        if self.report.video_link:
            pdf.setFont("arialB", 11.5)
            pdf.drawString(50, y0 - 15, "Video")
            pdf.setFont("arial", 10)
            pdf.drawString(155, y0 - 15, self.report.video_link)

        pdf.setLineWidth(0.1)
        pdf.line(x1=50, x2=550, y1=640, y2=640)
        pdf.line(x1=50, x2=550, y1=560, y2=560)

        pdf.save()
        return self.filename
