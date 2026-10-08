"""PDF report (multi-page, light theme) with model summary, figures and developer credit."""
import textwrap

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from appinfo import APP_NAME, APP_SUBTITLE, CREDIT
from visualization.theme import LIGHT, credit


def write_report(path, title: str, summary_lines: list, figure_builders: list, meta: dict):
    """figure_builders: list of callables fig -> None that draw on an empty Figure (LIGHT theme)."""
    with PdfPages(path) as pdf:
        fig = Figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.95, APP_NAME, fontsize=22, weight="bold", color="#0d2a4a")
        fig.text(0.08, 0.925, APP_SUBTITLE, fontsize=10, color="#555555")
        fig.text(0.08, 0.89, title, fontsize=14, weight="bold")
        y = 0.86
        for line in summary_lines:
            for sub in textwrap.wrap(str(line), 95) or [""]:
                fig.text(0.08, y, sub, fontsize=8.5, family="monospace")
                y -= 0.016
                if y < 0.08:
                    break
        fig.text(0.08, 0.05, f"Created: {meta.get('created', '')}", fontsize=8, color="#555555")
        fig.text(0.08, 0.035, CREDIT, fontsize=9, style="italic", color="#0d2a4a")
        pdf.savefig(fig)
        for build in figure_builders:
            fig = Figure(figsize=(11.69, 8.27))
            build(fig)
            credit(fig, LIGHT, CREDIT)
            pdf.savefig(fig)
        d = pdf.infodict()
        d["Title"] = f"{APP_NAME} - {title}"
        d["Author"] = CREDIT
