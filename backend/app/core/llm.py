import json
import requests
from typing import Dict, Any, List
from app.config import OLLAMA_URL, LLM_MODEL
from app.schemas.case import ClassificationResult, ExtractedFacts, ComplaintDraft, RetrievedContext

class OllamaClient:
    def __init__(self):
        self.url = f"{OLLAMA_URL}/api/chat"

    def _call_ollama(self, prompt: str, system_prompt: str = "", json_mode: bool = True) -> str:
        """Helper to invoke Ollama chat API."""
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for highly structured facts and classification
            }
        }
        if json_mode:
            payload["format"] = "json"
            
        try:
            response = requests.post(self.url, json=payload, timeout=120)
            response.raise_for_status()
            result_json = response.json()
            return result_json.get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            print(f"Ollama API connection failed: {e}")
            raise RuntimeError(f"Could not connect to Ollama at {OLLAMA_URL}. Ensure Ollama is running and '{LLM_MODEL}' is pulled.")

    def classify_narrative(self, narrative: str) -> ClassificationResult:
        """Classify narrative as POSH, POCSO, or OTHER with detailed sub-category breakdown."""
        system_prompt = (
            "You are a legal expert specializing in Indian safety laws:\n"
            "1. PoSH (Prevention of Sexual Harassment at Workplace Act 2013):\n"
            "   - Quid Pro Quo Harassment: Promising workplace benefits (promotions, hikes) or threats (termination, bad appraisal) for sexual favors.\n"
            "   - Hostile Work Environment: Unwelcome conduct (Verbal, Non-Verbal/Visual, Physical, Digital/Hybrid like WhatsApp, late calls, memes).\n"
            "   - Extended Workplace Scenarios: Incidents during off-site work travel, client meetings, corporate retreats, transport, or involving third parties (vendors, interns, contractors).\n"
            "   Note: POSH applies to any workplace incident involving adult complainants (18 or older).\n\n"
            "2. POCSO (Protection of Children from Sexual Offences Act 2012):\n"
            "   - Physical Offences: Penetrative Sexual Assault (Sec 3&4), Non-Penetrative Sexual Assault (Sec 7&8), Aggravated Forms (Sec 5,6,9,10 - authority figure/teacher/doctor/relative).\n"
            "   - Non-Physical & Digital Offences: Sexual Harassment/Stalking (Sec 11&12), Child Sexual Abuse Material (CSAM) / Pornography (Sec 13-15 - real, simulated, or AI-generated).\n"
            "   Note: POCSO applies whenever victim is a minor under 18 years of age.\n\n"
            "CRITICAL AGE & CATEGORY RULES:\n"
            "1. If victim's age is 18 or above (or adult employee), classify as POSH (if workplace related) or OTHER. minor_involved MUST be false.\n"
            "2. If victim is under 18 years (child, minor, student), classify as POCSO. minor_involved MUST be true.\n\n"
            "You must return ONLY a JSON object matching this schema:\n"
            "{\n"
            "  \"category\": \"POSH\" | \"POCSO\" | \"OTHER\",\n"
            "  \"sub_category\": \"Specific sub-category name from the taxonomy above\",\n"
            "  \"confidence\": float (between 0.0 and 1.0),\n"
            "  \"minor_involved\": boolean,\n"
            "  \"rationale\": \"Detailed legal explanation of category and sub-category match\"\n"
            "}"
        )

        prompt = f"Please classify this incident narrative:\n\n{narrative}"
        
        # 1. Extract age using regex (checking before calling Ollama, to use in post-processing overrides)
        import re
        age = None
        age_patterns = [
            r'\bage\s*[-:\bisaof\s]*\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*[-]?\s*years?\s*[-]?\s*old\b',
            r'\baged\s*(\d{1,2})\b'
        ]
        for pattern in age_patterns:
            match = re.search(pattern, narrative, re.IGNORECASE)
            if match:
                try:
                    val = int(match.group(1))
                    if 1 <= val <= 120:
                        age = val
                        break
                except ValueError:
                    pass

        has_sexual = any(w in narrative.lower() for w in ["harass", "sexual", "abuse", "assault", "molest", "touch", "inappropriate", "remark", "comment", "advance", "quid pro quo", "porn", "csam", "stalk", "leering"])
        has_workplace = any(w in narrative.lower() for w in ["work", "office", "employee", "employer", "colleague", "supervisor", "manager", "staff", "job", "company", "firm", "corporate", "vendor", "intern", "contractor", "retreat", "appraisal", "promotion"])

        category = "OTHER"
        sub_category = None
        minor_involved = False
        confidence = 0.5
        rationale = ""

        raw_response = self._call_ollama(prompt, system_prompt)
        try:
            data = json.loads(raw_response)
            category = data.get("category", "OTHER").upper()
            sub_category = data.get("sub_category", None)
            minor_involved = bool(data.get("minor_involved", False))
            confidence = float(data.get("confidence", 0.5))
            rationale = data.get("rationale", "No explanation provided.")
        except Exception as e:
            print(f"Failed to parse classification: {e}. Raw response: {raw_response}")
            # Dynamic fallback: check narrative text for minor indicators and ages
            if age is not None:
                minor_involved = (age < 18)
            else:
                minor_involved = any(word in narrative.lower() for word in ["child", "minor", "school", "kid", "boy", "girl", "under 18", "student"])
            
            category = "POCSO" if minor_involved else "POSH" if (has_sexual and has_workplace) else "OTHER"
            rationale = "Fallback classification due to parser failure."

        # Apply deterministic overrides to correct LLM classification errors
        if age is not None:
            if age >= 18:
                minor_involved = False
                if category == "POCSO":
                    category = "POSH" if has_workplace else "OTHER"
                    rationale = f"Overrode category from POCSO to {category} because victim's age ({age}) indicates she is an adult. " + rationale
            else:
                minor_involved = True
                category = "POCSO"
                rationale = f"Overrode category to POCSO because victim is a minor (age {age}). " + rationale

        # Upgrade to POSH if it has clear workplace sexual harassment context for an adult
        if category == "OTHER" and has_sexual and has_workplace and not minor_involved:
            category = "POSH"
            rationale = "Overrode category to POSH because description contains workplace sexual harassment elements. " + rationale

        # Prevent false POCSO classification for adults
        if category == "POCSO" and not minor_involved:
            category = "POSH" if (has_workplace and has_sexual) else "OTHER"
            rationale = f"Overrode category to {category} because minor_involved is false. " + rationale

        # Prevent false POSH classification when no sexual harassment elements exist
        if category == "POSH" and not has_sexual:
            category = "OTHER"
            rationale = "Overrode category to OTHER because narrative does not describe sexual harassment or sexual conduct as required under the POSH Act. " + rationale

        # Derive or validate sub_category
        if not sub_category or sub_category.lower() == "none":
            sub_category = self._determine_sub_category(narrative, category)

        return ClassificationResult(
            category=category,
            sub_category=sub_category,
            confidence=confidence,
            minor_involved=minor_involved,
            rationale=rationale
        )

    def _determine_sub_category(self, narrative: str, category: str) -> str:
        """Helper to assign fine-grained POSH and POCSO sub-categories."""
        low = narrative.lower()
        if category == "POSH":
            if any(k in low for k in ["promise", "promotion", "appraisal", "hike", "salary", "threat", "demotion", "benefit", "quid pro quo", "fire", "terminate"]):
                return "POSH - Quid Pro Quo Harassment (Sec 3)"
            elif any(k in low for k in ["travel", "trip", "retreat", "offsite", "client", "vendor", "intern", "contractor", "transport", "cab"]):
                return "POSH - Extended Workplace Scenario (Sec 2(n))"
            elif any(k in low for k in ["whatsapp", "text", "message", "call", "meme", "screensaver", "email", "online", "social media", "video"]):
                return "POSH - Hostile Work Environment (Digital/Visual)"
            elif any(k in low for k in ["touch", "physical", "corner", "advance", "hug", "grab", "force"]):
                return "POSH - Hostile Work Environment (Physical Harassment)"
            else:
                return "POSH - Hostile Work Environment (Verbal/General Harassment)"
        elif category == "POCSO":
            if any(k in low for k in ["penetrat", "object", "rape", "assault"]):
                return "POCSO - Penetrative Sexual Assault (Sec 3 & 4)"
            elif any(k in low for k in ["csam", "porn", "pornograph", "photo", "video", "ai-generated", "simulated", "image"]):
                return "POCSO - CSAM / Pornography Offence (Sec 13–15)"
            elif any(k in low for k in ["stalk", "follow", "watch", "explicit word", "gesture", "exhibit"]):
                return "POCSO - Sexual Harassment / Stalking (Sec 11 & 12)"
            elif any(k in low for k in ["teacher", "principal", "doctor", "police", "caretaker", "relative", "uncle", "trust", "authority", "warden"]):
                return "POCSO - Aggravated Sexual Assault / Offence (Sec 5, 6, 9, 10)"
            else:
                return "POCSO - Non-Penetrative Sexual Assault (Sec 7 & 8)"
        return "General / Other"

    def extract_facts(self, narrative: str) -> ExtractedFacts:
        """Extract structured facts from the narrative."""
        system_prompt = (
            "You are a helpful legal assistant. Analyze the incident narrative and extract these facts into JSON:\n"
            "- complainant_name: The name of the victim or person filing the complaint (e.g. the person saying 'I am [Name]').\n"
            "- respondent_name: The name of the accused person who committed the harassment/offence.\n"
            "- incident_date: The date or time range of the incident.\n"
            "- incident_location: Where the incident occurred.\n"
            "- nature_of_incident: A brief summary of the allegations.\n"
            "- witnesses: List of names of witnesses mentioned (excluding complainant).\n"
            "- evidence_description: List of any evidence mentioned (e.g. emails, messages).\n\n"
            "Format strictly as JSON:\n"
            "{\n"
            "  \"complainant_name\": \"Name or null\",\n"
            "  \"respondent_name\": \"Name or null\",\n"
            "  \"incident_date\": \"Date or null\",\n"
            "  \"incident_location\": \"Location or null\",\n"
            "  \"nature_of_incident\": \"Summary\",\n"
            "  \"witnesses\": [\"Witness1\"],\n"
            "  \"evidence_description\": [\"Evidence1\"]\n"
            "}"
        )

        prompt = f"Analyze and extract facts from this narrative:\n\n{narrative}"
        
        raw_response = self._call_ollama(prompt, system_prompt)
        try:
            data = json.loads(raw_response)
            return ExtractedFacts(
                complainant_name=data.get("complainant_name"),
                respondent_name=data.get("respondent_name"),
                incident_date=data.get("incident_date"),
                incident_location=data.get("incident_location"),
                nature_of_incident=data.get("nature_of_incident", "Not specified"),
                witnesses=data.get("witnesses", []),
                evidence_description=data.get("evidence_description", [])
            )
        except Exception as e:
            print(f"Failed to parse extracted facts: {e}. Raw response: {raw_response}")
            return ExtractedFacts(
                nature_of_incident="Failed to extract details automatically from narrative.",
                witnesses=[],
                evidence_description=[]
            )

    def _generate_incident_narrative(self, facts: ExtractedFacts, context_str: str) -> str:
        """Build a factual incident narrative paragraph.
        
        Uses a deterministic Python-built narrative as the foundation.
        The LLM is used to polish the language, but the output is validated
        to ensure it still references the correct names/facts. If the LLM
        hallucinates (common with small models), the Python-built version is used.
        """
        # Build the reliable, fact-based narrative in Python
        complainant = facts.complainant_name or "[Complainant]"
        respondent = facts.respondent_name or "[Respondent]"
        date = facts.incident_date or "[Date]"
        location = facts.incident_location or "[Location]"
        
        parts = [
            f"On {date}, at {location}, the respondent {respondent} engaged in the following conduct "
            f"against the complainant {complainant}: {facts.nature_of_incident}."
        ]
        if facts.witnesses:
            parts.append(f"The incident was witnessed by: {', '.join(facts.witnesses)}.")
        if facts.evidence_description:
            parts.append(f"Evidence available includes: {', '.join(facts.evidence_description)}.")
        
        base_narrative = " ".join(parts)

        # Attempt LLM polish — but validate the output contains the actual names
        try:
            system_prompt = (
                "You are a professional legal writer. Rewrite the following incident description "
                "into a more formal, professional paragraph suitable for a legal complaint. "
                "You MUST keep all names, dates, locations, and facts EXACTLY as provided. "
                "Do not invent any new details. Do not add disclaimers. Output ONLY the rewritten paragraph."
            )
            prompt = f"Rewrite this incident description more formally:\n\n{base_narrative}"
            
            polished = self._call_ollama(prompt, system_prompt, json_mode=False).strip()
            
            # Validate: the polished version must still reference the key facts
            if (polished 
                and complainant != "[Complainant]" and complainant.split()[0] in polished
                and respondent != "[Respondent]" and respondent.split()[0] in polished):
                return polished
            else:
                print(f"LLM narrative validation failed — using deterministic fallback.")
        except Exception as e:
            print(f"LLM narrative polish failed: {e}")

        return base_narrative

    def generate_draft(self, category: str, facts: ExtractedFacts, contexts: List[RetrievedContext]) -> ComplaintDraft:
        """Generate formal complaint draft using deterministic Python templates.
        
        The LLM is used ONLY to write the incident narrative paragraph.
        All structural elements (headers, sections, declarations) are built in Python
        to ensure consistency, correctness, and to avoid LLM safety filter refusals.
        """

        # Prepare context snippets and citations
        context_str = ""
        citations_list = []
        for i, ctx in enumerate(contexts):
            context_str += f"\n[{i+1}] Source: {ctx.source}\nContent: {ctx.text_snippet}\n"
            citations_list.append(f"Section/Snippet from {ctx.source}")
        citations_str = ", ".join(citations_list) if citations_list else "Relevant statutory provisions"

        # Use LLM only for the incident narrative paragraph
        incident_narrative = self._generate_incident_narrative(facts, context_str)

        # Format helper values
        complainant = facts.complainant_name or "[Specify Name]"
        respondent = facts.respondent_name or "[Specify Name]"
        date = facts.incident_date or "[Specify Date]"
        location = facts.incident_location or "[Specify Location]"
        witnesses_str = "\n".join(f"- {w}" for w in facts.witnesses) if facts.witnesses else "- None mentioned"
        evidence_str = "\n".join(f"- {e}" for e in facts.evidence_description) if facts.evidence_description else "- None mentioned"

        # Build complaint deterministically based on category
        if category == "POSH":
            addressed_to = "The Presiding Officer, Internal Committee (IC), [Organization Name]"
            draft_text = (
                "FORMAL COMPLAINT UNDER THE POSH ACT, 2013\n"
                "(Sexual Harassment of Women at Workplace - Prevention, Prohibition and Redressal Act, 2013)\n\n"
                "Addressed To:\n"
                "The Presiding Officer,\n"
                "Internal Committee (IC),\n"
                "[Organization Name]\n"
                "[Organization Address]\n\n"
                "Date of Complaint: [Current Date]\n\n"
                "1. Complainant Details\n"
                f"- Full Name: {complainant}\n"
                "- Employee/ID No.: [Specify Employee ID]\n"
                "- Designation/Department: [Specify Designation/Department]\n"
                "- Contact No. / Email: [Specify Contact Info]\n"
                "- Relationship to Respondent: [e.g., Colleague, Reporting Subordinate, etc.]\n\n"
                "2. Respondent (Accused) Details\n"
                f"- Full Name: {respondent}\n"
                "- Designation/Department: [Specify Designation/Department]\n"
                "- Relationship/Reporting Line to Complainant: [Specify Reporting Line]\n\n"
                "3. Details of Incident(s)\n"
                f"- Date(s) & Time(s) of Incident: {date}\n"
                f"- Location(s): {location}\n"
                f"- Nature of Incident(s):\n{incident_narrative}\n\n"
                f"  Legal References: {citations_str}\n\n"
                "4. Witnesses (if any)\n"
                f"{witnesses_str}\n\n"
                "5. Evidence Available\n"
                f"{evidence_str}\n\n"
                "6. Relief / Action Sought\n"
                "[Specify relief or action sought, e.g., inquiry, transfer, suspension of respondent, or policy action]\n\n"
                "7. Declaration\n"
                "I hereby declare that the information provided above is true and accurate to the best of my knowledge. "
                "I understand that a false or malicious complaint may attract action under the applicable rules of the PoSH Act, 2013. "
                "I am aware of the confidentiality provisions under Section 16 of the Act and request that this complaint "
                "and related proceedings be treated as confidential.\n\n"
                "Signature of Complainant: _________________________\n"
                "Date: _________________________"
            )
        elif category == "POCSO":
            addressed_to = "The Officer-in-Charge, Special Juvenile Police Unit (SJPU) / Local Police Station"
            draft_text = (
                "FORMAL COMPLAINT / REPORT UNDER THE POCSO ACT, 2012\n"
                "(Protection of Children from Sexual Offences Act, 2012)\n\n"
                "MANDATORY REPORTING NOTICE: Under Section 19 of the POCSO Act, 2012, any person who has "
                "knowledge of an offence against a child (a person under 18 years of age) is legally required "
                "to report it to the local Police or the Special Juvenile Police Unit (SJPU). Failure to report "
                "is a punishable offence under Section 21 of the Act.\n\n"
                "Addressed To:\n"
                "The Officer-in-Charge,\n"
                "[Police Station Name] / Special Juvenile Police Unit (SJPU)\n"
                "[Station Address]\n\n"
                "Date of Report: [Current Date]\n\n"
                "1. Reporting Person Details\n"
                "- Full Name: [Specify Your Full Name]\n"
                "- Relationship to Child: [Specify Relationship, e.g. Parent, Guardian, Teacher, Witness]\n"
                "- Contact No. / Email: [Specify Contact Info]\n"
                "- Address: [Specify Address]\n\n"
                "2. Child (Victim) Details\n"
                "(Note: Under Section 23 of the POCSO Act, the child's identity must not be disclosed to the media; "
                "handle this section with strict confidentiality.)\n"
                f"- Name / Initials: {complainant}\n"
                "- Age / Date of Birth: [Specify Age]\n"
                "- Relationship to Reporting Person: [Specify Relationship]\n"
                "- Current Location / Safety Status: [Specify Safety Status / Immediate Protection Details]\n\n"
                "3. Accused (If Known)\n"
                f"- Name: {respondent}\n"
                "- Relationship to Child: [Specify relationship if any, e.g., teacher, helper, stranger]\n"
                "- Address / Whereabouts (if known): [Specify Address]\n\n"
                "4. Details of Incident(s)\n"
                f"- Date(s) & Time(s) of Incident: {date}\n"
                f"- Location(s): {location}\n"
                f"- Nature of Incident(s):\n{incident_narrative}\n\n"
                f"  Legal References: {citations_str}\n\n"
                "5. Witnesses (if any)\n"
                f"{witnesses_str}\n\n"
                "6. Evidence Available\n"
                f"{evidence_str}\n\n"
                "7. Immediate Safety / Support Needs\n"
                "[Specify safety or trauma support requirements]\n\n"
                "8. Declaration\n"
                "I hereby declare that the information provided above is true and accurate to the best of my knowledge. "
                "I am submitting this report in compliance with the mandatory reporting obligation under Section 19 of "
                "the POCSO Act, 2012. I understand that identity and confidentiality provisions under Section 23 of the "
                "Act apply to this matter.\n\n"
                "Signature of Reporting Person: _________________________\n"
                "Date: _________________________"
            )
        else:
            addressed_to = "The Appropriate Authority"
            draft_text = (
                "FORMAL COMPLAINT\n\n"
                "Addressed To:\n"
                "The Appropriate Authority\n\n"
                "Date of Complaint: [Current Date]\n\n"
                "1. Details of Complainant\n"
                f"- Full Name: {complainant}\n"
                "- Contact No. / Email: [Specify Contact Info]\n\n"
                "2. Details of Accused/Respondent\n"
                f"- Full Name: {respondent}\n\n"
                "3. Incident Details\n"
                f"- Date: {date}\n"
                f"- Location: {location}\n"
                f"- Description:\n{incident_narrative}\n\n"
                "4. Witnesses\n"
                f"{witnesses_str}\n\n"
                "5. Evidence\n"
                f"{evidence_str}\n\n"
                "Signature: _________________________\n"
                "Date: _________________________"
            )

        # Standard legal disclaimer (strictly enforced in Python)
        disclaimer = (
            "DISCLAIMER: This complaint draft was generated using artificial intelligence (AI) based on the input provided. "
            "It is intended only as a drafting aid and does not constitute formal legal advice. Please review the details carefully "
            "and consult with a qualified legal professional or your organization's compliance officer before final submission."
        )

        return ComplaintDraft(
            category=category,
            addressed_to=addressed_to,
            draft_text=draft_text,
            disclaimer=disclaimer,
            citations=contexts
        )
