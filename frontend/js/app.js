document.addEventListener("DOMContentLoaded", () => {
    // Determine backend URL (fallback to localhost if opened as file://)
    const BASE_URL = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

    // DOM Elements
    const ingestBtn = document.getElementById("ingest-btn");
    const ingestStatus = document.getElementById("ingest-status");
    
    // Mode toggling
    const modeChatBtn = document.getElementById("mode-chat-btn");
    const modeTextBtn = document.getElementById("mode-text-btn");
    const chatModeView = document.getElementById("chat-mode-view");
    const textModeView = document.getElementById("text-mode-view");

    // Chat DOM Elements
    const chatMessagesList = document.getElementById("chat-messages-list");
    const quickRepliesWrapper = document.getElementById("quick-replies-wrapper");
    const quickRepliesBar = document.getElementById("quick-replies-bar");
    const welcomeChipsWrapper = document.getElementById("welcome-chips-wrapper");
    const ageSelectWrapper = document.getElementById("age-select-wrapper");
    const genderSelectWrapper = document.getElementById("gender-select-wrapper");
    const chatInput = document.getElementById("chat-input");
    const chatSendBtn = document.getElementById("chat-send-btn");
    const compileChatBtn = document.getElementById("compile-chat-btn");

    // Textarea DOM Elements
    const narrativeInput = document.getElementById("narrative-input");
    const analyzeBtn = document.getElementById("analyze-btn");

    // Output & Analysis View Elements
    const analyzeBtnText = document.getElementById("analyze-btn-text");
    const analyzeSpinner = document.getElementById("analyze-spinner");
    const outputPanel = document.getElementById("output-panel");
    const emptyView = document.getElementById("empty-view");
    const analysisView = document.getElementById("analysis-view");
    const pocsoAlert = document.getElementById("pocso-alert");
    
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");
    
    const verdictCategory = document.getElementById("verdict-category");
    const verdictSubcategory = document.getElementById("verdict-subcategory");
    const verdictConfidence = document.getElementById("verdict-confidence");
    const confidenceFill = document.getElementById("confidence-fill");
    const verdictRationale = document.getElementById("verdict-rationale");
    
    const factComplainant = document.getElementById("fact-complainant");
    const factRespondent = document.getElementById("fact-respondent");
    const factDate = document.getElementById("fact-date");
    const factLocation = document.getElementById("fact-location");
    const factNature = document.getElementById("fact-nature");
    const factWitnesses = document.getElementById("fact-witnesses");
    const factEvidence = document.getElementById("fact-evidence");
    
    const draftAddressedTo = document.getElementById("draft-addressed-to");
    const draftEditor = document.getElementById("draft-editor");
    const exportBtn = document.getElementById("export-btn");
    const ragSnippetsList = document.getElementById("rag-snippets-list");

    let currentAnalysisData = null;

    // State Tracking Flags
    let hasProvidedName = false;
    let hasProvidedAge = false;

    // Conversational Chat State
    let chatMessages = [
        {
            role: "assistant",
            content: "Hello, I am your AI Legal Assistant. Before we begin, could you please tell me your name?"
        }
    ];

    // Mode Toggle Logic
    modeChatBtn.addEventListener("click", () => {
        modeChatBtn.classList.add("active");
        modeTextBtn.classList.remove("active");
        chatModeView.classList.remove("hidden");
        textModeView.classList.add("hidden");
    });

    modeTextBtn.addEventListener("click", () => {
        modeTextBtn.classList.add("active");
        modeChatBtn.classList.remove("active");
        textModeView.classList.remove("hidden");
        chatModeView.classList.add("hidden");
    });

    // Render Chat Messages
    function renderChatMessages() {
        chatMessagesList.innerHTML = "";
        chatMessages.forEach(msg => {
            const msgDiv = document.createElement("div");
            msgDiv.className = `chat-msg ${msg.role === "user" ? "user-msg" : "assistant-msg"}`;
            
            const avatar = document.createElement("div");
            avatar.className = "msg-avatar";
            avatar.textContent = msg.role === "user" ? "👤" : "🤖";

            const content = document.createElement("div");
            content.className = "msg-content";

            // Format line breaks as paragraphs
            const lines = msg.content.split("\n").filter(l => l.trim().length > 0);
            lines.forEach(l => {
                const p = document.createElement("p");
                p.textContent = l;
                content.appendChild(p);
            });

            msgDiv.appendChild(avatar);
            msgDiv.appendChild(content);
            chatMessagesList.appendChild(msgDiv);
        });

        // Scroll chat to bottom
        chatMessagesList.scrollTop = chatMessagesList.scrollHeight;
    }

    // Attach listeners for initial welcome menu option chips
    document.querySelectorAll(".welcome-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            const val = btn.getAttribute("data-value") || btn.textContent.trim();
            if (welcomeChipsWrapper) welcomeChipsWrapper.classList.add("hidden");
            sendUserChatMessage(val);
        });
    });

    // Attach listeners for Age Select buttons
    document.querySelectorAll(".age-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            const ageVal = btn.getAttribute("data-age") || btn.textContent.trim();
            hasProvidedAge = true;
            if (ageSelectWrapper) ageSelectWrapper.classList.add("hidden");
            sendUserChatMessage(ageVal);
        });
    });

    // Helper: Check if user input likely contains a name or responds to a name inquiry
    function checkForNameInput(text) {
        if (hasProvidedName) return true;
        const low = text.trim().toLowerCase();
        
        // Simple greetings should not count as names
        const greetings = ["hello", "hi", "hey", "good morning", "good evening", "namaste", "help"];
        if (greetings.some(g => low === g || low === g + "." || low === g + "!")) {
            return false;
        }

        // Any non-greeting input after assistant greeting is recognized as the name
        return true;
    }

    // Send Chat Message Handler
    async function sendUserChatMessage(text) {
        const trimmed = text.trim();
        if (!trimmed) return;

        // Push User Message
        chatMessages.push({ role: "user", content: trimmed });
        chatInput.value = "";
        renderChatMessages();

        // Check for Name detection state change
        if (!hasProvidedName && checkForNameInput(trimmed)) {
            hasProvidedName = true;
            // Reveal Age Selection Box immediately when name is provided
            if (ageSelectWrapper && !hasProvidedAge) ageSelectWrapper.classList.remove("hidden");
        }

        // Show assistant typing state
        chatSendBtn.disabled = true;

        try {
            const response = await fetch(`${BASE_URL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: chatMessages })
            });

            if (!response.ok) throw new Error("Chat assistant error");

            const data = await response.json();
            chatMessages.push({ role: "assistant", content: data.reply });
            renderChatMessages();
        } catch (err) {
            console.error(err);
            chatMessages.push({
                role: "assistant",
                content: "I am having trouble connecting to the local LLM server. Please ensure Ollama is running."
            });
            renderChatMessages();
        } finally {
            chatSendBtn.disabled = false;
        }
    }

    chatSendBtn.addEventListener("click", () => {
        sendUserChatMessage(chatInput.value);
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            sendUserChatMessage(chatInput.value);
        }
    });

    // 1. Ingest Documents Event
    ingestBtn.addEventListener("click", async () => {
        ingestBtn.disabled = true;
        ingestStatus.textContent = "Scanning...";
        ingestStatus.className = "status-indicator";

        try {
            const response = await fetch(`${BASE_URL}/api/ingest`, {
                method: "POST"
            });
            if (!response.ok) throw new Error("Failed to scan documents.");
            
            const data = await response.json();
            if (data.status === "success") {
                ingestStatus.textContent = `${data.total_chunks} chunks loaded`;
                ingestStatus.classList.add("ready");
                alert(`Successfully processed ${data.processed_files.length} file(s) into ${data.total_chunks} vector chunks!`);
            } else {
                ingestStatus.textContent = "0 files found";
                alert("No legal PDF/TXT files found in 'data/legal_sources/'. Please place act documents there and try again.");
            }
        } catch (error) {
            console.error(error);
            ingestStatus.textContent = "Scan Error";
            alert("Error running document ingestion. Check terminal logs.");
        } finally {
            ingestBtn.disabled = false;
        }
    });

    // 2. Compile Chat to Draft Analysis Event
    compileChatBtn.addEventListener("click", () => {
        const userMsgs = chatMessages.filter(m => m.role === "user");
        if (userMsgs.length === 0) {
            alert("Please chat or select options to describe the incident before generating a draft.");
            return;
        }

        runAnalysisPipeline({ messages: chatMessages });
    });

    // 3. Analyze narrative text event (Legacy text mode)
    analyzeBtn.addEventListener("click", () => {
        const text = narrativeInput.value.trim();
        if (!text) {
            alert("Please enter a description of the incident first.");
            return;
        }
        runAnalysisPipeline({ raw_text: text });
    });

    // Core Analysis Pipeline Call
    async function runAnalysisPipeline(payload) {
        const activeBtn = modeChatBtn.classList.contains("active") ? compileChatBtn : analyzeBtn;
        activeBtn.disabled = true;
        analyzeSpinner.style.display = "inline-block";
        analyzeBtnText.textContent = "Analyzing incident details...";

        try {
            const response = await fetch(`${BASE_URL}/api/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error during analysis.");
            }

            const data = await response.json();
            currentAnalysisData = data;

            // Render Results
            renderAnalysis(data);
        } catch (error) {
            console.error(error);
            alert(`Analysis failed: ${error.message}\nEnsure Ollama is running locally with llama3.2:1b.`);
        } finally {
            activeBtn.disabled = false;
            analyzeSpinner.style.display = "none";
            analyzeBtnText.textContent = "✨ Convert Conversation into Draft Complaint";
        }
    }

    // Render Analysis results
    function renderAnalysis(data) {
        // Toggle view panels
        emptyView.classList.add("hidden");
        outputPanel.classList.remove("empty-state");
        analysisView.classList.remove("hidden");

        // POCSO alert handling
        if (data.mandatory_report_alert) {
            pocsoAlert.classList.remove("hidden");
        } else {
            pocsoAlert.classList.add("hidden");
        }

        // Classification Results
        const category = data.classification.category;
        verdictCategory.textContent = category;
        verdictCategory.className = "verdict-badge " + category.toLowerCase();
        
        if (verdictSubcategory) {
            verdictSubcategory.textContent = data.classification.sub_category || "";
        }
        
        const confPercent = Math.round(data.classification.confidence * 100);
        verdictConfidence.textContent = `${confPercent}%`;
        confidenceFill.style.width = `${confPercent}%`;
        
        verdictRationale.textContent = data.classification.rationale;

        // Extracted Facts
        const facts = data.extracted_facts;
        factComplainant.textContent = facts.complainant_name || "[Not mentioned - add manually in draft]";
        factRespondent.textContent = facts.respondent_name || "[Not mentioned - add manually in draft]";
        factDate.textContent = facts.incident_date || "[Not specified]";
        factLocation.textContent = facts.incident_location || "[Not specified]";
        factNature.textContent = facts.nature_of_incident || "-";
        factWitnesses.textContent = facts.witnesses.length ? facts.witnesses.join(", ") : "None";
        factEvidence.textContent = facts.evidence_description.length ? facts.evidence_description.join(", ") : "None";

        // Legal context RAG
        ragSnippetsList.innerHTML = "";
        const citations = data.draft.citations || [];
        if (citations.length === 0) {
            ragSnippetsList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No matching legal sections were found in the database. Scan files first.</p>';
        } else {
            citations.forEach(cit => {
                const card = document.createElement("div");
                card.className = "rag-card";
                
                const meta = document.createElement("div");
                meta.className = "rag-meta";
                meta.innerHTML = `<span>Source: ${cit.source}</span><span>Relevance: ${Math.round(cit.relevance_score * 100)}%</span>`;
                
                const snippet = document.createElement("div");
                snippet.className = "rag-snippet";
                snippet.textContent = cit.text_snippet;

                card.appendChild(meta);
                card.appendChild(snippet);
                ragSnippetsList.appendChild(card);
            });
        }

        // Draft Section
        draftAddressedTo.textContent = data.draft.addressed_to;
        draftEditor.value = data.draft.draft_text;
    }

    // Tab Toggling Logic
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const tabId = btn.getAttribute("data-tab");
            document.getElementById(tabId).classList.add("active");
        });
    });

    // Export DOCX Event
    exportBtn.addEventListener("click", async () => {
        if (!currentAnalysisData) return;

        exportBtn.disabled = true;
        exportBtn.innerHTML = '<span class="spinner" style="display:inline-block"></span> Exporting...';

        try {
            const exportPayload = {
                category: currentAnalysisData.draft.category,
                addressed_to: currentAnalysisData.draft.addressed_to,
                draft_text: draftEditor.value,
                disclaimer: currentAnalysisData.draft.disclaimer,
                citations: []
            };

            const response = await fetch(`${BASE_URL}/api/export`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(exportPayload)
            });

            if (!response.ok) throw new Error("Failed to export Word document.");

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `complaint_draft_${exportPayload.category.toLowerCase()}.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error(error);
            alert("Error downloading document draft.");
        } finally {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<span class="icon">📥</span> Export to Word (.docx)';
        }
    });
});
