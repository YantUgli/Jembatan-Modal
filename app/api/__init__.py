"""Adaptor kanal HTTP — FastAPI di atas orchestrator.

Ini **satu adaptor** dari lapisan KANAL, bukan intinya: ia menerjemahkan HTTP ↔
`PesanKeluar`. Adaptor lain (WhatsApp) akan berbagi orchestrator & kontrak yang
sama tanpa menyentuh modul ini.
"""
