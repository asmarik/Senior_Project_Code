class ResultsRenderer {
    formatJSON(obj) {
        return JSON.stringify(obj, null, 2);
    }

    createScoreGauge(score) {
        const circumference = 2 * Math.PI * 75;
        const offset = circumference - (score / 100) * circumference;

        return `
            <div class="score-gauge">
                <svg class="gauge-circle" width="200" height="200">
                    <circle class="gauge-background" cx="100" cy="100" r="75"></circle>
                    <circle class="gauge-progress" cx="100" cy="100" r="75" style="--progress: ${offset}"></circle>
                </svg>
                <div class="gauge-text">
                    <span class="gauge-score">${score}</span>
                    <span class="gauge-label">Score</span>
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

    renderScore(data) {
        const overall = data.overall_compliance || {};
        const score = overall.overall_score || 0;
        const badge = this.getComplianceBadge(score);

        const fullyCoveredPct = overall.total_articles ? (overall.fully_covered / overall.total_articles * 100) : 0;
        const partiallyCoveredPct = overall.total_articles ? (overall.partially_covered / overall.total_articles * 100) : 0;
        const missingPct = overall.total_articles ? (overall.missing / overall.total_articles * 100) : 0;

        let html = `
            <div class="score-hero">
                <div class="score-container">
                    ${this.createScoreGauge(score)}
                    <div class="score-details">
                        <div class="score-title">Compliance Assessment</div>
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
                                <div class="stat-label">Partial</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${overall.missing || 0}</div>
                                <div class="stat-label">Missing</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="coverage-cards">
                <div class="coverage-card success">
                    <div class="coverage-card-header">
                        <span class="coverage-icon">✅</span>
                        <span class="coverage-count">${overall.fully_covered || 0}</span>
                    </div>
                    <div class="coverage-card-title">Fully Covered Articles</div>
                    <p>All regulatory requirements comprehensively addressed with complete documentation.</p>
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
                    <p>Some sections need additional attention or more detailed documentation.</p>
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
                    <p>Critical gaps in compliance documentation requiring immediate attention.</p>
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

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion(this)">
                    <span>View Full Response Data</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    renderMissing(data) {
        let html = '';

        if (data.missing_articles && data.missing_articles.length > 0) {
            html += `
                <div class="missing-section">
                    <div class="missing-header">
                        <h2 class="missing-title">Gap Analysis Results</h2>
                        <div class="missing-count-badge">${data.missing_articles.length} Issues Identified</div>
                    </div>
                    <div class="missing-items">
            `;

            data.missing_articles.forEach((article, index) => {
                const level = article.coverage_level || 'missing';
                const badgeClass = level === 'missing' ? 'badge-error' :
                                 level === 'partially_covered' ? 'badge-warning' : 'badge-info';
                const badgeText = level === 'missing' ? '❌ Missing' :
                                level === 'partially_covered' ? '⚠️ Partial' : '📊 Low Coverage';

                const preview = (article.text || 'No description available').substring(0, 250);
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
                            ${article.label ? ` • ${article.label}` : ''}
                            ${coverage !== 'N/A' ? ` • Coverage: ${coverage}` : ''}
                        </div>
                        <div class="missing-item-text">${preview}${preview.length >= 250 ? '...' : ''}</div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="data-card" style="background: #d1fae5; border-left-color: var(--color-success);">
                    <h3>✅ Complete Coverage</h3>
                    <p>All PDPL articles are adequately covered in your compliance documentation. Excellent work!</p>
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
                <div class="accordion-header" onclick="toggleAccordion(this)">
                    <span>View Full Response Data</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    renderTest(data, testType) {
        let html = '';

        if (testType === 'ocr' && data.pages) {
            html += `<h3 style="margin-bottom: 1.5rem; font-size: 1.25rem;">📄 OCR Extraction Results</h3>`;

            data.pages.forEach((page, index) => {
                html += `
                    <div class="accordion">
                        <div class="accordion-header" onclick="toggleAccordion(this)">
                            <span>Page ${page.page || index + 1} (${page.text ? page.text.length.toLocaleString() : 0} characters)</span>
                            <span class="accordion-icon">▼</span>
                        </div>
                        <div class="accordion-content">
                            <div style="background: var(--color-gray-50); padding: 1rem; border-radius: var(--radius-md); white-space: pre-wrap; line-height: 1.8; font-size: 0.875rem;">
                                ${page.text || 'No text extracted'}
                            </div>
                        </div>
                    </div>
                `;
            });
        } else if ((testType === 'hybrid' || testType === 'rag') && data.matches) {
            html += `
                <h3 style="margin-bottom: 1rem; font-size: 1.25rem;">
                    🔍 ${testType.toUpperCase()} Matching Results
                </h3>
                <div class="data-card" style="background: #dbeafe; border-left-color: var(--color-primary);">
                    <h3>📊 Match Summary</h3>
                    <p><strong>${data.total_matches || data.matches.length} PDPL articles</strong> identified in your document</p>
                </div>
            `;

            if (data.matches.length > 0) {
                html += `<div style="display: grid; gap: 1rem; margin-top: 1.5rem;">`;

                data.matches.forEach((match, index) => {
                    const article = match.article || {};
                    const similarity = match.similarity ? (match.similarity * 100).toFixed(1) : 'N/A';
                    const coverageType = match.coverage_type || 'unknown';
                    const badgeClass = coverageType === 'fully_covered' ? 'badge-success' :
                                      coverageType === 'partially_covered' ? 'badge-warning' : 'badge-error';

                    html += `
                        <div class="data-card" style="animation: fadeInUp 0.4s ease-out ${index * 0.05}s both;">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;">
                                <div>
                                    <h3 style="margin-bottom: 0.25rem;">${article.id || 'Unknown'}</h3>
                                    <p style="font-size: 0.75rem; color: var(--color-gray-600); margin: 0;">
                                        Article ${article.article_number || 'N/A'}
                                        ${article.label ? ` • ${article.label}` : ''}
                                    </p>
                                </div>
                                <span class="badge ${badgeClass}">${similarity}% match</span>
                            </div>
                            <p style="font-size: 0.875rem; line-height: 1.6;">${article.text || 'No text available'}</p>
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
                <div class="accordion-header" onclick="toggleAccordion(this)">
                    <span>View Full Response Data</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }

    renderUpload(data) {
        let html = `
            <div class="data-card" style="background: #d1fae5; border-left-color: var(--color-success);">
                <h3>✅ Upload Successful</h3>
                <p>Your compliance document has been processed successfully.</p>
            </div>
        `;

        if (data.filename) {
            html += `
                <div class="data-card">
                    <h3>📄 Document Information</h3>
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
                        <p>Complete regulatory coverage</p>
                    </div>

                    <div class="coverage-card warning">
                        <div class="coverage-card-header">
                            <span class="coverage-icon">⚠️</span>
                            <span class="coverage-count">${partiallyCovered}</span>
                        </div>
                        <div class="coverage-card-title">Partial Coverage</div>
                        <p>Needs attention</p>
                    </div>

                    <div class="coverage-card error">
                        <div class="coverage-card-header">
                            <span class="coverage-icon">❌</span>
                            <span class="coverage-count">${missing}</span>
                        </div>
                        <div class="coverage-card-title">Missing</div>
                        <p>Critical gaps</p>
                    </div>
                </div>
            `;
        }

        html += `
            <div class="accordion">
                <div class="accordion-header" onclick="toggleAccordion(this)">
                    <span>View Full Response Data</span>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="json-viewer">${this.formatJSON(data)}</div>
                </div>
            </div>
        `;

        return html;
    }
}

const resultsRenderer = new ResultsRenderer();
