"""Forms that can advance an accounting report card."""

CORE_REPORT_FORMS = frozenset({
    "10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A",
    "40-F", "40-F/A", "6-K", "6-K/A",
})
MATERIAL_EVENT_FORMS = frozenset({
    "8-K", "8-K/A", "NT 10-K", "NT 10-Q", "UPLOAD", "CORRESP",
})
REPORT_CARD_FORMS = CORE_REPORT_FORMS | MATERIAL_EVENT_FORMS
