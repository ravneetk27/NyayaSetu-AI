import re
import json
import os
from datetime import date
from typing import Dict, Any, List, Optional
from groq import Groq
from app.config import GROQ_API_KEY, LLM_MODEL
from app.schemas.case import (
    ClassificationResult, 
    ExtractedFacts, 
    ComplaintDraft, 
    RetrievedContext,
    AgentResponsePayload,
    UIState,
    ExtractedEntities
)

OUT_OF_SCOPE_MESSAGE = "I am an AI assistant specialized strictly in POSH (Prevention of Sexual Harassment) and POCSO (Protection of Children from Sexual Offences) matters. I cannot answer or process queries outside of these legal domains."

class OllamaClient:
    """LLM client — now backed by the Groq cloud API instead of a local Ollama server."""

    def __init__(self):
        if not GROQ_API_KEY:
            print("[WARN] GROQ_API_KEY is not set. LLM calls will fail. "
                  "Set it via the GROQ_API_KEY environment variable.")
        self._groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    # ------------------------------------------------------------------
    # Private helpers — Groq equivalents of the old Ollama helpers
    # ------------------------------------------------------------------

    def _call_ollama(self, prompt: str, system_prompt: str = "", json_mode: bool = True) -> str:
        """Single-turn call that requests JSON output (mirrors old Ollama JSON mode)."""
        if self._groq is None:
            raise RuntimeError("GROQ_API_KEY is not configured. "
                               "Add it as an environment variable.")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = dict(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=512,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._groq.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"Groq API call failed: {e}")
            raise RuntimeError(f"Could not reach Groq API: {e}")

    def check_domain_relevance(self, text: str) -> bool:
        """Check if user query is strictly within POSH or POCSO legal domain scope."""
        if not text or not text.strip():
            return True
        low = text.lower().strip()

        # Simple conversational greetings & intake steps are within scope
        greetings = [
            "hello", "hi", "hey", "good morning", "good evening", "namaste", 
            "sat shri akal", "adaab", "pranam", "help", "yes", "no", "sure",
            "18 or above", "under 18", "adult", "minor"
        ]
        if low in greetings or any(low == g for g in greetings) or low.startswith("my name is") or low.startswith("i am "):
            return True

        # Explicit out of scope patterns (coding, corporate finance, sports, weather, unrelated general law/math)
        out_of_scope_patterns = [
            r'\bpython\b', r'\bjavascript\b', r'\bcode\b', r'\bcoding\b', r'\bfunction\b', r'\bhtml\b', r'\bcss\b', r'\bjava\b', r'\bc\+\+\b',
            r'\bweather\b', r'\bcricket\b', r'\bfootball\b', r'\bsport\b', r'\bmovie\b', r'\brecipe\b', r'\bcooking\b',
            r'\bstock market\b', r'\bfinance\b', r'\bcorporate tax\b', r'\breal estate\b', r'\bbitcoin\b', r'\bcrypto\b',
            r'\bmath\b', r'\bphysics\b', r'\bchemistry\b', r'\bheadache\b', r'\bmedicine\b',
            r'\btraffic violation\b', r'\btheft\b', r'\bburglary\b', r'\bincome tax\b', r'\bgst\b', r'\bproperty\b'
        ]
        for pat in out_of_scope_patterns:
            if re.search(pat, low):
                return False

        # Positive POSH / POCSO domain terms
        posh_pocso_terms = [
            "posh", "pocso", "harass", "sexual", "abuse", "assault", "molest", "touch",
            "inappropriate", "remark", "advance", "quid pro quo", "porn", "csam", "stalk",
            "workplace", "office", "ic", "internal committee", "local committee", "presiding officer",
            "district officer", "sjpu", "police", "child", "minor", "under 18", "18 or above",
            "employee", "employer", "victim", "complainant", "respondent", "accused", "witness",
            "evidence", "reporting", "confidential", "penalty", "punishment", "inquiry",
            "conciliation", "interim relief", "compensation", "false complaint", "malicious",
            "court", "magistrate", "statement", "rights", "act", "section", "law", "legal",
            "incident", "happened", "colleague", "manager", "boss", "supervisor", "school",
            "teacher", "principal", "doctor", "hospital", "hostile", "environment"
        ]
        if any(kw in low for kw in posh_pocso_terms):
            return True

        # General non-legal queries without POSH/POCSO context
        general_non_legal = ["who is", "what is", "how to", "tell me about", "where is", "why does", "calculate", "write a"]
        if any(low.startswith(p) for p in general_non_legal) and not any(kw in low for kw in posh_pocso_terms):
            return False

        return True

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
            category = "OTHER"

        sub_category = self._determine_sub_category(narrative, category)

        return ClassificationResult(
            category=category,
            sub_category=sub_category if category != "OTHER" else "General / Non-Sexual Interaction",
            confidence=0.98,
            minor_involved=minor_involved,
            rationale=f"Classified as {category} based on statutory legal scope (Sexual Harassment: {has_sexual}, Workplace: {has_workplace}, Minor: {minor_involved})."
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

    def _extract_facts_via_llm(self, text: str) -> Dict[str, Any]:
        """Invoke Ollama in JSON mode for LLM-based structured fact extraction using strict compliance guidelines."""
        system_prompt = (
            "You are a strict legal fact-extraction assistant specializing in POSH and POCSO cases. "
            "Extract facts ONLY from the text provided. Do NOT invent, infer, or add any information not "
            "explicitly stated. Return results in flat JSON.\n\n"
            "EXTRACTION RULES (apply to BOTH POSH and POCSO):\n"
            "1. 'respondent_name': Extract the name of the person performing the alleged misconduct. "
            "Search near phrases like 'against', 'Mr./Ms./Dr.', 'named', 'called', 'my manager/supervisor/teacher'. "
            "If no name is given but a role IS mentioned (e.g. 'Associate Director'), set name to "
            "'[Name Withheld / Unknown - <Role>]' substituting the actual role. Only return null if absolutely "
            "no respondent information exists.\n"
            "2. 'respondent_designation': Extract the EXACT title/role from the narrative (e.g. 'Associate Director', "
            "'Senior Teacher', 'Bus Driver'). Do not generalize. Return null if not mentioned.\n"
            "3. 'incident_date': Extract the FULL date with year when available (e.g. 'October 12, 2026', "
            "'18 July 2026'). Also capture the specific time if stated alongside (e.g. 'at approximately 4:30 PM IST'). "
            "Do NOT substitute the current execution date. Append '(year unspecified)' if year is missing. "
            "Return null only if no date reference exists.\n"
            "4. 'incident_time': Extract the EXACT clock time stated (e.g. '4:30 PM IST', '3:30 PM'). Also accept "
            "qualitative windows: 'lunch break', 'after office hours', 'morning standup', 'during commute', "
            "'midnight', 'late evening', 'end of day'. Return null only if no time reference exists.\n"
            "5. 'incident_location': Extract the FULL location hierarchy from the narrative — include Room/Area, "
            "Floor, Building/Company name, and City if all are mentioned (e.g. 'Conference Room B, 3rd Floor, "
            "TechSolutions Pvt. Ltd., Mumbai'). Do NOT truncate to just the company name. Only return null if "
            "absolutely no location information exists.\n"
            "6. 'nature_of_incident': Write a factual 2-4 sentence summary using ONLY acts explicitly described "
            "in the input. Include verbatim quotes from the narrative where possible. NEVER add standardized "
            "boilerplate claims (e.g. do NOT add 'display of explicit material' unless the input explicitly states it). "
            "Name the specific acts (e.g. 'unwanted physical touching', 'verbal sexual remarks', "
            "'quid pro quo demand for sexual favours'). Reference applicable statutory sections where relevant "
            "(PoSH Act Sec 2(n), POCSO Act Sec 7/11). Include perpetrator context and impact.\n"
            "7. 'witnesses': Extract every person who was present, saw, or heard the incident — even if the word "
            "'witness' is not used. Look for: 'was present', 'was there', 'saw it', 'heard this', 'along with [Name]', "
            "'in front of [Name]', '[Name] also noticed', '[Name] saw/heard'. For each witness, capture their "
            "name, title/role, and relevance in the format 'Name | Role | What they observed'. "
            "Example: 'Tanya Sharma | Senior Quality Analyst | Observed physical conduct in room'. "
            "Return [] only if no third party is mentioned.\n"
            "8. 'evidence_description': List every artifact explicitly cited (e.g. 'swipe logs from Oct 12', "
            "'timestamped Slack screenshots', 'CCTV footage', 'call records'). List each item separately. "
            "Return [] if none mentioned.\n\n"
            "JSON Format:\n"
            "{\n"
            '  "complainant_name": "Name of complainant or null",\n'
            '  "complainant_age": "Age/DOB or null",\n'
            '  "respondent_name": "Exact name, or \'[Name Withheld / Unknown - <Role>]\', or null",\n'
            '  "respondent_designation": "Exact title/role from narrative or null",\n'
            '  "incident_date": "Full date with year and time if stated (e.g. \'October 12, 2026, at approximately 4:30 PM IST\') or null",\n'
            '  "incident_time": "Clock time or qualitative window or null",\n'
            '  "incident_location": "Full hierarchy: Room, Floor, Building/Company, City or null",\n'
            '  "nature_of_incident": "Grounded factual summary with verbatim quotes, specific acts only (2-4 sentences)",\n'
            '  "witnesses": ["Name | Role | What they observed (one entry per witness)"],\n'
            '  "evidence_description": ["Each artifact cited in the narrative"]\n'
            "}"
        )
        try:
            raw_response = self._call_ollama(f"Text:\n\"\"\"{text}\"\"\"", system_prompt=system_prompt, json_mode=True)
            if raw_response:
                data = json.loads(raw_response)
                if isinstance(data, dict):
                    mapped = {}
                    
                    # Detect flat JSON output format
                    is_flat = any(k in data for k in ["complainant_name", "respondent_name", "nature_of_incident"])
                    
                    if is_flat:
                        mapped["complainant_name"] = data.get("complainant_name")
                        mapped["complainant_age"] = data.get("complainant_age")
                        mapped["respondent_name"] = data.get("respondent_name")
                        mapped["respondent_designation"] = data.get("respondent_designation")
                        mapped["incident_date"] = data.get("incident_date")
                        mapped["incident_time"] = data.get("incident_time")
                        mapped["incident_location"] = data.get("incident_location")
                        mapped["nature_of_incident"] = data.get("nature_of_incident")
                        
                        wit = data.get("witnesses")
                        if isinstance(wit, list):
                            mapped["witnesses"] = wit
                        elif isinstance(wit, str) and wit.strip():
                            mapped["witnesses"] = [w.strip() for w in wit.split(",") if w.strip()]
                        else:
                            mapped["witnesses"] = []
                        
                        ev = data.get("evidence_description") or data.get("evidence_mentioned")
                        if isinstance(ev, list):
                            mapped["evidence_description"] = ev
                        elif isinstance(ev, str) and ev.strip():
                            mapped["evidence_description"] = [e.strip() for e in ev.split(",") if e.strip()]
                        else:
                            mapped["evidence_description"] = []
                    else:
                        # Legacy nested schema parser fallback
                        comp = data.get("complainant", {}) or {}
                        victim = data.get("victim", {}) or {}
                        resp = data.get("respondent", {}) or {}
                        org = data.get("organization", {}) or {}
                        details = data.get("incident_details", {}) or {}
                        
                        comp_name = comp.get("name")
                        if not comp_name:
                            comp_name = victim.get("name")
                        mapped["complainant_name"] = comp_name
                        mapped["complainant_age"] = victim.get("age") or comp.get("age")
                        
                        resp_name = resp.get("name")
                        resp_role = resp.get("role_or_designation")
                        mapped["respondent_name"] = resp_name if resp_name else ("Unknown" if resp_role else None)
                        mapped["respondent_designation"] = resp_role

                        mapped["incident_date"] = details.get("date")
                        mapped["incident_time"] = details.get("time")
                        
                        loc = details.get("location")
                        org_name = org.get("name")
                        if loc and org_name and org_name.lower() not in loc.lower():
                            mapped["incident_location"] = f"{loc}, {org_name}"
                        elif loc:
                            mapped["incident_location"] = loc
                        else:
                            mapped["incident_location"] = org_name

                        mapped["nature_of_incident"] = details.get("nature_of_incident_summary")

                        wit = details.get("witnesses")
                        if isinstance(wit, list):
                            mapped["witnesses"] = wit
                        elif isinstance(wit, str) and wit.strip():
                            mapped["witnesses"] = [w.strip() for w in wit.split(",") if w.strip()]
                        else:
                            mapped["witnesses"] = []

                        ev = details.get("evidence_mentioned")
                        if isinstance(ev, list):
                            mapped["evidence_description"] = ev
                        elif isinstance(ev, str) and ev.strip():
                            mapped["evidence_description"] = [e.strip() for e in ev.split(",") if e.strip()]
                        else:
                            mapped["evidence_description"] = []

                    return mapped
        except Exception as e:
            print(f"LLM fact extraction fallback triggered: {e}")
        return {}

    def _postprocess_and_regex_fallback(self, text: str, facts: Dict[str, Any]) -> ExtractedFacts:
        """Apply normalization, title casing, regex fallbacks, and validations to extracted facts."""
        
        def _to_str(val):
            if isinstance(val, list):
                return ", ".join(str(v) for v in val if v)
            if val is not None:
                s = str(val).strip()
                if s.lower() not in ["", "null", "none", "not provided", "unspecified", "not specified", "not mentioned", "none specified", "none provided", "[not provided / unspecified]"]:
                    return s
            return None

        # 1. Complainant Name
        comp_name = _to_str(facts.get("complainant_name"))
        if not comp_name:
            comp_patterns = [
                r'\b(?:complainant(?:\s+name)?(?:\s+is)?|name is|i am|my name is|my name|this is)\s*[:\-]?\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,2})',
                r'\b([A-Za-z]+(?:\s+[A-Za-z]+){1,2})\s*,\s*(?:phone|email|age|an employee|working as|hereby)\b',
            ]
            for pat in comp_patterns:
                comp_match = re.search(pat, text, re.IGNORECASE)
                if comp_match:
                    cand = comp_match.group(1).strip()
                    # Strip any trailing stopwords that were caught by {1,2}
                    cand = re.sub(r'\s+(?:my|who|and|at|the|is|was|on|in)$', '', cand, flags=re.IGNORECASE).strip().title()
                    cand_low = cand.lower()
                    if cand_low not in ("my manager", "the manager", "my supervisor", "a complaint", "harassment", "formal complaint") and len(cand) > 1:
                        comp_name = cand
                        break
        else:
            comp_name = re.sub(r'\s+(?:my|who|and|at|the|is|was|on|in)$', '', comp_name, flags=re.IGNORECASE).strip().title()

        # 2. Complainant Age
        comp_age = _to_str(facts.get("complainant_age"))
        if comp_age:
            if "under 18" in comp_age.lower() or "minor" in comp_age.lower():
                comp_age = "Under 18 (Minor)"
            elif "18 or above" in comp_age.lower() or "adult" in comp_age.lower():
                comp_age = "18 or Above (Adult)"

        # 3. Respondent Designation
        resp_desig = _to_str(facts.get("respondent_designation"))
        if not resp_desig:
            desig_match = re.search(r'\b(?:my|the)\s+(team lead|manager|supervisor|boss|colleague|bus driver|teacher|principal|doctor|colleague|director)\b', text, re.IGNORECASE)
            if desig_match:
                resp_desig = desig_match.group(1).title()
        else:
            resp_desig = resp_desig.strip().title()

        # 4. Respondent Name — Rule 1 & 2: use [Name Withheld / Unknown - Role] when name absent but role known
        resp_name = _to_str(facts.get("respondent_name"))
        _EXCLUDED_RESP_WORDS = {"at", "in", "on", "sexual", "harass", "harassed", "harassing", "unknown", "the", "my", "a", "an", "hanuai"}
        if not resp_name:
            resp_match = re.search(r'\b(?:against|accused|respondent|mr\.?|ms\.?|dr\.?|named|called)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', text, re.IGNORECASE)
            if resp_match:
                cand = resp_match.group(1).strip().title()
                first_w = cand.lower().split()[0]
                if first_w not in _EXCLUDED_RESP_WORDS and cand.lower() not in _EXCLUDED_RESP_WORDS:
                    resp_name = cand
            if not resp_name:
                resp_match2 = re.search(r'\b(?:supervisor|manager|team lead|boss|colleague)\s*,\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)', text, re.IGNORECASE)
                if resp_match2:
                    cand = resp_match2.group(1).strip().title()
                    first_w = cand.lower().split()[0]
                    if first_w not in _EXCLUDED_RESP_WORDS and cand.lower() not in _EXCLUDED_RESP_WORDS:
                        resp_name = cand
        else:
            # Strip designation bleed-over from LLM output
            if resp_desig:
                desig_lower = resp_desig.lower()
                resp_name = re.sub(rf',\s*(?:my|the\s+)?{re.escape(desig_lower)}', '', resp_name, flags=re.IGNORECASE).strip()
                resp_name = re.sub(rf'\s*\(\s*(?:my|the\s+)?{re.escape(desig_lower)}\s*\)', '', resp_name, flags=re.IGNORECASE).strip()
                for word in desig_lower.split():
                    if len(word) > 2:
                        resp_name = re.sub(rf',\s*(?:my|the\s+)?{re.escape(word)}[a-z]*', '', resp_name, flags=re.IGNORECASE).strip()

            resp_name = re.sub(rf',\s*(?:my|the\s+)?(?:manager|supervisor|team lead|driver|teacher|colleague|boss|employee|accused|respondent).*$', '', resp_name, flags=re.IGNORECASE).strip()

            if resp_name.lower() not in ["unknown", "not mentioned", "not provided"]:
                resp_name = resp_name.title()

        # Rule 2: If name absent or starts with preposition/unknown but designation known → structured placeholder
        if (not resp_name or resp_name.lower() in ["unknown", "not provided", "name withheld"] or resp_name.lower().startswith("at ")):
            if resp_desig:
                resp_name = f"[Name Withheld / Unknown - {resp_desig.title()}]"
            else:
                resp_name = "Unknown"

        # 5. Incident Date — always capture full date with year (req 2)
        inc_date = _to_str(facts.get("incident_date"))
        if not inc_date:
            # Try full date with year first (e.g. "5 oct 2026", "18 July 2026", "Oct 12, 2026", "12/10/2026")
            date_match = re.search(
                r'\b(\d{1,2}[\s/-]+[A-Za-z]+[\s/-]+\d{2,4}'
                r'|[A-Za-z]+[\s/-]+\d{1,2}[,\s/-]+\d{4}'
                r'|\d{1,2}/\d{1,2}/\d{2,4}'
                r'|\d{4}-\d{2}-\d{2})\b',
                text, re.IGNORECASE
            )
            if date_match:
                inc_date = date_match.group(1).strip()
            else:
                # Partial date without year (e.g. "Oct 12", "18 July")
                partial = re.search(
                    r'\b(?:on|date|during|since)\s+'
                    r'((?:\d{1,2}\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
                    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
                    r'(?:\s+\d{1,2})?)',
                    text, re.IGNORECASE
                )
                if partial:
                    inc_date = partial.group(1).strip() + " (year unspecified)"
                else:
                    # Relative references
                    rel = re.search(
                        r'\b(yesterday|last\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|week|month))\b',
                        text, re.IGNORECASE
                    )
                    inc_date = rel.group(1).title() if rel else None
        else:
            # Normalise LLM-returned date — preserve year if already present
            inc_date = re.sub(r'\(year unspecified\)', '(year unspecified)', inc_date.strip())
            # Title-case only the textual parts, keep digits and punctuation
            inc_date = re.sub(
                r'([A-Za-z]+)',
                lambda m: m.group(1).capitalize(),
                inc_date
            )

        # 6. Incident Time — qualitative windows accepted (req 2)
        _QUALITATIVE_TIMES = [
            "lunch break", "during lunch", "lunch hour",
            "after office hours", "after-hours", "after hours",
            "morning standup", "morning stand-up", "morning meeting",
            "during the commute", "during commute", "commute",
            "midnight", "late evening", "late night", "end of day",
            "early morning", "before office hours", "after work",
            "during break", "tea break", "post work",
        ]
        inc_time = _to_str(facts.get("incident_time"))
        if not inc_time:
            # Exact clock time
            time_match = re.search(
                r'\b(?:at|around|approximately|~)?\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\b',
                text, re.IGNORECASE
            )
            if time_match:
                inc_time = time_match.group(1).upper()
            else:
                # Qualitative window — search longest first to avoid partial matches
                for qt in sorted(_QUALITATIVE_TIMES, key=len, reverse=True):
                    if re.search(re.escape(qt), text, re.IGNORECASE):
                        inc_time = qt.title()
                        break
        else:
            # If LLM returned a qualitative phrase, preserve it; if clock time, upper-case it
            if re.search(r'\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)', inc_time):
                inc_time = inc_time.upper()
            else:
                inc_time = inc_time.strip()  # preserve qualitative as-is

        # 7. Incident Location — Rule 3: capture full hierarchy (Room, Floor, Building, City)
        inc_loc = _to_str(facts.get("incident_location"))
        if not inc_loc:
            # Try full hierarchy: "Room X, Floor Y, Company Z, City"
            hierarchy_match = re.search(
                r'\b([A-Za-z0-9\s,]+(?:room|floor|cabin|hall|office|canteen|cafeteria|classroom|building|premises)[A-Za-z0-9\s,]*)',
                text, re.IGNORECASE
            )
            if hierarchy_match:
                inc_loc = hierarchy_match.group(1).strip()
            else:
                org_match = re.search(r'\b([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*\s+(?:Private Limited|Pvt\.? Ltd\.?|Limited|Ltd\.?|Inc\.?|Corporation|Co\.?|School|College|University|Hospital|Office))\b', text, re.IGNORECASE)
                if org_match:
                    inc_loc = org_match.group(1).strip().title()
                else:
                    loc_match = re.search(r'\b(?:at|in)\s+(?:the\s+)?([A-Za-z0-9\s]+(?:office|meeting room|workplace|building|site|cabin|canteen|online|premises|desk|conference room|pantry|cafeteria|classroom|park|street))', text, re.IGNORECASE)
                    if loc_match:
                        inc_loc = loc_match.group(1).strip().title()
                    else:
                        # Simple preposition match: "at Hanuai", "in Noida"
                        simple_prep = re.search(r'\b(?:at|in)\s+([A-Za-z0-9]{3,25})\b', text, re.IGNORECASE)
                        if simple_prep:
                            cand_loc = simple_prep.group(1).strip().title()
                            if cand_loc.lower() not in ("night", "work", "home", "meeting", "the", "that", "this"):
                                inc_loc = cand_loc
        # Do NOT call .title() on multi-part hierarchy — preserve casing from narrative
        if inc_loc:
            inc_loc = re.sub(r'^(?:the|a|an|at|in)\s+', '', inc_loc, flags=re.IGNORECASE).strip()
            # Fix common acronym casing issues only
            inc_loc = re.sub(r'\bHr\b', 'HR', inc_loc)
            inc_loc = re.sub(r'\bSjpu\b', 'SJPU', inc_loc, flags=re.IGNORECASE)

        # 8. Witnesses — broad extraction including implicit presence cues (req 1)
        witnesses = []
        wit_val = facts.get("witnesses")
        if isinstance(wit_val, list):
            witnesses = [str(w).strip() for w in wit_val if w]
        elif isinstance(wit_val, str) and wit_val.strip():
            witnesses = [w.strip() for w in wit_val.split(",") if w.strip()]

        if not witnesses:
            # Pattern 0: Direct witness statement e.g. "witness is Harish", "witnesses: Priya, Rahul"
            wit_direct = re.search(
                r'\b(?:witness(?:es)?(?:\s+is|\s+are|\s*:)?)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
                text, re.IGNORECASE
            )
            if wit_direct:
                cand = wit_direct.group(1).strip().title()
                if cand.lower() not in ("not", "none", "no", "unknown", "the", "present"):
                    witnesses = [cand]

        if not witnesses:
            # Pattern A: explicit named witness pairs/lists ("colleagues Priya and Rahul", "witnessed by Anjali, Deepak")
            wit_match_names = re.search(
                r'\b(?:witnessed by|in presence of|in front of|along with|with|colleagues?|co-workers?)\s+'
                r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+|\s*,\s*[A-Z][a-z]+)+)',
                text
            )
            if wit_match_names:
                names_str = wit_match_names.group(1)
                witnesses = [w.strip().title() for w in re.split(r'\band\b|&|,', names_str) if w.strip()]

        if not witnesses:
            # Pattern B: group descriptors ("in front of three colleagues", "saw by HR staff")
            wit_match_group = re.search(
                r'\b(?:in front of|witnessed by|saw|observed by|in presence of|noticed by)\s+'
                r'(?:the\s+)?(\d+|two|three|four|five|several|some|a few|many|other)?\s*'
                r'(team members?|colleagues?|co-workers?|employees?|HR manager|HR staff|'
                r'supervisor|bystanders?|staff|people|persons?|others?)\b',
                text, re.IGNORECASE
            )
            if wit_match_group:
                qty   = (wit_match_group.group(1) or "").strip()
                group = wit_match_group.group(2).strip().title()
                witnesses = [(f"{qty.title()} {group}").strip() if qty else group]

        if not witnesses:
            # Pattern C: subject-verb — "[Name] witnessed", "[Name] saw", "[Name] heard"
            wit_subj = re.search(
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:witnessed|saw|observed|heard|noticed)\b',
                text
            )
            if wit_subj:
                subj = re.sub(r'^(?:the|a|my|our)\s+', '', wit_subj.group(1), flags=re.IGNORECASE).strip().title()
                if subj.lower() not in ("i", "he", "she", "they", "we", "complainant", "victim", "respondent"):
                    witnesses = [subj]

        if not witnesses:
            # Pattern D: implicit presence — "along with [Name]", "[Name] was present/was there",
            #             "in front of [Name]", "[Name] also saw/heard"
            implicit_patterns = [
                r'\balong with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+was\s+(?:also\s+)?(?:present|there)\b',
                r'\bin front of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:also\s+)?(?:saw|heard|noticed|overheard)\b',
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+was\s+(?:also\s+)?(?:a\s+)?witness\b',
            ]
            for pat in implicit_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    candidate = m.group(1).strip().title()
                    if candidate.lower() not in ("i", "he", "she", "they", "we",
                                                 "complainant", "victim", "respondent"):
                        witnesses = [candidate]
                        break

        # De-duplicate, normalise casing, clean pipe delimiters, exclude complainant/respondent
        _HR_FIXES = {"Hr Manager": "HR Manager", "Hr Staff": "HR Staff", "Sjpu": "SJPU"}
        cleaned_witnesses = []
        seen = set()
        for w in witnesses:
            w_str = _to_str(w)
            if not w_str or w_str.lower() in ("none", "none specified", "null"):
                continue
            # If formatted as "Name | Role | Details", isolate the name
            if "|" in w_str:
                w_str = w_str.split("|")[0].strip()
            w_title = w_str.title()
            for wrong, right in _HR_FIXES.items():
                w_title = w_title.replace(wrong, right)
            exclude = [x.lower() for x in (comp_name, resp_name) if x]
            if w_title.lower() not in exclude and w_title.lower() not in seen and len(w_title) > 1:
                cleaned_witnesses.append(w_title)
                seen.add(w_title.lower())
        witnesses = cleaned_witnesses

        # 9. Nature of incident — Rule 5: grounded only; no boilerplate injection
        _GENERIC_STUBS = {
            "workplace harassment", "alleged incident of workplace harassment",
            "sexual harassment", "alleged sexual harassment",
            "inappropriate behaviour", "inappropriate behavior",
            "unspecified incident description", "incident of harassment",
        }
        nature_summary = _to_str(facts.get("nature_of_incident"))
        if nature_summary:
            # Strip conversational openers
            nature_summary = re.sub(
                r'^(?:my name is|i am|this is|hi|hello)\s+[A-Za-z]+(?:\s+[A-Za-z]+)?\.?\s*',
                '', nature_summary, flags=re.IGNORECASE
            ).strip()
            # Reject if the cleaned summary is still a generic stub
            if nature_summary.lower().rstrip('.') in _GENERIC_STUBS:
                nature_summary = None
            elif nature_summary:
                nature_summary = nature_summary[0].upper() + nature_summary[1:]
        if not nature_summary:
            # Rule 5: Only add acts that are explicitly present in the text — no boilerplate
            acts_found = []
            low = text.lower()
            if any(k in low for k in ["touch", "physical", "grab", "grope", "hug", "fondle"]):
                acts_found.append("unwanted physical contact")
            if any(k in low for k in ["comment", "remark", "joke", "say", "said", "tell", "told", "verbal"]):
                acts_found.append("verbal remarks of a sexual nature")
            if any(k in low for k in ["message", "whatsapp", "text", "email", "send", "sent"]):
                acts_found.append("unsolicited sexual messages")
            # Rule 5: ONLY add 'display of explicit material' if EXPLICITLY stated in text
            if any(k in low for k in ["explicit material", "showed explicit", "displayed explicit", "pornograph", "csam"]):
                acts_found.append("display of explicit material")
            if any(k in low for k in ["promise", "promotion", "appraisal", "favour", "threat", "quid pro quo"]):
                acts_found.append("quid pro quo demands")
            if acts_found:
                nature_summary = (
                    f"The complainant alleges {', and '.join(acts_found)} by the respondent "
                    f"constituting sexual harassment as defined under the applicable Act."
                )
            else:
                # Minimal non-boilerplate fallback — no invented claims
                nature_summary = (
                    "The complainant alleges conduct by the respondent constituting sexual harassment "
                    "as defined under the applicable Act. Specific details of the alleged acts are "
                    "as described in the complainant's narrative."
                )

        # 10. Evidence description
        evidence = []
        ev_val = facts.get("evidence_description")
        if isinstance(ev_val, list):
            evidence = [str(e).strip() for e in ev_val if e]
        elif isinstance(ev_val, str) and ev_val.strip():
            evidence = [ev_val.strip()]
        
        cleaned_evidence = []
        for e in evidence:
            e_str = _to_str(e)
            if e_str and e_str.lower() not in ["none", "none provided", "null"]:
                cleaned_evidence.append(e_str[0].upper() + e_str[1:])
        evidence = cleaned_evidence

        return ExtractedFacts(
            complainant_name=comp_name if comp_name and comp_name.lower() not in ("unknown", "not provided") else None,
            complainant_age=comp_age if comp_age and comp_age.lower() not in ("unknown", "not provided") else None,
            respondent_name=resp_name if resp_name and resp_name.lower() not in ("unknown", "not provided") else None,
            respondent_designation=resp_desig if resp_desig and resp_desig.lower() not in ("unknown", "not provided") else None,
            incident_date=inc_date if inc_date and inc_date.lower() not in ("unknown", "not provided") else None,
            incident_time=inc_time if inc_time and inc_time.lower() not in ("unknown", "not provided") else None,
            incident_location=inc_loc if inc_loc and inc_loc.lower() not in ("unknown", "not provided") else None,
            nature_of_incident=nature_summary,
            witnesses=[w for w in witnesses if w and w.lower() not in ("none", "none specified", "none mentioned", "not provided")],
            evidence_description=[e for e in evidence if e and e.lower() not in ("none", "none mentioned", "none provided", "not provided")]
        )

    def extract_facts_from_chat(self, messages: List[Dict[str, str]]) -> ExtractedFacts:
        """Extract structured facts across chat dialogue pairing + LLM JSON fallback."""
        user_msgs = [m['content'].strip() for m in messages if m['role'] == 'user']
        full_text = " ".join(user_msgs)

        complainant_name = None
        complainant_age = None
        respondent_name = None
        respondent_designation = None
        incident_date = None
        incident_time = None
        incident_location = None
        nature_of_incident = None
        witnesses = []
        evidence_description = []

        # Age group detection
        for u in user_msgs:
            if "under 18" in u.lower() or "minor" in u.lower():
                complainant_age = "Under 18 (Minor)"
            elif "18 or above" in u.lower() or "adult" in u.lower():
                complainant_age = "18 or Above (Adult)"

        # Dialogue turn pairing
        for i in range(len(messages)):
            msg = messages[i]
            if msg['role'] == 'user' and i > 0 and messages[i-1]['role'] == 'assistant':
                prev_asst = messages[i-1]['content'].lower()
                u_content = msg['content'].strip()
                u_low = u_content.lower()

                if u_low in ["hello", "hi", "hey", "namaste", "help", "18 or above", "under 18"]:
                    continue

                if "tell me your name" in prev_asst or "what is your name" in prev_asst:
                    name_clean = re.sub(r'^(my name is|i am|this is)\s+', '', u_content, flags=re.IGNORECASE).strip()
                    if name_clean and name_clean.lower() not in ["hi", "hello", "help"]:
                        complainant_name = name_clean.title()

                elif "person involved" in prev_asst or "accused" in prev_asst or "how you know the person" in prev_asst or "job role of the person" in prev_asst:
                    if not any(neg in u_low for neg in ["no", "none", "don't know", "dont know", "not sure", "refuse", "n/a", "withheld"]):
                        resp_clean = re.sub(r'^(accused is|respondent is|it was|by|mr|ms|dr)\s+', '', u_content, flags=re.IGNORECASE).strip()
                        if resp_clean:
                            respondent_name = resp_clean.title()

                elif "where this happened" in prev_asst or "where this incident took place" in prev_asst or "where" in prev_asst:
                    if not any(neg in u_low for neg in ["no", "none", "not sure", "n/a"]):
                        loc_clean = re.sub(r'^(it happened at|at|in|located at)\s+', '', u_content, flags=re.IGNORECASE).strip()
                        if loc_clean:
                            incident_location = loc_clean.title()

                elif "when did this happen" in prev_asst or "date" in prev_asst:
                    if not any(neg in u_low for neg in ["no", "none", "not sure", "don't know", "n/a"]):
                        date_clean = re.sub(r'^(it happened on|on|during|in)\s+', '', u_content, flags=re.IGNORECASE).strip()
                        if date_clean:
                            incident_date = date_clean.title()

                elif "evidence" in prev_asst:
                    if any(neg in u_low for neg in ["no", "none", "no, nothing", "nah", "nope", "n/a"]):
                        evidence_description = []
                    elif u_low not in ["yes", "yeah", "yep", "sure"]:
                        evidence_description = [u_content]

                elif "specify what kind of evidence" in prev_asst:
                    if not any(neg in u_low for neg in ["no", "none", "n/a"]):
                        evidence_description = [u_content]

                elif "witnessed" in prev_asst or "witness" in prev_asst:
                    if any(neg in u_low for neg in ["no", "none", "nobody", "no one", "nah", "nope", "n/a"]):
                        witnesses = []
                    elif u_low not in ["yes", "yeah", "yep", "sure"]:
                        witnesses = [u_content]

                elif "share their names" in prev_asst:
                    if not any(neg in u_low for neg in ["no", "none", "n/a"]):
                        witnesses = [u_content]

                elif ("take your time and share what happened" in prev_asst or 
                      "share what happened" in prev_asst or 
                      "tell me a little more" in prev_asst):
                    if u_content and not nature_of_incident:
                        nature_of_incident = u_content

        llm_facts = {}
        if len(full_text.strip()) >= 30:
            keywords = ["harass", "abuse", "assault", "touch", "remark", "inappropriate", "incident", "happened", "office", "workplace", "school", "pocso", "posh", "minor", "child"]
            if any(k in full_text.lower() for k in keywords) or len(full_text.strip()) > 80:
                llm_facts = self._extract_facts_via_llm(full_text)

        merged_facts = {
            "complainant_name": complainant_name or llm_facts.get("complainant_name"),
            "complainant_age": complainant_age or llm_facts.get("complainant_age"),
            "respondent_name": respondent_name or llm_facts.get("respondent_name"),
            "respondent_designation": respondent_designation or llm_facts.get("respondent_designation"),
            "incident_date": incident_date or llm_facts.get("incident_date"),
            "incident_time": incident_time or llm_facts.get("incident_time"),
            "incident_location": incident_location or llm_facts.get("incident_location"),
            "nature_of_incident": nature_of_incident or llm_facts.get("nature_of_incident"),
            "witnesses": witnesses or llm_facts.get("witnesses") or [],
            "evidence_description": evidence_description or llm_facts.get("evidence_description") or []
        }

        return self._postprocess_and_regex_fallback(full_text, merged_facts)

    def extract_facts(self, narrative: str) -> ExtractedFacts:
        """Extract facts for direct narrative text using high-accuracy LLM JSON extraction + regex fallback."""
        llm_facts = self._extract_facts_via_llm(narrative)
        return self._postprocess_and_regex_fallback(narrative, llm_facts)

    def format_standard_template(
        self,
        category: str,
        facts: ExtractedFacts
    ) -> str:
        """Format facts into the strict 8-section FORMAL COMPLAINT FORM layout."""
        current_date_str = date.today().strftime("%B %d, %Y")

        comp_name = facts.complainant_name or "[Not Provided / Unspecified]"
        comp_age = facts.complainant_age or "[Not Provided / Unspecified]"
        resp_name = facts.respondent_name or "[Not Provided / Unspecified]"
        resp_desig = facts.respondent_designation or "[Not Provided / Unspecified]"
        inc_date = facts.incident_date or "[Not Provided / Unspecified]"
        inc_time = facts.incident_time or "[Not Provided / Unspecified]"
        inc_loc = facts.incident_location or "[Not Provided / Unspecified]"
        narrative = facts.nature_of_incident or "[Provide a factual, detailed narrative of what transpired based on user inputs]"
        
        witnesses_str = ", ".join(facts.witnesses) if facts.witnesses else "[None Specified]"
        evidence_str = ", ".join(facts.evidence_description) if facts.evidence_description else "[None Provided]"

        if inc_time and inc_time != "[Not Provided / Unspecified]" and inc_time.lower() not in ["not provided", "none", "null", "not mentioned", "unknown"]:
            inc_date_time = f"{inc_date} at {inc_time}" if inc_date != "[Not Provided / Unspecified]" else inc_time
        else:
            inc_date_time = inc_date

        if category == "POSH":
            framework_str = "POSH Act 2013"
        elif category == "POCSO":
            framework_str = "POCSO Act 2012 (Subject to Mandatory Reporting under Section 19)"
        elif category == "BOTH":
            framework_str = "POSH Act 2013 / POCSO Act 2012 (Subject to Mandatory Reporting under Section 19)"
        else:
            framework_str = "POSH Act 2013 / POCSO Act 2012"

        # Note: the raw template string is used only as a data-transmission medium
        # to the DOCX exporter which applies all real formatting.  Avoid ==== lines,
        # mixed-Act references, and duplicate titles here.
        return (
            f"Formal Complaint under the {framework_str}\n\n"
            f"Date of Submission: {current_date_str}\n\n"
            "1. Complainant Details:\n"
            f"   Full Name: {comp_name}\n"
            f"   Age: {comp_age}\n\n"
            "2. Respondent Details:\n"
            f"   Full Name: {resp_name}\n"
            f"   Designation: {resp_desig}\n\n"
            "3. Incident Details:\n"
            f"   Date/Time: {inc_date_time}\n"
            f"   Location: {inc_loc}\n\n"
            "4. Description:\n"
            f"   {narrative}\n\n"
            "5. Witnesses:\n"
            f"   {witnesses_str}\n\n"
            "6. Evidence:\n"
            f"   {evidence_str}\n\n"
            "7. Declaration:\n"
            "   The information above is true and correct to the best of my knowledge."
        )


    def generate_draft(self, category: str, facts: ExtractedFacts, contexts: List[RetrievedContext]) -> ComplaintDraft:
        """Generate formal complaint draft with fixed standard template."""
        formatted_template = self.format_standard_template(category, facts)

        # Rule 1: Use extracted org name in addressed_to instead of static placeholder
        org_name = None
        if facts.incident_location:
            # Try to extract org name from full location hierarchy
            org_match = re.search(
                r'([A-Z][A-Za-z0-9\s]*(?:Pvt\.?\s*Ltd\.?|Private Limited|Limited|Ltd\.?|Inc\.?|Corp\.?|School|College|University|Hospital|Solutions|Technologies|Services|Consultancy|Foundation))',
                facts.incident_location
            )
            if org_match:
                org_name = org_match.group(1).strip()

        if category == "POSH":
            if org_name:
                addressed_to = f"The Presiding Officer, Internal Committee (IC), {org_name}"
            else:
                addressed_to = "The Presiding Officer, Internal Committee (IC), [Organization Name]"
        elif category == "POCSO":
            addressed_to = "The Officer-in-Charge, Special Juvenile Police Unit (SJPU) / Local Police Station"
        else:
            addressed_to = "The Appropriate Authority"

        disclaimer = (
            "DISCLAIMER: This complaint draft was generated using artificial intelligence (AI) based on the input provided. "
            "It is intended only as a drafting aid and does not constitute formal legal advice. Please review the details carefully "
            "and consult with a qualified legal professional or your organization's compliance officer before final submission."
        )

        return ComplaintDraft(
            category=category,
            addressed_to=addressed_to,
            draft_text=formatted_template,
            disclaimer=disclaimer,
            citations=contexts,
            facts=facts,
        )

    def build_agent_response_payload(
        self,
        is_relevant: bool,
        action_triggered: str,
        advice_response: str,
        facts: ExtractedFacts,
        formatted_draft: str = ""
    ) -> AgentResponsePayload:
        """Construct structured JSON response matching exact frontend schema requirements."""
        if not is_relevant:
            return AgentResponsePayload(
                is_posh_pocso_relevant=False,
                action_triggered=action_triggered if action_triggered in ["ADVISE", "GENERATE_DRAFT"] else "ADVISE",
                ui_state=UIState(expand_draft_view=False, close_chat_tab=False),
                advice_response=OUT_OF_SCOPE_MESSAGE,
                extracted_entities=ExtractedEntities(),
                formatted_draft=""
            )

        expand_view = (action_triggered == "GENERATE_DRAFT")
        close_chat = (action_triggered == "GENERATE_DRAFT")

        entities = ExtractedEntities(
            complainant_name=facts.complainant_name or "[Not Provided / Unspecified]",
            complainant_age=facts.complainant_age or "[Not Provided / Unspecified]",
            respondent_name=facts.respondent_name or "[Not Provided / Unspecified]",
            respondent_designation=facts.respondent_designation or "[Not Provided / Unspecified]",
            date_of_incident=facts.incident_date or "[Not Provided / Unspecified]",
            time_of_incident=facts.incident_time or "[Not Provided / Unspecified]",
            place_of_incident=facts.incident_location or "[Not Provided / Unspecified]",
            witnesses=", ".join(facts.witnesses) if facts.witnesses else "[None Specified]",
            evidence=", ".join(facts.evidence_description) if facts.evidence_description else "[None Provided]"
        )

        return AgentResponsePayload(
            is_posh_pocso_relevant=True,
            action_triggered="GENERATE_DRAFT" if expand_view else "ADVISE",
            ui_state=UIState(
                expand_draft_view=expand_view,
                close_chat_tab=close_chat
            ),
            advice_response=advice_response,
            extracted_entities=entities,
            formatted_draft=formatted_draft
        )
