---
title: Legal RAG (live)
emoji: ⚖️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

Live demo of an evidence-grounded legal research prototype for the GDPR and the Italian Privacy
Code. Every statement quotes the provision it rests on; the system says what it could not
establish, or abstains. Research mode: the provisions have not been reviewed by a person yet.

- **Your question is sent to Anthropic's API** for analysis, generation and verification. Do not
  include personal data.
- **Limits:** 3 questions per visitor per hour and 10 per day, in at most 300 characters; 40
  questions and a fixed API budget per day in total. They may reset when the Space restarts.
- **Saved answers, no model calls:** https://huggingface.co/spaces/SimoneZanetti00/legal-rag-demo
- **Source code:** https://github.com/SimoneZanetti00/legal-rag (MIT). This Space also runs
  PyMuPDF (AGPL-3.0), which the corpus code imports; the complete source is in this Space's files
  and in that public repository.
- **Sources and attribution:** [NOTICE.md](NOTICE.md). The GDPR text is from EUR-Lex (CC BY 4.0).
  The Privacy Code text is an unverified user transcription (Normattiva: testo non autentico e
  gratuito).

Experimental prototype. Not legal advice.
