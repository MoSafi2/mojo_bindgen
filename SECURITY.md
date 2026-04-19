# Security

## Supported versions

Security fixes are applied to the latest minor release line when practical. Use the newest tagged release.

## Reporting a vulnerability

Please report security issues **privately** to the maintainers rather than using public GitHub issues.

- **Email:** [mohamed.mabrouk@rwth-aachen.de](mailto:mohamed.mabrouk@rwth-aachen.de)

Include a short description, steps to reproduce, and impact if known. You should receive an acknowledgment within a few business days.

This project processes untrusted C headers through libclang; treat header paths and compiler flags as part of your trust boundary when integrating the tool.
