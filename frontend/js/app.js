document.addEventListener("DOMContentLoaded", () => {
    // Determine backend URL (fallback to localhost only if opened directly from local filesystem)
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    const BASE_URL = (window.location.protocol === "file:" || (isLocalhost && window.location.port && window.location.port !== "8000")) ? "http://127.0.0.1:8000" : "";



    // DOM Elements
    const ingestBtn = document.getElementById("ingest-btn");
    const ingestStatus = document.getElementById("ingest-status");
    
    // Panel Elements
    const inputPanel = document.querySelector(".input-panel");

    // Textarea DOM Elements
    const narrativeInput = document.getElementById("narrative-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const textAnalyzeBtnText = document.getElementById("text-analyze-btn-text");
    const textAnalyzeSpinner = document.getElementById("text-analyze-spinner");

    // Output & Analysis View Elements
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
    const factRespondentDesignation = document.getElementById("fact-respondent-designation");
    const factDate = document.getElementById("fact-date");
    const factTime = document.getElementById("fact-time");
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

    // 2. Analyze narrative text event
    analyzeBtn.addEventListener("click", () => {
        const text = narrativeInput.value.trim();
        if (!text) {
            alert("Please enter a description of the incident first.");
            return;
        }
        runAnalysisPipeline({ 
            raw_text: text,
            action_triggered: "GENERATE_DRAFT"
        });
    });

    // Loading Animation Coordinator
    let loadingTimeouts = [];
    let progressInterval = null;
    let currentProgress = 0;
    let targetProgress = 0;

    function startProgressTick() {
        const fillEl = document.getElementById("progress-bar-fill");
        const textEl = document.getElementById("progress-percent");
        
        currentProgress = 0;
        targetProgress = 0;
        if (fillEl) fillEl.style.width = "0%";
        if (textEl) textEl.textContent = "0%";

        clearInterval(progressInterval);
        progressInterval = setInterval(() => {
            if (currentProgress < targetProgress) {
                currentProgress += 1;
                if (fillEl) fillEl.style.width = `${currentProgress}%`;
                if (textEl) textEl.textContent = `${currentProgress}%`;
            }
        }, 30);
    }

    function setStepState(stepIndex, state) {
        // state: "waiting", "active", "completed"
        const step = document.getElementById(`step-${stepIndex}`);
        if (!step) return;

        const iconEl = step.querySelector('.step-icon');
        const statusEl = step.querySelector('.step-status');

        if (state === "active") {
            step.classList.remove("completed");
            step.classList.add("active");
            if (statusEl) statusEl.textContent = "Running...";
        } else if (state === "completed") {
            step.classList.remove("active");
            step.classList.add("completed");
            if (iconEl) iconEl.textContent = "✔";
            if (statusEl) statusEl.textContent = "Done";
        } else {
            step.classList.remove("active", "completed");
            if (iconEl && step.dataset.originalIcon) {
                iconEl.textContent = step.dataset.originalIcon;
            }
            if (statusEl) statusEl.textContent = "Waiting...";
        }
    }

    function startLoadingAnimation() {
        const loadingView = document.getElementById("loading-view");
        if (!loadingView) return;

        // Clear existing timeouts & intervals
        loadingTimeouts.forEach(clearTimeout);
        loadingTimeouts = [];
        clearInterval(progressInterval);

        emptyView.classList.add("hidden");
        analysisView.classList.add("hidden");
        loadingView.classList.remove("hidden");

        const defaultTexts = {
            1: "Reading Complaint",
            2: "Identifying Important Facts",
            3: "Checking Applicable Law",
            4: "Extracting Complainant Details",
            5: "Drafting Complaint",
            6: "Final Verification"
        };

        const steps = [1, 2, 3, 4, 5, 6];
        steps.forEach(i => {
            const step = document.getElementById(`step-${i}`);
            if (step) {
                // Restore original icon and texts
                const iconEl = step.querySelector('.step-icon');
                if (iconEl && step.dataset.originalIcon) {
                    iconEl.textContent = step.dataset.originalIcon;
                }
                const textEl = step.querySelector('.step-text');
                if (textEl) {
                    textEl.textContent = defaultTexts[i];
                }
                const statusEl = step.querySelector('.step-status');
                if (statusEl) {
                    statusEl.textContent = "Waiting...";
                    statusEl.style.color = "";
                    statusEl.style.borderColor = "";
                    statusEl.style.background = "";
                }
            }
            if (step && !step.dataset.originalIcon) {
                step.dataset.originalIcon = step.querySelector('.step-icon').textContent;
            }
            setStepState(i, "waiting");
        });

        const statusSubtitle = document.querySelector(".status-subtitle");
        if (statusSubtitle) statusSubtitle.textContent = "Status: Initializing AI Engine";

        startProgressTick();

        // Step 1: Active immediately
        setStepState(1, "active");
        targetProgress = 15;
        if (statusSubtitle) statusSubtitle.textContent = "Status: Reading Complaint";

        // Step 2: at 1200ms
        loadingTimeouts.push(setTimeout(() => {
            setStepState(1, "completed");
            setStepState(2, "active");
            targetProgress = 35;
            if (statusSubtitle) statusSubtitle.textContent = "Status: Identifying Important Facts";
        }, 1200));

        // Step 3: at 2400ms
        loadingTimeouts.push(setTimeout(() => {
            setStepState(2, "completed");
            setStepState(3, "active");
            targetProgress = 55;
            if (statusSubtitle) statusSubtitle.textContent = "Status: Checking Applicable Law";
        }, 2400));

        // Step 4: at 3600ms
        loadingTimeouts.push(setTimeout(() => {
            setStepState(3, "completed");
            setStepState(4, "active");
            targetProgress = 72;
            if (statusSubtitle) statusSubtitle.textContent = "Status: Extracting Complainant Details";
        }, 3600));

        // Step 5: at 4800ms
        loadingTimeouts.push(setTimeout(() => {
            setStepState(4, "completed");
            setStepState(5, "active");
            targetProgress = 88;
            if (statusSubtitle) statusSubtitle.textContent = "Status: Drafting Complaint Structure";
        }, 4800));

        // Step 6: at 6000ms
        loadingTimeouts.push(setTimeout(() => {
            setStepState(5, "completed");
            setStepState(6, "active");
            targetProgress = 96;
            if (statusSubtitle) statusSubtitle.textContent = "Status: Final Verification Checklist";
        }, 6000));
    }

    function stopLoadingAnimation(callback) {
        loadingTimeouts.forEach(clearTimeout);
        loadingTimeouts = [];

        const statusSubtitle = document.querySelector(".status-subtitle");
        if (statusSubtitle) statusSubtitle.textContent = "Status: Complete";

        // Set target progress to 100%
        targetProgress = 100;

        // Complete any pending steps in a quick sequence for a polished feel
        let delay = 0;
        const steps = [1, 2, 3, 4, 5, 6];
        steps.forEach(i => {
            const step = document.getElementById(`step-${i}`);
            if (step && !step.classList.contains("completed")) {
                loadingTimeouts.push(setTimeout(() => {
                    setStepState(i, "completed");
                }, delay));
                delay += 200;
            }
        });

        // Hide loading screen and show results after sequence completes
        loadingTimeouts.push(setTimeout(() => {
            clearInterval(progressInterval);
            
            // Force 100% visual state
            const fillEl = document.getElementById("progress-bar-fill");
            const textEl = document.getElementById("progress-percent");
            if (fillEl) fillEl.style.width = "100%";
            if (textEl) textEl.textContent = "100%";

            const loadingView = document.getElementById("loading-view");
            if (loadingView) loadingView.classList.add("hidden");
            if (callback) callback();
        }, delay + 100));
    }

    function stopLoadingAnimationOther(callback) {
        loadingTimeouts.forEach(clearTimeout);
        loadingTimeouts = [];

        const statusSubtitle = document.querySelector(".status-subtitle");
        if (statusSubtitle) statusSubtitle.textContent = "Status: Classification Complete - Out of Scope";

        // Stop progress at 65%
        clearInterval(progressInterval);
        const fillEl = document.getElementById("progress-bar-fill");
        const textEl = document.getElementById("progress-percent");
        if (fillEl) fillEl.style.width = "65%";
        if (textEl) textEl.textContent = "65%";

        // Step 1: Reading Incident -> Done
        document.querySelector("#step-1 .step-text").textContent = "Reading Incident";
        setStepState(1, "completed");

        // Step 2: Extracting Important Facts -> Done
        document.querySelector("#step-2 .step-text").textContent = "Extracting Important Facts";
        setStepState(2, "completed");

        // Step 3: Determining Applicable Law -> Done
        document.querySelector("#step-3 .step-text").textContent = "Determining Applicable Law";
        setStepState(3, "completed");

        // Step 4: Incident Classification Complete -> Done
        document.querySelector("#step-4 .step-text").textContent = "Incident Classification Complete";
        setStepState(4, "completed");

        // Step 5: Complaint Draft Not Applicable -> Skipped
        const step5Icon = document.querySelector("#step-5 .step-icon");
        if (step5Icon) step5Icon.textContent = "⛔";
        document.querySelector("#step-5 .step-text").textContent = "Complaint Draft Not Applicable";
        const status5 = document.querySelector("#step-5 .step-status");
        if (status5) {
            status5.textContent = "N/A";
            status5.style.color = "var(--color-danger)";
            status5.style.borderColor = "var(--color-danger-border)";
            status5.style.background = "var(--color-danger-bg)";
        }
        document.getElementById("step-5").classList.remove("active");
        document.getElementById("step-5").classList.add("completed");

        // Step 6: Legal Advice Restricted -> Restricted
        const step6Icon = document.querySelector("#step-6 .step-icon");
        if (step6Icon) step6Icon.textContent = "⛔";
        document.querySelector("#step-6 .step-text").textContent = "Legal Advice Restricted";
        const status6 = document.querySelector("#step-6 .step-status");
        if (status6) {
            status6.textContent = "Blocked";
            status6.style.color = "var(--color-danger)";
            status6.style.borderColor = "var(--color-danger-border)";
            status6.style.background = "var(--color-danger-bg)";
        }
        document.getElementById("step-6").classList.remove("active");
        document.getElementById("step-6").classList.add("completed");

        // Pause for 1.8 seconds so user can read the "OTHER" state before transitioning
        loadingTimeouts.push(setTimeout(() => {
            const loadingView = document.getElementById("loading-view");
            if (loadingView) loadingView.classList.add("hidden");
            if (callback) callback();
        }, 1800));
    }

    function cancelLoadingAnimation() {
        loadingTimeouts.forEach(clearTimeout);
        loadingTimeouts = [];
        clearInterval(progressInterval);
        const loadingView = document.getElementById("loading-view");
        if (loadingView) loadingView.classList.add("hidden");
        emptyView.classList.remove("hidden");
    }

    // Core Analysis Pipeline Call
    async function runAnalysisPipeline(payload) {
        analyzeBtn.disabled = true;
        if (textAnalyzeSpinner) textAnalyzeSpinner.style.display = "inline-block";
        if (textAnalyzeBtnText) textAnalyzeBtnText.textContent = "Analyzing...";

        startLoadingAnimation();

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

            const isOther = data.classification.category === "OTHER";

            if (isOther) {
                stopLoadingAnimationOther(() => {
                    renderAnalysis(data);
                });
            } else {
                stopLoadingAnimation(() => {
                    renderAnalysis(data);
                });
            }
        } catch (error) {
            cancelLoadingAnimation();
            console.error(error);
            alert(`Analysis failed: ${error.message}\nEnsure backend server is running.`);
        } finally {
            analyzeBtn.disabled = false;
            if (textAnalyzeSpinner) textAnalyzeSpinner.style.display = "none";
            if (textAnalyzeBtnText) textAnalyzeBtnText.textContent = "Analyze & Draft Complaint";
        }
    }

    // Render Analysis results
    function renderAnalysis(data) {
        const loadingView = document.getElementById("loading-view");
        if (loadingView) loadingView.classList.add("hidden");

        emptyView.classList.add("hidden");
        outputPanel.classList.remove("empty-state");
        analysisView.classList.remove("hidden");

        const isOther = data.classification.category === "OTHER";
        const tabsHeader = document.querySelector(".tabs-header");
        const tabsContent = document.querySelector(".tabs-content");
        const outOfScopeView = document.getElementById("out-of-scope-view");

        if (isOther) {
            if (tabsHeader) tabsHeader.classList.add("hidden");
            if (tabsContent) tabsContent.classList.add("hidden");
            if (outOfScopeView) outOfScopeView.classList.remove("hidden");
            if (pocsoAlert) pocsoAlert.classList.add("hidden");
        } else {
            if (tabsHeader) tabsHeader.classList.remove("hidden");
            if (tabsContent) tabsContent.classList.remove("hidden");
            if (outOfScopeView) outOfScopeView.classList.add("hidden");

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
            factComplainant.textContent = facts.complainant_name || "[Not Provided / Unspecified]";
            factRespondent.textContent = facts.respondent_name || "[Not Provided / Unspecified]";
            factRespondentDesignation.textContent = facts.respondent_designation || "[Not Provided / Unspecified]";
            factDate.textContent = facts.incident_date || "[Not Provided / Unspecified]";
            factTime.textContent = facts.incident_time || "[Not Provided / Unspecified]";
            factLocation.textContent = facts.incident_location || "[Not Provided / Unspecified]";
            factNature.textContent = facts.nature_of_incident || "-";
            factWitnesses.textContent = facts.witnesses.length ? facts.witnesses.join(", ") : "[None Specified]";
            factEvidence.textContent = facts.evidence_description.length ? facts.evidence_description.join(", ") : "[None Provided]";

            // Legal context RAG
            ragSnippetsList.innerHTML = "";
            const citations = data.draft.citations || [];
            if (citations.length === 0) {
                ragSnippetsList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No matching legal sections were found in the database. Click "Scan & Ingest Docs" first.</p>';
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

            // Draft Section formatting
            draftAddressedTo.textContent = data.draft.addressed_to;
            
            if (data.payload && data.payload.formatted_draft) {
                draftEditor.value = data.payload.formatted_draft;
            } else {
                draftEditor.value = data.draft.draft_text;
            }
        }
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
                citations: [],
                facts: currentAnalysisData.extracted_facts
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
