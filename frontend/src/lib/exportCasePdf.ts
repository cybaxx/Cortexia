import { jsPDF } from 'jspdf';
import type { SimulateResponse } from '@/types/simulation';

const COLORS = {
  deep: [11, 15, 25] as const,
  surface: [20, 27, 39] as const,
  elevated: [31, 41, 55] as const,
  text: [243, 244, 246] as const,
  muted: [156, 163, 175] as const,
  pastel1: [188, 231, 219] as const,
  pastel2: [160, 214, 255] as const,
  pastel3: [255, 191, 166] as const,
};

function setFill(doc: jsPDF, color: readonly number[]) {
  doc.setFillColor(color[0], color[1], color[2]);
}

function setText(doc: jsPDF, color: readonly number[]) {
  doc.setTextColor(color[0], color[1], color[2]);
}

function card(doc: jsPDF, x: number, y: number, w: number, h: number, color = COLORS.surface) {
  setFill(doc, color);
  doc.roundedRect(x, y, w, h, 8, 8, 'F');
}

function addPageFrame(doc: jsPDF, title: string, eyebrow: string, accent: readonly number[]) {
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  setFill(doc, COLORS.deep);
  doc.rect(0, 0, pageW, pageH, 'F');
  setFill(doc, accent);
  doc.roundedRect(14, 12, 46, 7, 3.5, 3.5, 'F');
  setText(doc, COLORS.deep);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.text(eyebrow.toUpperCase(), 18, 16.7);
  setText(doc, COLORS.text);
  doc.setFontSize(24);
  doc.text(title, 14, 33);
}

function textBlock(doc: jsPDF, text: string, x: number, y: number, w: number, size = 11, color = COLORS.text) {
  setText(doc, color);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(size);
  const lines = doc.splitTextToSize(text, w);
  doc.text(lines, x, y);
  return lines.length * (size * 0.42);
}

function labelValue(doc: jsPDF, label: string, value: string, x: number, y: number, w: number) {
  card(doc, x, y, w, 24, COLORS.surface);
  setText(doc, COLORS.muted);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.text(label.toUpperCase(), x + 6, y + 7);
  setText(doc, COLORS.text);
  doc.setFontSize(16);
  doc.text(value, x + 6, y + 17);
}

function chip(doc: jsPDF, text: string, x: number, y: number, color = COLORS.pastel2) {
  setFill(doc, color);
  doc.roundedRect(x, y, Math.max(22, text.length * 2.2 + 8), 8, 4, 4, 'F');
  setText(doc, COLORS.deep);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.text(text, x + 4, y + 5.3);
}

