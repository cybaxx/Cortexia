import { jsPDF } from 'jspdf';
import type { PropagationReport } from '@/lib/propagationReport';

export function exportPropagationPdf(params: {
  title: string;
  subtitle: string;
  report: PropagationReport;
  memoLabel: 'A' | 'B';
}) {
  const { title, subtitle, report, memoLabel } = params;
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 16;
  let y = 18;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(30, 41, 59);
  doc.text('Cortexia — Propagation Report', margin, y);
  y += 7;
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(71, 85, 105);
  doc.text(title, margin, y);
  y += 5;
  doc.setFontSize(8);
  doc.text(subtitle, margin, y);
  y += 6;
  doc.text(`Memo ${memoLabel} run · ${new Date().toLocaleString()}`, margin, y);
  y += 12;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.text('Reach & adoption', margin, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  const bench =
    report.benchmarkComparison === 'above'
      ? 'above'
      : report.benchmarkComparison === 'below'
        ? 'below'
        : 'in line with';
  doc.text(
    `Overall reach: ${report.reachPct}% of the synthetic population surface. Belief adoption: ${report.adoptionRate}% (${bench} the ${report.benchmark}% reference).`,
    margin,
    y,
    { maxWidth: pageW - 2 * margin },
  );
  y += 16;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.text('Rejection concentration', margin, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  for (const h of report.rejectionHotspots) {
    doc.text(
      `• ${h.label} (${h.area}) — ~${Math.round(h.share * 100)}% of modelled rejections`,
      margin,
      y,
      { maxWidth: pageW - 2 * margin },
    );
    y += 6;
  }
  y += 4;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.text('Why resistance clusters', margin, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  const whyLines = doc.splitTextToSize(report.whyResistance, pageW - 2 * margin);
  doc.text(whyLines, margin, y);
  y += whyLines.length * 4.2 + 6;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.text('Recommendations', margin, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  for (const line of report.recommendations) {
    const t = doc.splitTextToSize(`• ${line}`, pageW - 2 * margin);
    doc.text(t, margin, y);
    y += t.length * 4.2 + 1;
  }
  y += 4;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.text('Predicted outcome (with fixes)', margin, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  const pred = doc.splitTextToSize(report.predictedOutcome, pageW - 2 * margin);
  doc.text(pred, margin, y);

  doc.save('cortexia-propagation-report.pdf');
}
