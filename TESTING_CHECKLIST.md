# AIBuildCare — 20-Point Test Checklist

Legend: [A] = I can verify automatically · [P] = needs your phone/provider ·
[R] = needs Render restart · [X] = feature not built yet

| # | Test | Who | Pass criteria |
|--|------|-----|---------------|
| 1 | WhatsApp text only (Hindi) | A | ticket created, ack in Hindi |
| 2 | WhatsApp text + photo | A | photo→R2, Haiku vision reads it, severity set |
| 3 | WhatsApp audio (Hindi voice note) | P/X | needs Whisper host + your phone |
| 4 | Email + attachment | P | SendGrid inbound not provisioned |
| 5 | SMS | P | Twilio SMS number not provisioned |
| 6 | Google Form submission | A | `/webhooks/forms` → ticket |
| 7 | Dashboard manual entry | A | POST /complaints → ticket |
| 8 | Login → complaints from all channels | A | list shows multi-channel |
| 9 | Assign → contractor WhatsApp | X | notify-on-assign not implemented |
| 10 | Status received→…→resolved | A | each transition persists |
| 11 | Image gallery on detail | A | media_urls render |
| 12 | Hinglish → Hinglish reply | A | detected_language=hinglish |
| 13 | Marathi → Marathi reply | A | detected_language=marathi |
| 14 | Multiple images one complaint | A | all stored/returned |
| 15 | Filter status/category/priority | A | filtered results |
| 16 | Search by unit number | A | finds it |
| 17 | Restart backend → data persists | A | Supabase row survives reconnect |
| 18 | Real-time dashboard update | A | WS broadcast on create |
| 19 | Contractor performance stats | X | endpoint not built |
| 20 | Rate complaint after resolve | X | endpoint/UI not built |
