class UIManager {
    constructor() {
        this.activeSection = null;
    }

    showLoading(sectionId, message = 'Processing...') {
        const section = document.getElementById(sectionId);
        const loadingEl = section.querySelector('.loading-indicator');
        const loadingText = loadingEl.querySelector('.loading-text');

        loadingText.textContent = message;
        loadingEl.classList.add('active');

        const buttons = section.querySelectorAll('.btn');
        buttons.forEach(btn => btn.disabled = true);
    }

    hideLoading(sectionId) {
        const section = document.getElementById(sectionId);
        const loadingEl = section.querySelector('.loading-indicator');
        loadingEl.classList.remove('active');

        const buttons = section.querySelectorAll('.btn');
        buttons.forEach(btn => btn.disabled = false);
    }

    showError(message) {
        const errorEl = document.getElementById('globalError');
        errorEl.textContent = message;
        errorEl.classList.add('active');

        setTimeout(() => {
            errorEl.classList.remove('active');
        }, 5000);
    }

    hideError() {
        const errorEl = document.getElementById('globalError');
        errorEl.classList.remove('active');
    }

    updateFileInfo(file) {
        const fileInfoEl = document.getElementById('fileInfo');
        const fileName = fileInfoEl.querySelector('#fileName');
        const fileSize = fileInfoEl.querySelector('#fileSize');

        fileName.textContent = file.name;
        fileSize.textContent = this.formatFileSize(file.size);
        fileInfoEl.classList.add('active');

        const uploadArea = document.getElementById('fileUploadArea');
        uploadArea.classList.add('has-file');
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    formatJSON(obj) {
        return JSON.stringify(obj, null, 2);
    }

    showResults(title, content) {
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsTitle = document.getElementById('resultsTitle');
        const resultsContent = document.getElementById('resultsContent');

        resultsTitle.textContent = title;
        resultsContent.innerHTML = content;
        resultsContainer.classList.add('active');

        setTimeout(() => {
            this.animateProgressBars();
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    closeResults() {
        const resultsContainer = document.getElementById('resultsContainer');
        resultsContainer.classList.remove('active');
    }

    animateProgressBars() {
        const progressBars = document.querySelectorAll('.coverage-progress-bar');
        progressBars.forEach(bar => {
            const width = bar.getAttribute('data-width');
            if (width) {
                setTimeout(() => {
                    bar.style.width = width + '%';
                }, 100);
            }
        });
    }

    createScoreGauge(score, label = 'Compliance Score') {
        const circumference = 2 * Math.PI * 75;
        const offset = circumference - (score / 100) * circumference;

        return `
            <div class="score-gauge">
                <svg class="gauge-circle" width="200" height="200">
                    <circle class="gauge-background" cx="100" cy="100" r="75"></circle>
                    <circle
                        class="gauge-progress"
                        cx="100"
                        cy="100"
                        r="75"
                        style="--progress: ${offset}">
                    </circle>
                </svg>
                <div class="gauge-text">
                    <span class="gauge-score">${score}</span>
                    <span class="gauge-label">${label}</span>
                </div>
            </div>
        `;
    }

    getComplianceBadge(score) {
        if (score >= 90) return { text: 'Excellent Compliance', emoji: '✅' };
        if (score >= 75) return { text: 'Good Compliance', emoji: '👍' };
        if (score >= 60) return { text: 'Moderate Compliance', emoji: '⚠️' };
        if (score >= 40) return { text: 'Poor Compliance', emoji: '❌' };
        return { text: 'Critical Issues', emoji: '🚨' };
    }

    createScoreDisplay(data) {
        const overall = data.overall_compliance || {};
        const score = overall.overall_score || 0;
        const badge = this.getComplianceBadge(score);

        let html = `
            <div class="score-hero">
                <div class="score-container">
                    ${this.createScoreGauge(score)}
                    <div class="score-details">
                        <div class="score-title">Overall Compliance Score</div>
                        <div class="score-badge">${badge.emoji} ${badge.text}</div>
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-value">${overall.total_articles || 0}</div>
                                <div class="stat-label">Total Articles</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${overall.fully_covered || 0}</div>
                                <div class="stat-label">Fully Covered</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${overall.partially_covered || 0}</div>
                                <div class="stat-label">Partially Covered</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${overall.missing || 0}</div>
                                <div class="stat-label">Missing</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const fullyCoveredPct = overall.total_articles ? (overall.fully_covered / overall.total_articles * 100) : 0;
        const partiallyCoveredPct = overall.total_articles ? (overall.partially_covered / overall.total_articles * 100) : 0;
        const missingPct = overall.total_articles ? (overall.missing / overall.total_articles * 100) : 0;

        html += `
            <div class="coverage-cards">
                <div class="coverage-card success">
                    <div class="coverage-card-header">
                        <span class="coverage-icon">✅</span>
                        <span class="coverage-count">${overall.fully_covered || 0}</span>
                    </div>
                    <div class="coverage-card-title">Fully Covered Articles</div>
                    <p style="color: var(--neutral-600); font-size: 14px;">All requirements comprehensively addressed</p>
                    <div class="coverage-progress">
                        <div class="coverage-progress-bar" data-width="${fullyCoveredPct.toFixed(1)}"></div>
                    </div>
                </div>

                <div class="coverage-card warning">
                    <div class="coverage-card-header">
                        <span class="coverage-icon">⚠️</span>
                        <span class="coverage-count">${overall.partially_covered || 0}</span>
                    </div>
                    <div class="coverage-card-title">Partially Covered Articles</div>
                    <p style="color: var(--neutral-600); font-size: 14px;">Some sections need attention</p>
                    <div class="coverage-progress">
                        <div class="coverage-progress-bar" data-width="${partiallyCoveredPct.toFixed(1)}"></div>
                    </div>
                </div>

                <div class="coverage-card error">
                    <div class="coverage-card-header">
                        <span class="coverage-icon">❌</span>
                        <span class="coverage-count">${overall.missing || 0}</span>
                    </div>
                    <div class="coverage-card-title">Missing Articles</div>
                    <p style="color: var(--neutral-600); font-size: 14px;">Critical gaps in compliance</p>
                    <div class="coverage-progress">
                        <div class="coverage-progress-bar" data-width="${missingPct.toFixed(1)}"></div>
                    </div>
                </div>
            </div>
        `;

        if (data.timing) {
            html += `
                <div class="data-card">
                    <h3>⚡ Processing Time</h3>
                    <p>Analysis completed in ${data.timing.toFixed(2)} seconds</p>
                </div>
            `;
        }

        if (data.summary_counts) {
            html += `<div class="data-card"><h3>📋 Summary Statistics</h3>`;
            for (const [key, value] of Object.entries(data.summary_counts)) {
                html += `<p><strong>${key}:</strong> ${value}</p>`;
            }
            html += `</div>`;
        }

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="uiManager.toggleAccordion(this)">
                    <span>View Full Response (JSON)</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    createMissingDisplay(data) {
        let html = '';

        if (data.missing_articles && data.missing_articles.length > 0) {
            html += `
                <div class="missing-section">
                    <div class="missing-header">
                        <h2 class="missing-title">Missing Articles Analysis</h2>
                        <div class="missing-count-badge">${data.missing_articles.length} Issues Found</div>
                    </div>
                    <div class="missing-items">
            `;

            data.missing_articles.forEach((article, index) => {
                const level = article.coverage_level || 'missing';
                const badgeClass = level === 'missing' ? 'badge-error' :
                                 level === 'partially_covered' ? 'badge-warning' : 'badge-info';
                const badgeText = level === 'missing' ? '❌ Missing' :
                                level === 'partially_covered' ? '⚠️ Partial' : '📊 Low Coverage';

                const preview = (article.text || 'No description available').substring(0, 200);
                const coverage = article.coverage_percentage ?
                    `${article.coverage_percentage.toFixed(1)}%` : 'N/A';

                html += `
                    <div class="missing-item" style="animation-delay: ${index * 0.05}s;">
                        <div class="missing-item-header">
                            <div class="missing-item-id">${article.id || 'Unknown Article'}</div>
                            <span class="missing-item-badge ${badgeClass}">${badgeText}</span>
                        </div>
                        <div class="missing-item-meta">
                            Article ${article.article_number || 'N/A'}
                            ${article.label ? `• ${article.label}` : ''}
                            ${coverage !== 'N/A' ? `• Coverage: ${coverage}` : ''}
                        </div>
                        <div class="missing-item-text">${preview}${preview.length >= 200 ? '...' : ''}</div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="data-card" style="background: #d1fae5; border-left-color: var(--success-green);">
                    <h3>✅ Perfect Coverage</h3>
                    <p>All PDPL articles are adequately covered in your compliance document. Great job!</p>
                </div>
            `;
        }

        if (data.timing) {
            html += `
                <div class="data-card">
                    <h3>⚡ Processing Time</h3>
                    <p>Analysis completed in ${data.timing.toFixed(2)} seconds</p>
                </div>
            `;
        }

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="uiManager.toggleAccordion(this)">
                    <span>View Full Response (JSON)</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    createTestDisplay(data, testType) {
        let html = '';

        if (testType === 'ocr' && data.pages) {
            html += `<h3 style="margin-bottom: 16px; color: var(--neutral-900); font-size: 24px;">📄 OCR Extraction Results</h3>`;

            data.pages.forEach((page, index) => {
                html += `
                    <div class="accordion">
                        <div class="accordion-header" onclick="uiManager.toggleAccordion(this)">
                            <span>Page ${page.page || index + 1} (${page.text ? page.text.length.toLocaleString() : 0} characters)</span>
                            <span class="accordion-icon">▼</span>
                        </div>
                        <div class="accordion-content">
                            <div style="background: var(--neutral-50); padding: 16px; border-radius: 8px; white-space: pre-wrap; line-height: 1.8; font-size: 14px;">
                                ${page.text || 'No text extracted'}
                            </div>
                        </div>
                    </div>
                `;
            });
        } else if ((testType === 'hybrid' || testType === 'rag') && data.matches) {
            html += `
                <h3 style="margin-bottom: 16px; color: var(--neutral-900); font-size: 24px;">
                    🔍 ${testType.toUpperCase()} Matching Results
                </h3>
                <div class="data-card" style="background: #fff4ed; border-left-color: var(--primary-brand);">
                    <h3>📊 Match Summary</h3>
                    <p><strong>${data.total_matches || data.matches.length} PDPL articles</strong> matched with your document</p>
                </div>
            `;

            if (data.matches.length === 0) {
                html += `
                    <div class="data-card">
                        <p>No matches found in the document.</p>
                    </div>
                `;
            } else {
                html += `<div style="display: grid; gap: 16px; margin-top: 24px;">`;

                data.matches.forEach((match, index) => {
                    const article = match.article || {};
                    const similarity = match.similarity ? (match.similarity * 100).toFixed(1) : 'N/A';
                    const coverageType = match.coverage_type || 'unknown';
                    const badgeClass = coverageType === 'fully_covered' ? 'badge-success' :
                                      coverageType === 'partially_covered' ? 'badge-warning' : 'badge-error';

                    html += `
                        <div class="data-card" style="animation: fadeIn 0.4s ease-out ${index * 0.05}s both;">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                                <div>
                                    <h3 style="margin-bottom: 4px;">${article.id || 'Unknown'}</h3>
                                    <p style="font-size: 12px; color: var(--neutral-600); margin: 0;">
                                        Article ${article.article_number || 'N/A'}
                                        ${article.label ? ` • ${article.label}` : ''}
                                    </p>
                                </div>
                                <span class="badge ${badgeClass}">${similarity}% match</span>
                            </div>
                            <p style="margin-bottom: 8px; font-size: 14px; line-height: 1.6;">${article.text || 'No text available'}</p>
                            ${match.coverage_percentage ?
                                `<p style="font-size: 13px; color: var(--neutral-600); margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--neutral-200);">
                                    Coverage: <strong>${match.coverage_percentage.toFixed(1)}%</strong>
                                </p>` : ''}
                        </div>
                    `;
                });

                html += `</div>`;
            }
        }

        if (data.timing) {
            html += `
                <div class="data-card">
                    <h3>⚡ Processing Time</h3>
                    <p>Completed in ${data.timing.toFixed(2)} seconds</p>
                </div>
            `;
        }

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="uiManager.toggleAccordion(this)">
                    <span>View Full Response (JSON)</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    createUploadDisplay(data) {
        let html = `
            <div class="data-card" style="background: #d1fae5; border-left-color: var(--success-green);">
                <h3>✅ Upload Successful</h3>
                <p>Your file has been processed successfully.</p>
            </div>
        `;

        if (data.filename) {
            html += `
                <div class="data-card">
                    <h3>📄 File Information</h3>
                    <p><strong>Filename:</strong> ${data.filename}</p>
                    ${data.pages ? `<p><strong>Pages Processed:</strong> ${data.pages.length}</p>` : ''}
                </div>
            `;
        }

        if (data.matches && data.matches.length > 0) {
            const fullyCovered = data.matches.filter(m => m.coverage_type === 'fully_covered').length;
            const partiallyCovered = data.matches.filter(m => m.coverage_type === 'partially_covered').length;
            const missing = data.matches.filter(m => m.coverage_type === 'missing').length;

            html += `
                <div class="coverage-cards">
                    <div class="coverage-card success">
                        <div class="coverage-card-header">
                            <span class="coverage-icon">✅</span>
                            <span class="coverage-count">${fullyCovered}</span>
                        </div>
                        <div class="coverage-card-title">Fully Covered</div>
                        <p style="color: var(--neutral-600); font-size: 14px;">Complete coverage</p>
                    </div>

                    <div class="coverage-card warning">
                        <div class="coverage-card-header">
                            <span class="coverage-icon">⚠️</span>
                            <span class="coverage-count">${partiallyCovered}</span>
                        </div>
                        <div class="coverage-card-title">Partially Covered</div>
                        <p style="color: var(--neutral-600); font-size: 14px;">Needs attention</p>
                    </div>

                    <div class="coverage-card error">
                        <div class="coverage-card-header">
                            <span class="coverage-icon">❌</span>
                            <span class="coverage-count">${missing}</span>
                        </div>
                        <div class="coverage-card-title">Missing</div>
                        <p style="color: var(--neutral-600); font-size: 14px;">Critical gaps</p>
                    </div>
                </div>
            `;
        }

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="uiManager.toggleAccordion(this)">
                    <span>View Full Response (JSON)</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    toggleAccordion(headerEl) {
        const content = headerEl.nextElementSibling;
        headerEl.classList.toggle('active');
        content.classList.toggle('active');
    }

    enableAllButtons() {
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(btn => {
            if (btn.id !== 'closeResultsBtn') {
                btn.disabled = false;
            }
        });
    }

    disableAllButtons() {
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(btn => {
            if (btn.id !== 'closeResultsBtn') {
                btn.disabled = true;
            }
        });
    }
}

const uiManager = new UIManager();
