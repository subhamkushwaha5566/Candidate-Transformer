document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // API Status Check
    // -------------------------------------------------------------
    const apiStatus = document.getElementById("api-status");
    
    function checkApiHealth() {
        fetch("/health")
            .then(res => res.json())
            .then(data => {
                if (data && data.status === "healthy") {
                    apiStatus.className = "status-badge connected";
                    apiStatus.querySelector(".status-text").textContent = "Connected to Transformer API";
                } else {
                    throw new Error("Invalid status");
                }
            })
            .catch(() => {
                apiStatus.className = "status-badge error";
                apiStatus.querySelector(".status-text").textContent = "Disconnected from API";
            });
    }
    
    checkApiHealth();
    // Re-check health every 30 seconds
    setInterval(checkApiHealth, 30000);

    // -------------------------------------------------------------
    // Drag & Drop / File Inputs Configuration
    // -------------------------------------------------------------
    setupDragZone("csv-drag-zone", "csv-file-input", "csv-file-name", "CSV");
    setupDragZone("resume-drag-zone", "resume-file-input", "resume-file-name", "PDF");

    function setupDragZone(zoneId, inputId, nameDisplayId, fileTypeLabel) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);
        const display = document.getElementById(nameDisplayId);

        zone.addEventListener("click", () => input.click());

        input.addEventListener("change", (e) => {
            handleFileSelection(input.files[0], zone, display, fileTypeLabel);
        });

        // Drag events
        ["dragenter", "dragover"].forEach(eventName => {
            zone.addEventListener(eventName, (e) => {
                e.preventDefault();
                zone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach(eventName => {
            zone.addEventListener(eventName, (e) => {
                e.preventDefault();
                zone.classList.remove("dragover");
            }, false);
        });

        zone.addEventListener("drop", (e) => {
            const dt = e.dataTransfer;
            const file = dt.files[0];
            
            // Assign file to input
            input.files = dt.files;
            handleFileSelection(file, zone, display, fileTypeLabel);
        });
    }

    function handleFileSelection(file, zone, display, type) {
        if (file) {
            display.textContent = `${file.name} (${formatBytes(file.size)})`;
            zone.classList.add("file-loaded");
            showToast(`Selected ${type} file: ${file.name}`, "success");
        } else {
            display.textContent = "No file selected";
            zone.classList.remove("file-loaded");
        }
    }

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // -------------------------------------------------------------
    // Dynamic Fields Rename Row Elements
    // -------------------------------------------------------------
    const renameContainer = document.getElementById("rename-mappings-container");
    const addRenameBtn = document.getElementById("add-rename-btn");

    addRenameBtn.addEventListener("click", () => {
        const row = document.createElement("div");
        row.className = "rename-row";
        
        row.innerHTML = `
            <input type="text" class="rename-path" placeholder="Path (e.g. location.city)">
            <i class="fa-solid fa-arrow-right-long rename-arrow"></i>
            <input type="text" class="rename-to" placeholder="New Name (e.g. city)">
            <button type="button" class="btn-icon delete-rename-row">
                <i class="fa-solid fa-trash-can"></i>
            </button>
        `;

        // Delete action
        row.querySelector(".delete-rename-row").addEventListener("click", () => {
            row.remove();
        });

        renameContainer.appendChild(row);
    });

    // Handle delete on default row (if any custom delete added)
    document.querySelectorAll(".delete-rename-row").forEach(btn => {
        if (!btn.disabled) {
            btn.addEventListener("click", (e) => {
                e.currentTarget.closest(".rename-row").remove();
            });
        }
    });

    // -------------------------------------------------------------
    // Circular Gauge Progress Implementation
    // -------------------------------------------------------------
    const circle = document.getElementById("confidence-circle");
    if (circle) {
        const radius = circle.r.baseVal.value;
        const circumference = radius * 2 * Math.PI;
        circle.style.strokeDasharray = `${circumference} ${circumference}`;
        circle.style.strokeDashoffset = circumference;
    }

    function setGaugeProgress(percent) {
        const confidenceCircle = document.getElementById("confidence-circle");
        const confidenceScoreText = document.getElementById("confidence-score-text");
        
        if (!confidenceCircle) return;
        
        const radius = confidenceCircle.r.baseVal.value;
        const circumference = radius * 2 * Math.PI;
        const offset = circumference - (percent / 100) * circumference;
        
        confidenceCircle.style.strokeDashoffset = offset;
        confidenceScoreText.textContent = `${Math.round(percent)}%`;
    }

    // -------------------------------------------------------------
    // Form Submission & Transformation Ingest
    // -------------------------------------------------------------
    const form = document.getElementById("transform-form");
    const submitBtn = document.getElementById("submit-btn");
    const btnNormal = document.getElementById("btn-text-normal");
    const btnLoading = document.getElementById("btn-text-loading");
    
    // Result displays
    const jsonOutputDisplay = document.getElementById("json-output-display");
    const metricsContainer = document.getElementById("metrics-container");
    const provenanceContainer = document.getElementById("provenance-container");
    const provenanceTableBody = document.getElementById("provenance-table-body");
    
    // Ingest summary fields
    const metSources = document.getElementById("metrics-sources");
    const metSkills = document.getElementById("metrics-skills");
    const metJobs = document.getElementById("metrics-jobs");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const csvInput = document.getElementById("csv-file-input");
        const resumeInput = document.getElementById("resume-file-input");

        if (!csvInput.files[0] && !resumeInput.files[0]) {
            showToast("Please upload at least a CSV file or a Resume PDF file.", "error");
            return;
        }

        // Toggle Loading Button
        submitBtn.disabled = true;
        btnNormal.classList.add("hidden");
        btnLoading.classList.remove("hidden");

        // Build config payload
        const includeConfidence = document.getElementById("cfg-confidence").checked;
        const includeProvenance = document.getElementById("cfg-provenance").checked;
        const onMissing = document.getElementById("cfg-missing-behavior").value;

        // Collect fields & rename mapping configurations
        const fields = [];
        document.querySelectorAll(".field-select:checked").forEach(cb => {
            fields.push(cb.value);
        });

        document.querySelectorAll(".rename-row").forEach(row => {
            const pathVal = row.querySelector(".rename-path").value.trim();
            const toVal = row.querySelector(".rename-to").value.trim();
            if (pathVal && toVal) {
                fields.push({
                    "path": toVal,
                    "from": pathVal
                });
            }
        });

        const config = {
            fields: fields.length > 0 ? fields : null,
            include_confidence: includeConfidence,
            include_provenance: includeProvenance,
            on_missing: onMissing
        };

        // Prepare Multipart FormData
        const formData = new FormData();
        if (csvInput.files[0]) {
            formData.append("csv_file", csvInput.files[0]);
        }
        if (resumeInput.files[0]) {
            formData.append("resume_file", resumeInput.files[0]);
        }
        formData.append("config", JSON.stringify(config));

        try {
            const response = await fetch("/api/v1/transform", {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || "Transformation request failed");
            }

            // Successfully processed!
            showToast("Ingested files transformed successfully!", "success");
            renderDashboardResults(result, config);

        } catch (error) {
            console.error(error);
            showToast(error.message, "error");
            jsonOutputDisplay.textContent = JSON.stringify({ error: error.message }, null, 2);
            metricsContainer.classList.add("hidden");
            provenanceContainer.classList.add("hidden");
        } finally {
            // Restore button states
            submitBtn.disabled = false;
            btnNormal.classList.remove("hidden");
            btnLoading.classList.add("hidden");
        }
    });

    // -------------------------------------------------------------
    // Render Dashboard Elements
    // -------------------------------------------------------------
    let currentResponseJSON = null;

    function renderDashboardResults(data, config) {
        currentResponseJSON = data;

        // 1. Display JSON output nicely formatted
        jsonOutputDisplay.textContent = JSON.stringify(data, null, 2);

        // 2. Render confidence metrics
        const showConfidence = config.include_confidence && (data.overall_confidence !== undefined);
        if (showConfidence) {
            metricsContainer.classList.remove("hidden");
            // Normalize confidence score to percentage representation
            const percentage = data.overall_confidence * 100;
            setGaugeProgress(percentage);
        } else {
            metricsContainer.classList.add("hidden");
        }

        // 3. Render count indicators
        const sourcesSet = new Set();
        if (data.provenance && Array.isArray(data.provenance)) {
            data.provenance.forEach(p => {
                if (p.source) sourcesSet.add(p.source.toUpperCase());
            });
        }
        metSources.textContent = sourcesSet.size > 0 ? Array.from(sourcesSet).join(" + ") : "N/A";
        
        const skillsCount = Array.isArray(data.skills) ? data.skills.length : 0;
        metSkills.textContent = skillsCount;

        const experienceCount = Array.isArray(data.experience) ? data.experience.length : 0;
        metJobs.textContent = experienceCount;

        // 4. Render Field Provenance Audit Trail
        const showProvenance = config.include_provenance && Array.isArray(data.provenance);
        if (showProvenance && data.provenance.length > 0) {
            provenanceContainer.classList.remove("hidden");
            provenanceTableBody.innerHTML = "";
            
            data.provenance.forEach(prov => {
                const tr = document.createElement("tr");
                
                const sourceBadgeClass = `badge badge-${prov.source.toLowerCase()}`;
                const confidencePct = Math.round(prov.confidence * 100);
                
                // Format raw value (handle object representation if nested list item like Experience)
                let rawValueDisplay = prov.raw_value;
                if (typeof prov.raw_value === 'object' && prov.raw_value !== null) {
                    rawValueDisplay = JSON.stringify(prov.raw_value);
                }

                tr.innerHTML = `
                    <td style="font-weight: 600; color: var(--text-primary);">${prov.field}</td>
                    <td><span class="${sourceBadgeClass}">${prov.source}</span></td>
                    <td style="font-weight: 500;">${confidencePct}%</td>
                    <td style="color: var(--text-secondary); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title='${rawValueDisplay}'>
                        ${rawValueDisplay}
                    </td>
                `;
                provenanceTableBody.appendChild(tr);
            });
        } else {
            provenanceContainer.classList.add("hidden");
        }
    }

    // -------------------------------------------------------------
    // Clipboard Copy & Download Result Actions
    // -------------------------------------------------------------
    const copyBtn = document.getElementById("copy-btn");
    const downloadBtn = document.getElementById("download-btn");

    copyBtn.addEventListener("click", () => {
        if (!currentResponseJSON) {
            showToast("No JSON output available to copy.", "error");
            return;
        }
        navigator.clipboard.writeText(JSON.stringify(currentResponseJSON, null, 2))
            .then(() => showToast("Copied JSON output to clipboard!", "success"))
            .catch(() => showToast("Failed to copy text.", "error"));
    });

    downloadBtn.addEventListener("click", () => {
        if (!currentResponseJSON) {
            showToast("No JSON output available to download.", "error");
            return;
        }
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentResponseJSON, null, 2));
        const dlAnchor = document.createElement('a');
        dlAnchor.setAttribute("href", dataStr);
        dlAnchor.setAttribute("download", `candidate_transformed_${Date.now()}.json`);
        document.body.appendChild(dlAnchor);
        dlAnchor.click();
        dlAnchor.remove();
        showToast("JSON file download initialized.", "success");
    });

    // -------------------------------------------------------------
    // Toast Notification Banner Module
    // -------------------------------------------------------------
    function showToast(message, type = "success") {
        const toast = document.getElementById("toast");
        toast.className = `toast toast-${type}`;
        
        const icon = type === "success" 
            ? '<i class="fa-solid fa-circle-check"></i>' 
            : '<i class="fa-solid fa-triangle-exclamation"></i>';
            
        toast.innerHTML = `${icon} <span>${message}</span>`;
        toast.classList.remove("hidden");
        
        // Slide up animation effect
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(20px)";
            setTimeout(() => {
                toast.classList.add("hidden");
            }, 300);
        }, 4000);
    }
});
