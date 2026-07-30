# Changelog

All notable changes are documented here. The project follows semantic
versioning for released behavior and manifest compatibility.

## 0.2.0

- Reconstructed course, module, lesson, and lecture hierarchy explicitly.
- Added ordered, collision-resistant transcript paths with stable video IDs.
- Added JSON and CSV manifests with download status and course metadata.
- Added interruption-safe reporting and recoverable stale-file archiving.
- Added scoped language/format manifests so TXT and SRT outputs can coexist.
- Prevented Coursera cookies from being forwarded to external subtitle hosts.
- Added subtitle response validation, path containment checks, and atomic writes.
- Separated orchestration, domain models, reporting, presentation, and storage.
- Added automated tests, CI, architecture documentation, and contributor guidance.

## 0.1.4

- Original bulk transcript downloader and interactive CLI behavior.
