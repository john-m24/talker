# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report (suspected) security vulnerabilities to **john@bondstudios.us**. You will receive a response within 48 hours. If the issue is confirmed, we will release a patch as soon as possible depending on complexity but historically within a few days.

### Security Considerations

This project interacts with:
- **macOS system permissions**: Requires Accessibility and Microphone permissions
- **Local LLM endpoints**: Communicates with local AI services
- **AppleScript**: Executes system commands to control windows
- **Microphone input**: Processes audio data locally

### Security Best Practices

When using this software:

1. **Review presets.json**: Ensure preset configurations don't contain sensitive information
2. **Local LLM only**: The project is designed to work with local LLM endpoints. If you modify it to use cloud services, ensure proper authentication
3. **Permissions**: Only grant necessary macOS permissions (Accessibility, Microphone)
4. **Network**: If using a network-accessible LLM endpoint, ensure it's on a trusted network or properly secured
5. **Code review**: Review any custom modifications before running

### Known Security Limitations

- The project uses AppleScript which has broad system access when granted Accessibility permissions
- Microphone access is required for voice input
- No built-in authentication for LLM endpoints (assumes local/trusted network)

## Disclosure Policy

When we receive a security bug report, we will assign it to a primary handler. This person will coordinate the fix and release process, involving the following steps:

1. Confirm the problem and determine the affected versions
2. Audit code to find any similar problems
3. Prepare fixes for all releases still under maintenance
4. Publish a security advisory and release patches

We appreciate your efforts to responsibly disclose your findings, and will make every effort to acknowledge your contributions.

