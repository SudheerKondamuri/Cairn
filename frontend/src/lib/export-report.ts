import type { Report } from "./reports";
export function reportMarkdown(report: Report) {
  return `# Cairn investigation: ${report.verdict}\n\n${report.summary}\n\n## Claim\n\n${report.claim.report}\n\n## Evidence\n\nSource hash: ${report.evidence.source_hash}\n\nIndependent recheck: ${report.evidence.independent_recheck?.outcome || "Not available"}\n\n${report.evidence.attempts.map((a, i) => `### Attempt ${i + 1}\n\nPath: ${a.path}\nParameter: ${a.param_name}\nPayload: ${JSON.stringify(a.param_value)}\nHTTP status: ${a.status}\nOutcome: ${a.outcome}\nMarker detected: ${a.marker_detected}\nResponse: ${JSON.stringify(a.body)}\n`).join("\n")}\n## Sandbox\n\n${report.lifecycle.sandbox_name}\nDeleted: ${report.lifecycle.sandbox_deleted}\nDuration: ${report.lifecycle.wall_clock_s}s\n\n## Suggested next steps (not a verified fix)\n\n${report.explanation?.remediation?.join("\n") || "Review the evidence before choosing a remediation."}\n\nInvestigation: ${report.investigation_id}\nGenerated: ${report.generated_at}\n`;
}
export async function reportPdf(report: Report) {
  const { PDFDocument, StandardFonts, rgb } = await import("pdf-lib");
  const pdf = await PDFDocument.create();
  pdf.setTitle(`Cairn — ${report.investigation_id}`);
  const font = await pdf.embedFont(StandardFonts.Helvetica),
    bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  let page = pdf.addPage([595, 842]),
    y = 740,
    index = 1;
  function header() {
    page.drawText("CAIRN", {
      x: 48,
      y: 790,
      size: 22,
      font: bold,
      color: rgb(0.76, 0.14, 0.09),
    });
    page.drawText(`Investigation evidence / ${index}`, {
      x: 330,
      y: 795,
      size: 10,
      font,
      color: rgb(0.25, 0.28, 0.27),
    });
    page.drawLine({
      start: { x: 48, y: 772 },
      end: { x: 547, y: 772 },
      thickness: 1,
      color: rgb(0.8, 0.82, 0.8),
    });
  }
  header();
  const text =
    reportMarkdown(report) +
    "\nPDF uses a basic character set. Download JSON or Markdown for exact original Unicode evidence.";
  for (const raw of text.split("\n")) {
    const heading = raw.startsWith("#"),
      line = raw.replace(/^#+ /, "").replace(/[^\x20-\x7E]/g, "?");
    const words = line.split(/(\s+)/);
    let current = "";
    const draw = (value: string) => {
      if (y < 55) {
        page = pdf.addPage([595, 842]);
        index++;
        y = 740;
        header();
      }
      page.drawText(value, {
        x: 48,
        y,
        size: heading ? 12 : 10,
        font: heading ? bold : font,
        color: rgb(0.1, 0.14, 0.12),
      });
      y -= heading ? 20 : 15;
    };
    for (const word of words) {
      for (let offset = 0; offset < word.length; offset += 65) {
        const part = word.slice(offset, offset + 65);
        if (font.widthOfTextAtSize(current + part, heading ? 12 : 10) > 490) {
          draw(current);
          current = "";
        }
        current += part;
      }
    }
    draw(current);
    if (heading) y -= 4;
  }
  return pdf.save();
}
