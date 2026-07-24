document.addEventListener("DOMContentLoaded", () => {
    // Determine backend URL (fallback to localhost if opened as file://)
    const BASE_URL = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

    // DOM Elements
    const ingestBtn = document.getElementById("ingest-btn");
    const ingestStatus = document.getElementById("ingest-status");
    const narrativeInput = document.getElementById("narrative-input");
    const analyzeBtn = document.getElementById("analyze-btn");
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

    // 2. Analyze narrative event
    analyzeBtn.addEventListener("click", async () => {
        const text = narrativeInput.value.trim();
        if (!text) {
            alert("Please enter a description of the incident first.");
            return;
        }

        // Setup loading state
        analyzeBtn.disabled = true;
        analyzeSpinner.style.display = "inline-block";
        analyzeBtnText.textContent = "Analyzing incident details...";

        try {
            const response = await fetch(`${BASE_URL}/api/analyze`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ raw_text: text })
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
            analyzeBtn.disabled = false;
            analyzeSpinner.style.display = "none";
            analyzeBtnText.textContent = "Analyze & Draft Complaint";
        }
    });

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

    // 3. Tab Toggling Logic
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const tabId = btn.getAttribute("data-tab");
            document.getElementById(tabId).classList.add("active");
        });
    });

    // 4. Export DOCX Event
    exportBtn.addEventListener("click", async () => {
        if (!currentAnalysisData) return;

        exportBtn.disabled = true;
        exportBtn.innerHTML = '<span class="spinner" style="display:inline-block"></span> Exporting...';

        try {
            // Prepare modified draft data from user editor input
            const exportPayload = {
                category: currentAnalysisData.draft.category,
                addressed_to: currentAnalysisData.draft.addressed_to,
                draft_text: draftEditor.value,
                disclaimer: currentAnalysisData.draft.disclaimer,
                citations: [] // Citations not needed in docx template
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
