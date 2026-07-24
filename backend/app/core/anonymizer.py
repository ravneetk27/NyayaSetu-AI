import re
from typing import Tuple, Dict

class Anonymizer:
    def __init__(self):
        # Email pattern
        self.email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        # Phone pattern (supports standard 10 digit, country codes, spaces, hyphens)
        self.phone_regex = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

    def anonymize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Scan text for PII (emails, phone numbers) and replace with placeholders.
        Returns the anonymized text and a mapping dictionary for restoration.
        """
        mapping = {}
        anonymized_text = text

        # Anonymize Emails
        emails = self.email_regex.findall(anonymized_text)
        for idx, email in enumerate(set(emails)):
            placeholder = f"[EMAIL_{idx + 1}]"
            mapping[placeholder] = email
            anonymized_text = anonymized_text.replace(email, placeholder)

        # Anonymize Phone Numbers
        phones = self.phone_regex.findall(anonymized_text)
        for idx, phone in enumerate(set(phones)):
            # Skip short numbers matched by accident
            if len(re.sub(r'\D', '', phone)) < 8:
                continue
            placeholder = f"[PHONE_{idx + 1}]"
            mapping[placeholder] = phone
            anonymized_text = anonymized_text.replace(phone, placeholder)

        return anonymized_text, mapping

    def deanonymize(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Restore anonymized placeholders in the generated draft with original PII.
        """
        restored_text = text
        for placeholder, original in mapping.items():
            restored_text = restored_text.replace(placeholder, original)
        return restored_text
