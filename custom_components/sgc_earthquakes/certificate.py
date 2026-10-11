"""Checks the SGC server's certificate, which arrives without the one linking it to a root."""

from __future__ import annotations

from functools import cache
from os import environ
import ssl
from typing import Final

import certifi

# The SGC server (seen in October 2026) sends only its own certificate and
# leaves out this one, which links it to DigiCert's root. Browsers and antivirus
# programs fetch the missing link themselves. Python does not, so every download
# failed, and with no IPv6 route aiohttp reports that as "Network unreachable".
# Adding it only fills the gap: the chain must still end at a trusted root.
# Valid until 16 March 2032, and unused once the server sends it again.
VEROKEY_VERIFIED_BUSINESS_G2: Final = """\
-----BEGIN CERTIFICATE-----
MIIFNTCCBB2gAwIBAgIQAqN9dVvbCvNwvMrBdxUWujANBgkqhkiG9w0BAQwFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH
MjAeFw0yMjAzMTcwMDAwMDBaFw0zMjAzMTYyMzU5NTlaMEYxCzAJBgNVBAYTAkFV
MRAwDgYDVQQKEwdWZXJva2V5MSUwIwYDVQQDExxWZXJva2V5IFZlcmlmaWVkIEJ1
c2luZXNzIEcyMIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAoc1NaPMO
OH2LT7qbByD/qOLuCsGzrsg0BJIYk/Tk3sQnzLSL3TvW9HIhohERHD578kFRe7FT
7LTK36couuVLxcH+psulmtu2is6sd0xzZr8b8MvJ2yCom9vTinQHLQLr8pyfEVFB
nOt21igjzNfwDCY2zGPmOznPHNGY2fbmODgbodpvmpcNYYMJWwsS0G/T3PCDpgHU
r7uYrKnpUI6bcfMLoxMhlK4FBS5lds3TfnMlrP5B+Ws8l1toeagnWYm/bzIS0Yi3
NxNh17ghpC++lqPEmeiVQGp4KtBwc2kOkXNlmKi+cu2rtCo0BtgKH5cjCQAlnAWF
eHX3rLwc6STYd+w15BnNLXbde3SLwsT5v5AkWMcCFjE9MwznxSY2LHKgZvj/CXKA
F0aPt7MXI6E0i3OIC1spg4SBU+N+XUgvMjgWyt9392d7xDWY8cvX8fQOOuKX8oh2
Gt5DGNW5lwlurzIkMSUOWWbWf6MnRvO4doywRzWqDZHtohiv1j0oyrH9AgMBAAGj
ggGCMIIBfjASBgNVHRMBAf8ECDAGAQH/AgEAMB0GA1UdDgQWBBT0Mzw6yJtwGnCk
lmTmv0JS1f7/0jAfBgNVHSMEGDAWgBROIlQgGJXm427mD/r6uRLtBhePOTAOBgNV
HQ8BAf8EBAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwEGCCsGAQUFBwMCMHYGCCsG
AQUFBwEBBGowaDAkBggrBgEFBQcwAYYYaHR0cDovL29jc3AuZGlnaWNlcnQuY29t
MEAGCCsGAQUFBzAChjRodHRwOi8vY2FjZXJ0cy5kaWdpY2VydC5jb20vRGlnaUNl
cnRHbG9iYWxSb290RzIuY3J0MEIGA1UdHwQ7MDkwN6A1oDOGMWh0dHA6Ly9jcmwz
LmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydEdsb2JhbFJvb3RHMi5jcmwwPQYDVR0gBDYw
NDALBglghkgBhv1sAgEwBwYFZ4EMAQEwCAYGZ4EMAQIBMAgGBmeBDAECAjAIBgZn
gQwBAgMwDQYJKoZIhvcNAQEMBQADggEBAJBQbb8KlJII+B3nciahlhR0sXKeWd7U
ggM8XCOr0Mq3v9LJl7uPKsB0ccpfRwpuNOMdpP7y6YKGjtCSgT4g/KOZZvGTDd/E
FJilO/zH4+450jplHk3pc239017A4iOUsxdUBx/mVpi62eYgrzKHjlMBr2sUgqO5
D3X12njcJx3TUzFkP34Z0pHoT13jCR4YdZ4D1RC6fxm8AbS7SLoMBtyZC8tVHCq5
HloWYSOMEDbhghLQNAvoUZud1NfkZjQI/ykTVhbEhooN19fGQbshNT7lGtUxg+di
UAQhZL22EphGMPTyoC9w8OlcTr9x/33laOY1Dh3CQroSkJXBMPSN7tY=
-----END CERTIFICATE-----
"""


@cache
def sgc_ssl_context() -> ssl.SSLContext:
	"""The roots Home Assistant trusts plus the missing link. Reads files, so not in the event loop."""
	context = ssl.create_default_context(
		cafile=environ.get("REQUESTS_CA_BUNDLE", certifi.where())
	)
	context.load_verify_locations(cadata=VEROKEY_VERIFIED_BUSINESS_G2)
	# Python accepts any stored certificate as the end of the chain. This one
	# must lead on to the DigiCert root like any other link.
	context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
	return context