export function exportCasePdf(response: SimulateResponse) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();

  addPageFrame(doc, response.case_summary.title, 'Cortexia briefing', COLORS.pastel2);
  card(doc, 14, 42, pageW - 28, 38, COLORS.surface);
  setText(doc, COLORS.muted);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.text('Case Goal', 20, 51);
  textBlock(doc, response.case_summary.goal, 20, 58, pageW - 40, 12);
  labelValue(doc, 'Spread Risk', response.case_summary.spread_risk, 14, 88, 56);
  labelValue(doc, 'Confidence', `${Math.round(response.case_summary.overall_confidence * 100)}%`, 75, 88, 56);
  labelValue(doc, 'Target Region', response.case_summary.target_region, 136, 88, 60);
  card(doc, 14, 120, pageW - 28, 52, COLORS.elevated);
  setText(doc, COLORS.pastel1);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Key Finding', 20, 131);
  textBlock(doc, response.case_summary.key_finding, 20, 139, pageW - 40, 12);
  setText(doc, COLORS.muted);
  doc.setFontSize(9);
  doc.text(`Recommended next step: ${response.case_summary.recommended_next_step}`, 20, 165);

  doc.addPage();
  addPageFrame(doc, 'Evidence & Claims', 'Research input', COLORS.pastel1);
  card(doc, 14, 42, pageW - 28, 42, COLORS.surface);
  setText(doc, COLORS.pastel1);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Canonical Analysis Text', 20, 52);
  textBlock(doc, response.evidence_trace.analysis_text, 20, 60, pageW - 40, 10, COLORS.text);
  let y = 92;
  for (const claim of response.evidence_trace.claims.slice(0, 3)) {
    card(doc, 14, y, pageW - 28, 24, COLORS.elevated);
    setText(doc, claim.risk === 'High' ? COLORS.pastel3 : COLORS.pastel2);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.text(`${claim.risk.toUpperCase()} CLAIM`, 20, y + 8);
    textBlock(doc, claim.text, 20, y + 15, pageW - 40, 10);
    y += 30;
  }
  card(doc, 14, y, pageW - 28, 28, COLORS.surface);
  setText(doc, COLORS.pastel2);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.text('Themes', 20, y + 9);
  textBlock(doc, response.evidence_trace.themes.join(' · '), 20, y + 17, pageW - 40, 11);

  doc.addPage();
  addPageFrame(doc, 'Spread Model', 'Propagation view', COLORS.pastel3);
  labelValue(doc, 'Risk Score', String(response.spread_model.risk_score), 14, 42, 42);
  labelValue(doc, 'Adoption Rate', `${response.spread_model.belief_adoption_rate}%`, 60, 42, 42);
  labelValue(doc, 'Population Reached', `${response.spread_model.population_reached}%`, 106, 42, 48);
  labelValue(doc, 'Avg Load', response.spread_model.avg_cognitive_load.toFixed(2), 158, 42, 38);
  card(doc, 14, 74, pageW - 28, 34, COLORS.surface);
  setText(doc, COLORS.text);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Network Summary', 20, 84);
  textBlock(doc, response.spread_model.network_summary, 20, 92, pageW - 40, 11, COLORS.muted);
  y = 118;
  for (const segment of response.spread_model.high_risk_segments.slice(0, 4)) {
    card(doc, 14, y, pageW - 28, 26, COLORS.elevated);
    setText(doc, COLORS.text);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(segment.label, 20, y + 9);
    setText(doc, segment.risk_level === 'High' ? COLORS.pastel3 : COLORS.pastel2);
    doc.setFontSize(8);
    doc.text(segment.risk_level.toUpperCase(), pageW - 44, y + 9);
    textBlock(doc, segment.why_vulnerable, 20, y + 17, pageW - 40, 9, COLORS.muted);
    y += 31;
  }

  doc.addPage();
  addPageFrame(doc, 'Spread Pathways', 'Propagation patterns', COLORS.pastel1);
  card(doc, 14, 42, pageW - 28, 34, COLORS.surface);
  setText(doc, COLORS.pastel1);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Network Storyline', 20, 52);
  textBlock(doc, response.spread_model.network_summary, 20, 60, pageW - 40, 10, COLORS.text);
  y = 86;
  for (const pathway of response.spread_model.belief_adoption_pathways.slice(0, 4)) {
    card(doc, 14, y, pageW - 28, 26, COLORS.elevated);
    chip(doc, `${pathway.share}% share`, pageW - 54, y + 6, pathway.id === 'defensive_reactance' ? COLORS.pastel3 : COLORS.pastel2);
    setText(doc, COLORS.text);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(pathway.label, 20, y + 10);
    textBlock(doc, pathway.description, 20, y + 18, pageW - 48, 9, COLORS.muted);
    y += 31;
  }

  doc.addPage();
  addPageFrame(doc, 'Mechanisms & Interventions', 'Action playbook', COLORS.pastel2);
  card(doc, 14, 42, pageW - 28, 30, COLORS.surface);
  setText(doc, COLORS.pastel2);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Mechanism Summary', 20, 52);
  textBlock(doc, response.mechanisms.mechanism_summary, 20, 60, pageW - 40, 11);
  y = 82;
  for (const item of response.intervention_playbook.slice(0, 3)) {
    card(doc, 14, y, pageW - 28, 56, COLORS.elevated);
    setText(doc, COLORS.text);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(11);
    doc.text(item.title, 20, y + 10);
    setText(doc, COLORS.muted);
    doc.setFontSize(8);
    doc.text(`Audience: ${item.target_audience}`, 20, y + 18);
    doc.text(`Messenger: ${item.recommended_messenger}`, 20, y + 24);
    doc.text(`Channel: ${item.recommended_channel}`, 20, y + 30);
    doc.text(`Time horizon: ${item.time_horizon}`, 20, y + 36);
    textBlock(doc, item.message_strategy, 20, y + 44, pageW - 40, 9, COLORS.text);
    y += 62;
  }

  doc.addPage();
  addPageFrame(doc, 'Evidence Trace', 'Audit trail', COLORS.pastel3);
  card(doc, 14, 42, pageW - 28, 28, COLORS.surface);
  setText(doc, COLORS.pastel3);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.text('Source Provenance', 20, 52);
  textBlock(
    doc,
    `Source type: ${response.evidence_trace.provenance.source_type}. Transcript used: ${response.evidence_trace.provenance.transcript_used ? 'Yes' : 'No'}. Analysis source: ${response.evidence_trace.provenance.analysis_text_source}.`,
    20,
    60,
    pageW - 40,
    10,
    COLORS.text,
  );
  y = 80;
  for (const item of response.intervention_playbook.slice(0, 2)) {
    card(doc, 14, y, pageW - 28, 44, COLORS.elevated);
    setText(doc, COLORS.text);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(item.title, 20, y + 10);
    setText(doc, COLORS.muted);
    doc.setFontSize(8);
    doc.text(`Mechanism: ${item.mechanism_addressed}`, 20, y + 18);
    doc.text(`Confidence: ${Math.round(item.confidence * 100)}%`, pageW - 46, y + 18);
    textBlock(doc, `Supporting evidence: ${item.supporting_evidence.join(' · ')}`, 20, y + 28, pageW - 40, 9, COLORS.text);
    y += 50;
  }

  doc.save('cortexia-case-brief.pdf');
}
