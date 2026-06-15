#!/usr/bin/env python3
"""Generate a comprehensive PDF report from a Cortexia simulation run.

Usage:
    source .venv/bin/activate
    python scripts/export_report.py <run_id> [--output report.pdf]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2 not installed. Run: pip install fpdf2", file=sys.stderr)
    sys.exit(1)

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.pipeline_store import fetch_case_run


def _sanitize(text: str) -> str:
    """Replace Unicode chars that fpdf2 built-in fonts cannot render."""
    return (
        text.replace("\u2192", "->")
        .replace("\u2190", "<-")
        .replace("\u2194", "<->")
        .replace("\u2013", "--")
        .replace("\u2014", "---")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u00a0", " ")
    )


class CortexiaPDF(FPDF):
    """Dark-themed Cortexia PDF report generator."""

    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.set_auto_page_break(True, 14)
        self._deep = (11, 15, 25)
        self._surface = (20, 27, 39)
        self._elevated = (31, 41, 55)
        self._text = (243, 244, 246)
        self._muted = (156, 163, 175)
        self._accent1 = (188, 231, 219)
        self._accent2 = (160, 214, 255)
        self._accent3 = (255, 191, 166)
        self._w = 210
        self._h = 297

    # ── layout helpers ──────────────────────────────────────────

    def _page(self, title: str, eyebrow: str, accent: tuple):
        self.add_page()
        self.set_fill_color(*self._deep)
        self.rect(0, 0, self._w, self._h, "F")
        self.set_fill_color(*accent)
        self.rect(10, 10, 40, 6, "F")
        self.set_text_color(*self._deep)
        self.set_font("Helvetica", "B", 7)
        self.text(12, 14, eyebrow.upper())
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 22)
        self.text(10, 28, _sanitize(title))

    def _card(self, x, y, w, h, color=None):
        self.set_fill_color(*(color or self._surface))
        self.rect(x, y, w, h, "F")

    def _label(self, x, y, w, label, value):
        self._card(x, y, w, 18, self._surface)
        self.set_text_color(*self._muted)
        self.set_font("Helvetica", "B", 7)
        self.text(x + 4, y + 6, label.upper())
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 14)
        self.text(x + 4, y + 14, str(value))

    def _text_block(self, text, x, y, w, size=9, color=None):
        """Draw a text block at the given position. Returns y after the block."""
        self.set_xy(x, y)
        self.set_text_color(*(color or self._text))
        self.set_font("Helvetica", "", size)
        self.multi_cell(w, size * 0.46, _sanitize(str(text)), 0, "L")
        return self.get_y()

    def _chip(self, text, x, y, color=None):
        c = color or self._accent2
        self.set_fill_color(*c)
        w = max(18, len(text) * 2 + 8)
        self.rect(x, y, w, 7, "F")
        self.set_text_color(*self._deep)
        self.set_font("Helvetica", "B", 7)
        self.text(x + 3, y + 5, text)

    def _section_title(self, y, title):
        self.set_text_color(*self._accent1)
        self.set_font("Helvetica", "B", 11)
        self.text(10, y, _sanitize(title))
        self.set_draw_color(*self._accent1)
        self.line(10, y + 3, self._w - 10, y + 3)
        return y + 6  # return y after the section title

    def _ensure_space(self, needed_mm: int, y: float) -> float:
        """If there's not enough space left on the page, add a new page and return new y."""
        if y + needed_mm > self._h - 14:
            self.add_page()
            self.set_fill_color(*self._deep)
            self.rect(0, 0, self._w, self._h, "F")
            return 38
        return y

    # ── report pages ────────────────────────────────────────────

    def cover_page(self, response: dict):
        cs = response.get("case_summary", {})
        sm = response.get("spread_model", {})
        tm = response.get("tribe_meta", {})
        summary = response.get("summary", {})

        self._page(_sanitize(cs.get("title", "Cortexia Report")), "Cortexia briefing", self._accent2)

        y = 38
        self._card(10, y, self._w - 20, 28)
        self.set_text_color(*self._muted)
        self.set_font("Helvetica", "B", 8)
        self.text(14, y + 8, "CASE GOAL")
        y = self._text_block(cs.get("goal", ""), 14, y + 14, self._w - 24, 10)
        y += 6

        y = self._ensure_space(22, y)
        self._label(10, y, 45, "Risk Score", sm.get("risk_score", "?"))
        self._label(59, y, 45, "Adoption", f'{sm.get("belief_adoption_rate", "?")}%')
        self._label(108, y, 45, "Reached", f'{sm.get("population_reached", "?")}%')
        self._label(157, y, 45, "Risk", sm.get("spread_risk", "?"))
        y += 24

        y = self._ensure_space(44, y)
        self._card(10, y, self._w - 20, 40, self._elevated)
        self.set_text_color(*self._accent1)
        self.set_font("Helvetica", "B", 9)
        self.text(14, y + 10, "KEY FINDING")
        self._text_block(cs.get("key_finding", ""), 14, y + 17, self._w - 24, 11)
        y += 48

        # Summary counts
        y = self._ensure_space(36, y)
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 36)
        self.text(30, y + 5, str(summary.get("adopted", "?")))
        self.set_text_color(*self._accent2)
        self.set_font("Helvetica", "", 9)
        self.text(30, y + 14, "ADOPTED")
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 36)
        self.text(85, y + 5, str(summary.get("rejected", "?")))
        self.set_text_color(*self._accent3)
        self.set_font("Helvetica", "", 9)
        self.text(85, y + 14, "REJECTED")
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 36)
        self.text(140, y + 5, str(summary.get("neutral", "?")))
        self.set_text_color(*self._muted)
        self.set_font("Helvetica", "", 9)
        self.text(140, y + 14, "NEUTRAL")
        y += 24

        # TRIBE info
        if tm.get("provider"):
            y = self._ensure_space(26, y)
            self._card(10, y, self._w - 20, 22)
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 8)
            self.text(14, y + 7, f"Neural model: {tm.get('provider')} / {tm.get('model_id')}")
            sconf = tm.get("signal_confidence", 0)
            self.text(14, y + 15, f"Signal confidence: {sconf:.2f} | Dominant ROI: {tm.get('dominant_roi', '?')}")

    def evidence_page(self, response: dict):
        et = response.get("evidence_trace", {})
        self._page("Evidence & Claims", "Research input", self._accent1)

        y = 38
        self._card(10, y, self._w - 20, 34)
        self.set_text_color(*self._accent1)
        self.set_font("Helvetica", "B", 9)
        self.text(14, y + 9, "ANALYSIS TEXT")
        y = self._text_block(et.get("analysis_text", ""), 14, y + 15, self._w - 24, 9, self._text)
        y += 4

        for claim in et.get("claims", [])[:4]:
            y = self._ensure_space(24, y)
            self._card(10, y, self._w - 20, 20, self._elevated)
            risk_color = self._accent3 if claim.get("risk") == "High" else self._accent2
            self.set_text_color(*risk_color)
            self.set_font("Helvetica", "B", 7)
            self.text(14, y + 6, f'{claim.get("risk", "?").upper()} CLAIM')
            y = self._text_block(claim.get("text", ""), 14, y + 13, self._w - 24, 8)
            y += 4

        if et.get("themes"):
            y = self._ensure_space(22, y)
            self._card(10, y, self._w - 20, 18)
            self.set_text_color(*self._accent2)
            self.set_font("Helvetica", "B", 8)
            self.text(14, y + 6, "THEMES")
            self._text_block(" · ".join(et["themes"]), 14, y + 13, self._w - 24, 9)

    def spread_page(self, response: dict):
        sm = response.get("spread_model", {})
        self._page("Spread Model", "Propagation overview", self._accent3)

        y = 38
        self._label(10, y, 30, "Risk", str(sm.get("risk_score", "?")))
        self._label(44, y, 35, "Adopt", f'{sm.get("belief_adoption_rate", "?")}%')
        self._label(83, y, 40, "Reach", f'{sm.get("population_reached", "?")}%')
        self._label(127, y, 35, "Cog", f'{sm.get("avg_cognitive_load", 0):.2f}')
        self._label(166, y, 35, "Def", f'{sm.get("avg_defensive_activation", 0):.2f}')
        y += 28

        y = self._ensure_space(32, y)
        self._card(10, y, self._w - 20, 28)
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 9)
        self.text(14, y + 9, "NETWORK SUMMARY")
        y = self._text_block(sm.get("network_summary", ""), 14, y + 16, self._w - 24, 10, self._muted)
        y += 6

        for seg in sm.get("high_risk_segments", [])[:4]:
            y = self._ensure_space(26, y)
            self._card(10, y, self._w - 20, 22, self._elevated)
            self.set_text_color(*self._text)
            self.set_font("Helvetica", "B", 9)
            self.text(14, y + 7, _sanitize(seg.get("label", "")))
            risk = seg.get("risk_level", "")
            rc = self._accent3 if risk == "High" else self._accent2
            self.set_text_color(*rc)
            self.set_font("Helvetica", "B", 7)
            self.text(self._w - 44, y + 7, risk.upper())
            y = self._text_block(seg.get("why_vulnerable", ""), 14, y + 14, self._w - 38, 8, self._muted)
            y += 4

        # Hotspots
        hotspots = sm.get("hotspots", [])
        if hotspots:
            y = self._ensure_space(10, y)
            y = self._section_title(y + 4, "HOTSPOTS")
            for h in hotspots[:5]:
                y = self._ensure_space(20, y)
                self._card(10, y, self._w - 20, 16, self._elevated)
                self.set_text_color(*self._text)
                self.set_font("Helvetica", "B", 8)
                self.text(14, y + 5, _sanitize(h.get("label", "?")))
                self.set_text_color(*self._muted)
                self.set_font("Helvetica", "", 7)
                self.text(14, y + 11, f'{h.get("area", "?")} · share {h.get("share", 0):.0%} · state {h.get("state", "?")}')
                y += 19

    def agent_page(self, response: dict, top_n: int = 6):
        agents = sorted(
            response.get("agents", []),
            key=lambda a: abs(a.get("k2_decision_confidence", 0.5) - 0.5),
            reverse=True,
        )[:top_n]

        self._page("Agent Profiles", "Population analysis", self._accent2)
        y = 38

        for idx, agent in enumerate(agents):
            card_h = 68
            y = self._ensure_space(card_h + 10, y)
            state = agent.get("belief_state", "neutral")
            state_color = self._accent2 if state == "adopted" else self._accent3 if state == "rejected" else self._muted

            self._card(10, y, self._w - 20, card_h, self._elevated)

            # Header
            self.set_text_color(*self._text)
            self.set_font("Helvetica", "B", 11)
            self.text(14, y + 7, _sanitize(agent.get("name", "?")))
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 8)
            self.text(14, y + 13, agent.get("role", "?"))

            # State badge
            self.set_fill_color(*state_color)
            self.rect(self._w - 52, y + 4, 38, 10, "F")
            self.set_text_color(*self._deep)
            self.set_font("Helvetica", "B", 8)
            self.text(self._w - 48, y + 10.5, state.upper())
            conf = agent.get("k2_decision_confidence", 0)
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 7)
            self.text(self._w - 48, y + 14, f'conf {conf:.2f}')

            # BSV metrics
            bsv = agent.get("tribe_neurological_metrics", {})
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 7)
            self.text(14, y + 20, f'Cog {bsv.get("cognitive_load", 0):.2f}  Emo {bsv.get("emotional_friction", 0):.2f}  Def {bsv.get("defensive_activation", 0):.2f}  WM {bsv.get("working_memory_strain", 0):.2f}')

            # Reasoning trace (one line)
            traces = agent.get("k2_reasoning_trace", [])
            if traces:
                self._text_block(traces[0], 14, y + 27, self._w - 32, 7, self._text)

            # Intervention hint
            insight = agent.get("agent_insight", {})
            if insight.get("best_intervention"):
                self.set_text_color(*self._accent2)
                self.set_font("Helvetica", "I", 7)
                self.text(14, y + 62, _sanitize(f'Intervention: {insight["best_intervention"][:140]}'))

            y += card_h + 6

    def tribe_page(self, response: dict):
        tm = response.get("tribe_meta", {})
        self._page("Neural State", "TRIBE readout", self._accent1)

        y = 38
        comps = tm.get("composites", {})
        if comps:
            self._card(10, y, self._w - 20, 44)
            self.set_text_color(*self._accent1)
            self.set_font("Helvetica", "B", 9)
            self.text(14, y + 9, "COMPOSITE SCORES")
            comp_y = y + 16
            for i, (key, val) in enumerate(comps.items()):
                col = i % 3
                row = i // 3
                cx = 14 + col * 64
                cy = comp_y + row * 12
                self.set_text_color(*self._muted)
                self.set_font("Helvetica", "", 7)
                self.text(cx, cy, key.replace("_", " ").title())
                self.set_text_color(*self._text)
                self.set_font("Helvetica", "B", 10)
                self.text(cx, cy + 5, f"{val:.2f}")
            y += 50

        # Formatted state
        formatted = tm.get("formatted_state", "")
        if formatted:
            y = self._ensure_space(60, y)
            self._card(10, y, self._w - 20, 100)
            self.set_text_color(*self._accent1)
            self.set_font("Helvetica", "B", 9)
            self.text(14, y + 9, "NEURAL STATE NARRATIVE")
            self.set_text_color(*self._text)
            self.set_font("Courier", "", 6)
            line_y = y + 16
            for line in formatted.split("\n")[:20]:
                if line_y > self._h - 20:
                    break
                self.text(14, line_y, _sanitize(line)[:120])
                line_y += 4

        # Surface summary
        ss = tm.get("surface_summary", {})
        if ss.get("narrative_flags"):
            y = self._ensure_space(24, line_y + 6)
            self._card(10, y, self._w - 20, 20)
            self.set_text_color(*self._accent2)
            self.set_font("Helvetica", "B", 8)
            self.text(14, y + 6, "NARRATIVE FLAGS")
            self._text_block(" · ".join(ss["narrative_flags"]), 14, y + 13, self._w - 24, 8)

    def mechanisms_page(self, response: dict):
        mech = response.get("mechanisms", {})
        ip = response.get("intervention_playbook", [])
        self._page("Mechanisms & Interventions", "Action playbook", self._accent2)

        y = 38
        self._card(10, y, self._w - 20, 24)
        self.set_text_color(*self._accent2)
        self.set_font("Helvetica", "B", 9)
        self.text(14, y + 9, "MECHANISM SUMMARY")
        y = self._text_block(mech.get("mechanism_summary", ""), 14, y + 16, self._w - 24, 10)
        y += 4

        drivers = mech.get("dominant_cognitive_drivers", [])
        for d in drivers[:4]:
            y = self._ensure_space(18, y)
            self._card(10, y, self._w - 20, 15, self._elevated)
            self.set_text_color(*self._text)
            self.set_font("Helvetica", "B", 8)
            self.text(14, y + 5, _sanitize(d.get("description", "")))
            self.set_text_color(*self._accent2)
            self.set_font("Helvetica", "B", 7)
            self.text(self._w - 40, y + 5, f'{d.get("share", 0):.0%}')
            y += 18

        y = self._ensure_space(10, y)
        y = self._section_title(y + 4, "INTERVENTIONS")
        for item in ip[:3]:
            y = self._ensure_space(54, y)
            self._card(10, y, self._w - 20, 50, self._elevated)
            self.set_text_color(*self._text)
            self.set_font("Helvetica", "B", 10)
            self.text(14, y + 7, _sanitize(item.get("title", "")))
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 7)
            self.text(14, y + 14, f'Audience: {item.get("target_audience", "")}')
            self.text(14, y + 20, f'Messenger: {item.get("recommended_messenger", "")}  ·  Channel: {item.get("recommended_channel", "")}')
            self.text(14, y + 26, f'Time: {item.get("time_horizon", "")}  ·  Effect: {item.get("expected_effect", "")}')
            self._text_block(item.get("message_strategy", ""), 14, y + 34, self._w - 24, 8, self._text)
            y += 55

    def cyber_page(self, response: dict):
        ag = response.get("agents", [])
        self._page("Cyber Exposure", "Digital propagation", self._accent3)

        cyber_entries = sum(
            1 for a in ag for e in (a.get("round_history") or []) if e.get("source_channel") == "cyber")
        phys_entries = sum(
            1 for a in ag for e in (a.get("round_history") or []) if e.get("source_channel") == "physical")

        y = 38
        self._card(10, y, self._w - 20, 32)
        self.set_text_color(*self._accent3)
        self.set_font("Helvetica", "B", 9)
        self.text(14, y + 9, "CYBER PROPAGATION SUMMARY")
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 28)
        self.text(30, y + 27, str(cyber_entries))
        self.set_text_color(*self._muted)
        self.set_font("Helvetica", "", 8)
        self.text(30, y + 31, "cyber exposures")
        self.set_text_color(*self._text)
        self.set_font("Helvetica", "B", 28)
        self.text(110, y + 27, str(phys_entries))
        self.set_text_color(*self._muted)
        self.set_font("Helvetica", "", 8)
        self.text(110, y + 31, "physical exchanges")
        y += 40

        for a in sorted(ag, key=lambda x: sum(1 for e in (x.get("round_history") or []) if e.get("source_channel") == "cyber"), reverse=True)[:8]:
            ce = [e for e in (a.get("round_history") or []) if e.get("source_channel") == "cyber"]
            if not ce:
                continue
            y = self._ensure_space(24, y)
            self._card(10, y, self._w - 20, 20, self._elevated)
            self.set_text_color(*self._text)
            self.set_font("Helvetica", "B", 8)
            self.text(14, y + 5, _sanitize(f'{a.get("name")} ({a.get("role")})'))
            self.set_text_color(*self._muted)
            self.set_font("Helvetica", "", 7)
            self.text(14, y + 11, _sanitize(f'Exposed by: {ce[0].get("trigger", "")}') if ce else "")
            self.text(14, y + 16, _sanitize(f'Message: {ce[0].get("post", "")[:80]}') if ce else "")
            y += 24

    def build(self, record: dict, output_path: str):
        response = record.get("response") or record

        self.cover_page(response)
        self.evidence_page(response)
        self.spread_page(response)
        self.agent_page(response)
        self.tribe_page(response)
        self.mechanisms_page(response)
        self.cyber_page(response)

        self.output(output_path)
        print(f"PDF report saved to {output_path}")
        print(f"  Pages: {self.page_no()}")
        print(f"  Run: #{record.get('id')} — {record.get('domain')} / {record.get('city_id')}")


def main():
    parser = argparse.ArgumentParser(description="Generate Cortexia simulation PDF report")
    parser.add_argument("run_id", type=int, help="Simulation run ID to export")
    parser.add_argument("--output", "-o", default=None, help="Output PDF path")
    args = parser.parse_args()

    record = fetch_case_run(args.run_id)
    if record is None:
        print(f"Run #{args.run_id} not found.", file=sys.stderr)
        sys.exit(1)

    output = args.output or f"cortexia-run-{args.run_id}.pdf"
    pdf = CortexiaPDF()
    pdf.build(record, output)
    if output == "-":
        import io
        buf = io.BytesIO()
        pdf.output(buf)
        sys.stdout.buffer.write(buf.getvalue())


if __name__ == "__main__":
    main()
