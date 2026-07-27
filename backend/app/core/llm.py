import re
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

    def generate_chat_reply(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Empathetic, trauma-informed Legal Intake Assistant following PoSH vs POCSO rules and vague input handling."""
        user_msgs = [m['content'].strip() for m in messages if m['role'] == 'user']
        last_user_msg = user_msgs[-1] if user_msgs else ""
        low_last = last_user_msg.lower()

        greetings = [
            "hello", "hi", "hey", "good morning", "good evening", "namaste", 
            "sat shri akal", "satsriakal", "adaab", "pranam", "help"
        ]

        # Greeting handler (When user writes "hi" / "hello")
        if low_last in greetings or low_last in [g + "." for g in greetings] or low_last in [g + "!" for g in greetings]:
            return {
                "reply": "Before we begin, could you please tell me your name so we can get started?",
                "quick_replies": []
            }

        # Informational Queries
        if "rights" in low_last or "understand my rights" in low_last:
            return {
                "reply": "You have protected legal rights under Indian law:\n\n1. PoSH Act (2013): Protects adult employees against workplace sexual harassment, guarantees strict confidentiality (Sec 16), and interim relief (Sec 12).\n2. POCSO Act (2012): Protects minors under 18 years of age against sexual offences, ensuring mandatory reporting (Sec 19) and identity protection (Sec 23).\n\nWould you like to start drafting a confidential report?",
                "quick_replies": []
            }

        if low_last == "posh" or "what is posh" in low_last:
            return {
                "reply": "PoSH (Prevention of Sexual Harassment at Workplace Act, 2013) is an Indian law protecting employees from unwelcome physical, verbal, or digital conduct at workplace. Complaints are handled confidentially by an Internal Committee (IC).\n\nWould you like to start drafting a complaint?",
                "quick_replies": []
            }

        if low_last == "pocso" or "what is pocso" in low_last:
            return {
                "reply": "POCSO (Protection of Children from Sexual Offences Act, 2012) is a law protecting individuals under 18 years of age. Under Section 19, reporting offences to local police or SJPU is a legal obligation, and Emergency Childline is 1098.\n\nWould you like to start drafting a report?",
                "quick_replies": []
            }

        # Extract name & framework context
        full_user_text = " ".join(user_msgs).lower()
        non_greetings = [m for m in user_msgs if m.strip().lower() not in greetings and not any(m.strip().lower().startswith(g) for g in ["hello", "hi ", "hey ", "namaste"])]

        import re
        name_match = re.search(r'(?:name is|i am|my name is)\s+([A-Za-z]+)', full_user_text, re.IGNORECASE)
        if name_match:
            name_str = name_match.group(1).capitalize()
        elif non_greetings:
            name_str = non_greetings[0].strip().split()[0].capitalize()
        else:
            name_str = "there"

        # Check legal framework (Rule 1): POCSO (Under 18) vs POSH (18+)
        is_pocso = any(kw in full_user_text for kw in ["under 18", "minor", "child", "pocso", "school", "student", "kid"])
        is_posh = any(kw in full_user_text for kw in ["18 or above", "adult", "posh", "workplace", "office", "employee", "company"])

        # Stage 1: User provided Name -> Ask for Age Group
        if len(non_greetings) <= 1 and not (is_pocso or is_posh):
            return {
                "reply": f"Thank you, {name_str}. Please select your age group below so I can guide you under the correct legal framework.",
                "quick_replies": []
            }

        # Stage 2: User selected Age Group -> Gentle opening
        if len(non_greetings) == 2 or (len(non_greetings) == 1 and (is_pocso or is_posh)):
            if is_pocso:
                return {
                    "reply": f"Thank you for reaching out, {name_str}. You are in a safe, confidential space protected under Section 19 of the POCSO Act. Whenever you feel comfortable, please take your time and share what happened.",
                    "quick_replies": []
                }
            else:
                return {
                    "reply": f"Thank you, {name_str}. Under Section 16 of the PoSH Act, your conversation is 100% confidential. Whenever you feel comfortable, please take your time and share what happened so I can guide you and help prepare your report.",
                    "quick_replies": []
                }

        # Rule 2: Handle Vague or Confusing Inputs Naturally
        # Check if latest user input is very short, vague, or confusing
        vague_phrases = ["someone say my name", "i don't know", "idk", "it was bad", "not sure", "something happened", "someone touched", "bad thing"]
        is_vague = (len(low_last.split()) <= 4 and (any(v in low_last for v in vague_phrases) or low_last.startswith("someone") or low_last == "bad"))

        if is_vague:
            return {
                "reply": f"I am here to listen and support you. Could you tell me a little more about what happened when {low_last}?",
                "quick_replies": []
            }

        # Rule 3 & 4: Trauma-Informed Sequential Details Gathering (One by One)
        # Stage 3+: Incident described -> Ask missing details one by one using strict Framework rules!

        narrative_msgs = [
            m for m in non_greetings 
            if not any(k in m.lower() for k in ["18 or above", "under 18", "pocso", "posh", "adult", "minor"]) 
            and m.strip().capitalize() != name_str
        ]

        has_accused = any(w in full_user_text for w in ["boss", "colleague", "senior", "manager", "employee", "person", "accused", "respondent", "mr", "ms", "supervisor", "director", "teacher", "sir", "madam", "adult", "relative"])
        has_location = any(w in full_user_text for w in ["office", "workplace", "room", "building", "site", "online", "cabin", "canteen", "home", "school", "college", "premises", "desk", "park", "mohali", "chandigarh", "delhi", "mumbai"])
        has_date = any(w in full_user_text for w in ["yesterday", "today", "date", "month", "year", "week", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "2024", "2025", "2026"])
        has_evidence = any(w in full_user_text for w in ["email", "chat", "message", "photo", "proof", "record", "screenshot", "whatsapp", "documents", "cctv"]) or ("evidence" in full_user_text and low_last in ["no", "none", "no, nothing"])
        has_witnesses = any(w in full_user_text for w in ["witness", "people", "saw", "present"]) or ("witness" in full_user_text and low_last in ["no", "none", "no, nothing"])

        # Check if user just said "yes" to evidence inquiry (Ambiguity Handling)
        if low_last == "yes" or low_last == "yeah" or low_last == "yep":
            return {
                "reply": "Thank you for confirming. Could you please specify what kind of evidence you have, such as emails, text messages, or screenshots?",
                "quick_replies": []
            }

        # 1. Ask Accused Person
        if not has_accused:
            if is_pocso:
                return {
                    "reply": "I hear you, and thank you for trusting me with this. Could you share the name or how you know the person involved?",
                    "quick_replies": []
                }
            else:
                return {
                    "reply": "Thank you for sharing this. To help complete your formal complaint draft, could you share the name or job role of the person involved?",
                    "quick_replies": []
                }

        # 2. Ask Location
        if not has_location:
            if is_pocso:
                return {
                    "reply": "Could you tell me where this happened (for example, at school, at home, online, or somewhere else)?",
                    "quick_replies": []
                }
            else:
                return {
                    "reply": "Could you please specify where this incident took place (e.g. office premises, meeting room, client site, or online)?",
                    "quick_replies": []
                }

        # 3. Ask Date
        if not has_date:
            return {
                "reply": "Approximately when did this happen (e.g. recent date, day of week, or month)?",
                "quick_replies": []
            }

        # 4. Ask Evidence FIRST (One question at a time!)
        if not has_evidence:
            return {
                "reply": "Do you have any emails, text messages, or screenshots as evidence?",
                "quick_replies": []
            }

        # 5. Ask Witnesses SECOND (One question at a time!)
        if not has_witnesses:
            return {
                "reply": "Were there any colleagues or other people who witnessed the incident?",
                "quick_replies": []
            }

        # All details gathered
        return {
            "reply": "Thank you for the details, I have gathered the necessary facts for your confidential report. Whenever you are ready, click 'Convert Conversation into Draft Complaint' below to view your draft.",
            "quick_replies": []
        }

    def classify_narrative(self, narrative: str) -> ClassificationResult:
        """Strict statutory classification enforcing POSH, POCSO, or OTHER."""
        low = narrative.lower()

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

        minor_involved = (age is not None and age < 18) or any(w in low for w in ["under 18", "pocso", "minor", "child", "student", "kid", "school", "boy", "girl"])
        
        # Sexual Harassment & Offence terms strictly required for POSH & POCSO
        sexual_terms = [
            "harass", "sexual", "abuse", "assault", "molest", "touch", "inappropriate", 
            "remark", "comment", "advance", "quid pro quo", "porn", "csam", "stalk", 
            "leering", "uncomfortable", "dress", "body", "tease", "hug", "kiss", "naked"
        ]
        has_sexual = any(w in low for w in sexual_terms)
        has_workplace = any(w in low for w in ["work", "office", "employee", "employer", "colleague", "supervisor", "manager", "staff", "job", "company", "firm", "corporate", "vendor", "intern", "contractor", "retreat", "appraisal", "promotion", "18 or above", "adult", "posh"])

        if minor_involved and has_sexual:
            category = "POCSO"
        elif not minor_involved and has_sexual and (has_workplace or "posh" in low or "18 or above" in low):
            category = "POSH"
        elif minor_involved:
            category = "POCSO"
        elif has_sexual:
            category = "POSH"
        else:
            # If no sexual harassment elements exist (e.g. "someone talk to me"), classify strictly as OTHER!
            category = "OTHER"

        sub_category = self._determine_sub_category(narrative, category)

        return ClassificationResult(
            category=category,
            sub_category=sub_category if category != "OTHER" else "General / Non-Sexual Interaction",
            confidence=0.98,
            minor_involved=minor_involved,
            rationale=f"Classified as {category} based on statutory legal scope (Sexual Harassment: {has_sexual}, Workplace: {has_workplace}, Minor: {minor_involved})."
        )

    def extract_facts_from_chat(self, messages: List[Dict[str, str]]) -> ExtractedFacts:
        """Extract structured facts following Master System Prompt rules & zero-inference policy."""
        user_msgs = [m['content'].strip() for m in messages if m['role'] == 'user']
        full_text = " ".join(user_msgs)
        
        greetings = [
            "hello", "hi", "hey", "good morning", "good evening", "namaste", 
            "sat shri akal", "satsriakal", "adaab", "pranam", "help"
        ]
        
        non_greetings = [
            m for m in user_msgs 
            if m.strip().lower() not in greetings 
            and not any(m.strip().lower().startswith(g) for g in ["hello", "hi ", "hey ", "namaste", "sat shri akal"])
        ]

        # 1. Complainant Name: Extract proper nouns only (e.g. "Mita", "Geeta", or "I am Mita")
        complainant_name = "Not Provided"
        for msg in user_msgs:
            low_m = msg.lower().strip()
            if low_m in greetings or any(k in low_m for k in ["18 or above", "under 18", "pocso", "posh", "adult", "minor"]):
                continue
            comp_match = re.search(r'\b(?:name is|i am|my name is)\s+([A-Z][a-z]+)', msg, re.IGNORECASE)
            if comp_match:
                cand = comp_match.group(1).capitalize()
                if cand.lower() not in ["an", "the", "a", "user", "assistant", "statement", "here", "ready"]:
                    complainant_name = cand
                    break
            words = msg.strip().split()
            if len(words) <= 2 and words[0].isalpha() and words[0].lower() not in greetings and words[0].lower() not in ["no", "none", "an", "the", "employee", "manager", "someone", "yesterday", "today", "client", "office", "company", "room"]:
                complainant_name = words[0].capitalize()
                break

        # Filter out age selection responses and name message
        narrative_msgs = [
            m for m in non_greetings 
            if not any(k in m.lower() for k in ["18 or above", "under 18", "pocso", "posh", "adult", "minor"]) 
            and m.strip().capitalize() != complainant_name
            and not m.lower().startswith("i am ")
        ]

        # 2. Nature of Incident: Factual summary
        nature_of_incident = "Not Provided"
        if narrative_msgs:
            nature_of_incident = narrative_msgs[0].strip()

        # 3. Respondent (Accused Name): Extract proper nouns ONLY.
        # NEVER extract job titles ("manager", "employee"), location words ("meeting room", "company"), or action verbs!
        respondent_name = "Not Provided"

        location_words = ["room", "office", "company", "building", "site", "cabin", "premises", "floor", "street", "park", "online", "platform", "ivy", "ltd", "inc", "corp", "department"]
        job_titles = ["manager", "employee", "colleague", "boss", "senior", "subordinate", "staff", "director", "supervisor", "officer", "person", "someone", "adult"]
        action_verbs = ["tease", "talk", "harass", "harras", "touch", "said", "came", "went", "did", "looked", "asked", "call", "send", "give", "want"]
        refusal_terms = ["don't", "dont", "no", "none", "withheld", "unknown", "not provided", "right now", "refuse"]

        for msg in user_msgs:
            if any(w in msg.lower() for w in ["don't want to give", "dont want", "refuse", "not specified", "withheld"]):
                respondent_name = "Not Provided"
                break
            resp_match = re.search(r'\b(?:respondent|accused|by|mr|ms|dr)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', msg)
            if resp_match:
                cand_name = resp_match.group(1).title()
                if not any(lw in cand_name.lower() for lw in location_words) and not any(jt in cand_name.lower() for jt in job_titles):
                    respondent_name = cand_name
                    break

        if respondent_name == "Not Provided" and len(narrative_msgs) >= 2:
            r_text = narrative_msgs[1].strip()
            if (not any(lw in r_text.lower() for lw in location_words) and
                not any(jt in r_text.lower() for jt in job_titles) and
                not any(rf in r_text.lower() for rf in refusal_terms) and
                not any(verb in r_text.lower() for verb in action_verbs)):
                if len(r_text.split()) <= 3 and r_text[0].isupper():
                    respondent_name = r_text.title()

        # 4. Location: Extract physical place (e.g. "Ivy Company Meeting Room")
        incident_location = "Not Provided"
        for msg in user_msgs:
            low_m = msg.lower()
            if any(lw in low_m for lw in location_words) and not any(verb in low_m for verb in ["harras", "harass", "touch", "abuse", "molest", "assault"]) and not low_m.startswith("i am ") and not any(k in low_m for k in ["18 or above", "under 18"]):
                incident_location = msg.strip().title()
                break

        if incident_location == "Not Provided":
            loc_match = re.search(r'\b(?:at|in)\s+(?:the\s+)?(meeting room|office|workplace|building|site|cabin|canteen|online|premises|desk|mohali|chandigarh|delhi|mumbai)', full_text, re.IGNORECASE)
            if loc_match:
                incident_location = loc_match.group(1).title()

        # 5. Incident Date: Extract time/date ONLY (must contain date/time indicators and NO location words!)
        incident_date = "Not Provided"
        date_keywords = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "yesterday", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "2024", "2025", "2026", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "recent", "week", "month"]
        
        date_match = re.search(r'\b(?:on|date|during|in)\s+(\d{1,2}\s+[A-Za-z]+|[A-Za-z]+\s+\d{1,2}|yesterday|last week|recent days|\d{1,2}/\d{1,2}/\d{2,4})', full_text, re.IGNORECASE)
        if date_match:
            incident_date = date_match.group(1).title()
        elif len(narrative_msgs) >= 4:
            d_text = narrative_msgs[3].strip()
            low_d = d_text.lower()
            if low_d not in ["no", "none", "n/a", "not sure", "don't know", "not provided"]:
                # Must contain date/time indicators AND no location words
                if any(dk in low_d for dk in date_keywords) and not any(lw in low_d for lw in location_words):
                    incident_date = d_text.title()
                elif any(lw in low_d for lw in location_words):
                    # If location string was typed when asked for date, set location!
                    if incident_location == "Not Provided":
                        incident_location = d_text.title()
                    incident_date = "Not Provided"

        # 6. Witnesses & Evidence: Strictly "None" if denied
        witnesses = []
        evidence_description = []
        if any(msg.lower() == "no" or "no, nothing" in msg.lower() or "none" in msg.lower() for msg in user_msgs):
            witnesses = []
            evidence_description = []
        else:
            if len(narrative_msgs) >= 5:
                e_text = narrative_msgs[4].strip()
                if any(k in e_text.lower() for k in ["yes", "email", "chat", "message", "screenshot", "saw", "witness", "photo", "proof"]):
                    evidence_description = ["Digital records / Witness statements"]

        return ExtractedFacts(
            complainant_name=complainant_name,
            respondent_name=respondent_name,
            incident_date=incident_date,
            incident_location=incident_location,
            nature_of_incident=nature_of_incident,
            witnesses=witnesses,
            evidence_description=evidence_description
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
        """Fast pattern-based & hybrid fact extraction to eliminate multi-second LLM delays."""
        low = narrative.lower()

        # 1. Complainant Name
        complainant_name = None
        comp_match = re.search(r'(?:complainant statement|name is|i am|my name is)\s*[:\-]?\s*([A-Za-z]+)', narrative, re.IGNORECASE)
        if comp_match:
            c_candidate = comp_match.group(1).capitalize()
            if c_candidate.lower() not in ["statement", "the", "an", "a", "user", "assistant"]:
                complainant_name = c_candidate

        # 2. Respondent Name
        respondent_name = None
        resp_match = re.search(r'(?:respondent|accused|by|manager|colleague|boss|senior|employee|mr|ms|dr)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', narrative)
        if resp_match:
            respondent_name = resp_match.group(1).strip()
        elif "manager" in low or "boss" in low or "colleague" in low:
            respondent_name = "Manager / Accused Colleague"

        # 3. Incident Date
        incident_date = None
        date_match = re.search(r'(?:on|date|time|during|in)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|yesterday|last week|recent days|march\s+\d{1,2})', narrative, re.IGNORECASE)
        if date_match:
            incident_date = date_match.group(1).strip()

        # 4. Incident Location
        incident_location = None
        loc_match = re.search(r'(?:at|in|location)\s+(the\s+)?([A-Za-z0-9\s]+(?:office|meeting room|workplace|building|site|cabin|canteen|online|premises|desk))', narrative, re.IGNORECASE)
        if loc_match:
            incident_location = loc_match.group(0).strip()
        elif "office" in low or "meeting room" in low or "workplace" in low:
            incident_location = "Office Premises / Meeting Room"

        # 5. Nature of Incident
        statements = [line.replace("Complainant Statement:", "").strip() for line in narrative.split("\n") if "complainant statement:" in line.lower() or "harass" in line.lower() or "uncomfortable" in line.lower() or "dress" in line.lower() or "comment" in line.lower()]
        nature_summary = " ".join(statements) if statements else narrative.strip()

        # 6. Witnesses & Evidence
        witnesses = []
        evidence = []
        if "witness" in low or "saw" in low:
            witnesses.append("Witnesses mentioned in statement")
        if any(w in low for w in ["email", "message", "chat", "screenshot", "proof"]):
            evidence.append("Digital records / messages mentioned")

        return ExtractedFacts(
            complainant_name=complainant_name,
            respondent_name=respondent_name,
            incident_date=incident_date,
            incident_location=incident_location,
            nature_of_incident=nature_summary if nature_summary else "Alleged incident of workplace harassment.",
            witnesses=witnesses,
            evidence_description=evidence
        )

    def _generate_incident_narrative(self, facts: ExtractedFacts, context_str: str) -> str:
        """Fast, 0-millisecond deterministic incident narrative generator."""
        complainant = facts.complainant_name or "[Complainant]"
        respondent = facts.respondent_name or "[Respondent/Accused]"
        date = facts.incident_date or "[Date of Incident]"
        location = facts.incident_location or "[Location of Incident]"
        
        parts = [
            f"On {date}, at {location}, the respondent ({respondent}) reportedly engaged in unwelcome conduct "
            f"against the complainant ({complainant}), specifically: {facts.nature_of_incident}."
        ]
        if facts.witnesses:
            parts.append(f"Witnesses: {', '.join(facts.witnesses)}.")
        if facts.evidence_description:
            parts.append(f"Available Evidence: {', '.join(facts.evidence_description)}.")
        
        return " ".join(parts)

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
