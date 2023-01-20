"""
This module contains the PenaltyDocument and ReportDocument classes, which generate a pdf
file given a Penalty or Report object.
"""
from datetime import datetime
from textwrap import wrap

from reportlab.pdfbase import pdfmetrics  # type: ignore
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore

from models import Driver, Penalty, Report

pdfmetrics.registerFont(TTFont("arial", "./app/assets/fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("arialB", "./app/assets/fonts/arialB.ttf"))


class PenaltyDocument:
    def __init__(
        self,
        penalty: Penalty,
    ) -> None:
        if not penalty.time_penalty and not penalty.penalty_points:
            filename = f"{penalty.number} - Decisione {penalty.driver.psn_id}.pdf"
        else:
            filename = f"{penalty.number} - Penalità {penalty.driver.psn_id}.pdf"

        self.penalty: Penalty = penalty
        self.canvas = canvas.Canvas(filename=filename)
        self.canvas.setTitle(filename)

    def __header(self):
        self.canvas.drawImage(
            "./app/assets/images/logo_rti.jpg",
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

        reported_team = self.penalty.driver.current_team()
        if not reported_team:
            reported_team_name = "-"
        else:
            reported_team_name = reported_team.name

        self.canvas.drawString(75, 585, f"Scuderia {reported_team_name}")
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

        driver = self.penalty.driver
        self.canvas.drawString(
            135,
            499,
            f"{driver.current_race_number} / {driver.psn_id}",
        )

        reported_team = driver.current_team()
        if not reported_team:
            reported_team_name = "-"
        else:
            reported_team_name = reported_team.name

        self.canvas.drawString(135, 475, reported_team_name)
        self.canvas.drawString(135, 450, self.penalty.incident_time)
        self.canvas.drawString(135, 425, self.penalty.session.name)
        self.canvas.drawString(135, 400, self.penalty.fact)
        self.canvas.drawString(135, 375, "Regolamento Sportivo RTI")
        self.canvas.drawString(135, 350, self.penalty.decision)

        text = self.penalty.penalty_reason
        lines = "\n".join(wrap(text, 80)).split("\n")
        y_coord = 325
        for line in lines:
            self.canvas.drawString(135, y_coord, line)
            y_coord -= 15

        self.canvas.setFont("arialB", 11.5)
        self.canvas.drawString(50, y_coord - 55, "Direzione Gara")
        self.canvas.drawString(295, y_coord - 55, "Safety Commission")

    def generate_document(self) -> str:
        """Generates and saves the document returning its name"""

        self.__header()
        self.__body()

        self.canvas.save()

        return self.canvas._filename


class ReportDocument:
    def __init__(self, report: Report) -> None:
        self.report: Report = report
        self.reporting_driver: Driver = report.reporting_driver
        self.filename: str = f"{self.report.number} - Segnalazione {self.report.reported_driver.psn_id}.pdf"
        self.subtitle: str = f"{report.round.number}ª Tappa | {report.round.circuit}"
        self.canvas = canvas.Canvas(self.filename)

    filename: str

    def __header(self) -> None:

        logo_rti = "./app/assets/images/logo_rti.jpg"
        self.canvas.drawImage(
            logo_rti, x=220, y=715, height=90, width=180, preserveAspectRatio=True
        )

        self.canvas.setLineWidth(0.1)
        self.canvas.line(x1=50, x2=550, y1=640, y2=640)
        self.canvas.line(x1=50, x2=550, y1=560, y2=560)

        self.canvas.setFont("arialB", 28)
        self.canvas.drawCentredString(
            297, 690, f"CATEGORIA {self.report.category.name}"
        )
        self.canvas.setFont("arialB", 14)
        self.canvas.drawCentredString(297, 663, self.subtitle)
        self.canvas.setFont("arialB", 10)
        self.canvas.drawString(50, 620, "Da")
        self.canvas.drawString(50, 600, "Per")
        self.canvas.drawString(410, 620, "Documento")
        self.canvas.drawString(410, 600, "Data")
        self.canvas.drawString(410, 580, "Orario")
        self.canvas.setFont("arial", 10)

        current_team = self.reporting_driver.current_team()
        if not current_team:
            team_name = "-"
        else:
            team_name = current_team.name

        self.canvas.drawString(75, 619, f"Scuderia {team_name}")
        self.canvas.drawString(75, 599, "Safety Commission")
        self.canvas.drawString(480, 619, str(self.report.number))
        self.canvas.drawString(480, 599, datetime.now().date().strftime("%d %b %Y"))
        self.canvas.drawString(480, 579, datetime.now().time().strftime("%H:%M"))
        self.canvas.setFont("arial", 11)

        self.canvas.drawString(
            50,
            540,
            f"La scuderia {team_name} " "chiede la revisione del seguente incidente:",
        )

    def __body(self):
        self.canvas.setFont("arialB", 11.5)
        self.canvas.drawString(50, 500, "No / Vittima")
        self.canvas.drawString(50, 475, "No / Colpevole")
        self.canvas.drawString(50, 450, "Scuderia")
        self.canvas.drawString(50, 425, "Minuto")
        self.canvas.drawString(50, 400, "Sessione")
        self.canvas.drawString(50, 375, "Fatto")

        reported_driver = self.report.reported_driver
        reporting_driver = self.report.reporting_driver
        self.canvas.drawString(
            155,
            499,
            f"{reporting_driver.current_race_number} / {reporting_driver.psn_id}",
        )
        self.canvas.drawString(
            155,
            474,
            f"{self.report.reported_driver.current_race_number} / {self.report.reported_driver.psn_id}",
        )

        reported_team = reported_driver.current_team()
        if not reported_team:
            reported_team_name = "-"
        else:
            reported_team_name = reported_team.name

        self.canvas.drawString(155, 449, reported_team_name)
        self.canvas.drawString(155, 424, self.report.incident_time)
        self.canvas.drawString(155, 399, self.report.session.name)
        text = "\n".join(wrap(self.report.report_reason, 80)).split("\n")
        y0 = 374
        for line in text:
            self.canvas.drawString(155, y0, line)
            y0 -= 15

        if self.report.video_link:
            self.canvas.setFont("arialB", 11.5)
            self.canvas.drawString(50, y0 - 15, "Video")
            self.canvas.setFont("arial", 10)
            self.canvas.drawString(155, y0 - 15, self.report.video_link)

    def generate_document(self) -> str:
        """Generates and saves the document returning its name"""

        self.canvas.setTitle(self.filename)
        self.__header()
        self.__body()
        self.canvas.save()
        return self.filename
