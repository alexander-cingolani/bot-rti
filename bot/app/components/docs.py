"""
This module contains the PenaltyDocument and ReportDocument classes, which generate a pdf
file given a Penalty or Report object.
"""
from datetime import datetime
from textwrap import wrap

from app.components.models import Driver, Penalty, Report
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(TTFont("arial", "./app/fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("arialB", "./app/fonts/arialB.ttf"))


class PenaltyDocument:
    def __init__(
        self,
        penalty: Penalty,
    ) -> None:
        if not penalty.time_penalty and not penalty.penalty_points:
            filename = (
                f"{penalty.number} - Decisione {penalty.reported_driver.psn_id}.pdf"
            )
        else:
            filename = (
                f"{penalty.number} - Penalità {penalty.reported_driver.psn_id}.pdf"
            )

        self.penalty: Penalty = penalty
        self.reported_driver: Driver = penalty.reported_driver
        self.canvas = canvas.Canvas(filename=filename)
        self.canvas.setTitle(filename)

    def __header(self):
        self.canvas.drawImage(
            "./app/images/logo_rti.jpg",
            x=220,
            y=715,
            height=100,
            width=200,
            preserveAspectRatio=True,
        )

        self.canvas.setLineWidth(0.1)
        self.canvas.line(x1=50, x2=550, y1=640, y2=640)
        self.canvas.line(x1=50, x2=550, y1=560, y2=560)

        self.canvas.setFont("arialB", 24)
        self.canvas.drawCentredString(
            297, 680, f"CATEGORIA {self.penalty.category.name}"
        )

        self.canvas.setFontSize(14)
        self.canvas.drawCentredString(
            297,
            663,
            f"{self.penalty.round.number}ª Tappa | {self.penalty.round.circuit}",
        )

        self.canvas.setFontSize(11)
        self.canvas.drawString(50, 620, "Da")
        self.canvas.drawString(50, 600, "Per")
        self.canvas.drawString(410, 620, "Documento")
        self.canvas.drawString(410, 600, "Data")
        self.canvas.drawString(410, 580, "Orario")
        self.canvas.drawString(75, 619, "Safety Commission")
        self.canvas.drawString(75, 599, "Capo Scuderia,")

        self.canvas.setFont("arial", 11)
        self.canvas.drawString(
            75, 585, f"Scuderia {self.reported_driver.current_team().name}"
        )
        self.canvas.drawString(480, 619, str(self.penalty.number))
        self.canvas.drawString(480, 599, datetime.now().date().strftime("%d %b %Y"))
        self.canvas.drawString(480, 579, datetime.now().time().strftime("%H:%M"))

    def __body(self):
        self.canvas.setFont("arialB", 11.5)
        self.canvas.drawString(50, 500, "No / Pilota")
        self.canvas.drawString(50, 475, "Scuderia")
        self.canvas.drawString(50, 450, "Minuto")
        self.canvas.drawString(50, 425, "Sessione")
        self.canvas.drawString(50, 400, "Fatto")
        self.canvas.drawString(50, 375, "Violazione")
        self.canvas.drawString(50, 350, "Decisione")
        self.canvas.drawString(50, 325, "Motivazioni")

        self.canvas.setFont("arial", 11)
        self.canvas.drawString(
            50,
            540,
            "La Safety Commission, in seguito alla segnalazione ricevuta, ha analizzato"
            " l'episodio e determina che:",
        )

        self.canvas.drawString(
            135,
            499,
            f"{self.reported_driver.current_race_number} / {self.reported_driver.psn_id}",
        )
        self.canvas.drawString(135, 475, self.reported_driver.current_team().name)
        self.canvas.drawString(135, 450, self.penalty.incident_time)
        self.canvas.drawString(135, 425, self.penalty.session.name)
        self.canvas.drawString(135, 400, self.penalty.fact)
        self.canvas.drawString(135, 375, "Regolamento Sportivo RTI")
        self.canvas.drawString(135, 350, self.penalty.decision)

        text = self.penalty.penalty_reason
        text = "\n".join(wrap(text, 80)).split("\n")
        y_coord = 325
        for line in text:
            self.canvas.drawString(135, y_coord, line)
            y_coord -= 15

        self.canvas.setFont("arialB", 11.5)
        self.canvas.drawString(50, y_coord - 55, "Direzione Gara")
        self.canvas.drawString(295, y_coord - 55, "Safety Commission")

    def generate_document(self) -> str:
        """Generates the report document named as the filename attribute"""

        self.__header()
        self.__body()

        self.canvas.save()

        return self.canvas._filename


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
